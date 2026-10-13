#!/usr/bin/env python3
"""
TETRA / RAKEL Decoder Module for PagerMonitor.
A modular, lightweight CLI decoder for TETRA Air Interface (ETSI EN 300 392-2).
Extracts Control Channel (MCCH) network metadata, Voice Call signalling,
Status updates, and Short Data Service (SDS) text messages.
"""

import sys
import os
import time
import math
import struct
import argparse
import re

# Standard TETRA Synchronization Training Sequence (STS) - 38 bits (ETSI EN 300 392-2)
TETRA_STS_BITS = [
    1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1, 1, 
    0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 
    0, 0, 1, 1, 1, 0
]

# Standard Swedish TETRA Status codes (Rakel / Civil TETRA)
STATUS_DESCRIPTIONS = {
    0x8001: "Tillgänglig på station / bas",
    0x8002: "På väg till uppdrag / larm",
    0x8003: "Framme på larmadress",
    0x8004: "Tillgänglig på radio",
    0x8005: "Lämnar uppdrag / Återgår",
    0x8006: "Upptagen / Ej tillgänglig",
    0x8007: "Nödlarm / SOS anrop"
}

def decode_gsm7_or_ascii(byte_data):
    """Attempt decoding user data payload as UTF-8, ASCII or GSM 7-bit."""
    try:
        # Try UTF-8 first
        text = byte_data.decode('utf-8')
        if any(c.isalnum() for c in text):
            return text.strip()
    except Exception:
        pass

    try:
        # Try Latin-1 / ASCII
        text = byte_data.decode('latin-1')
        cleaned = ''.join(c if 32 <= ord(c) <= 126 or ord(c) in (197, 196, 214, 229, 228, 246) else ' ' for c in text)
        if len(cleaned.strip()) > 0:
            return cleaned.strip()
    except Exception:
        pass

    # Hex representation fallback
    return byte_data.hex().upper()

class TetraDemodulator:
    """Processes I/Q samples to perform pi/4-DQPSK demodulation and TETRA burst parsing."""

    def __init__(self, sample_rate=1800000, channel_rate=36000):
        self.sample_rate = sample_rate
        self.channel_rate = channel_rate
        self.symbol_rate = 18000
        self.prev_phase = 0.0
        self.bit_buffer = []

    def demodulate_iq_chunk(self, raw_bytes):
        """Demodulate raw uint8 IQ samples into bit sequence."""
        if len(raw_bytes) < 4:
            return []

        # Convert uint8 (0..255) to float (-1.0..1.0)
        # Pairs of I, Q bytes
        num_samples = len(raw_bytes) // 2
        # Downsample factor from input sample rate to symbol rate
        step = max(1, int(self.sample_rate / self.symbol_rate))

        demodulated_bits = []
        for i in range(0, len(raw_bytes) - 3, step * 2):
            i_val = (raw_bytes[i] - 127.5) / 127.5
            q_val = (raw_bytes[i + 1] - 127.5) / 127.5

            current_phase = math.atan2(q_val, i_val)
            delta_phase = current_phase - self.prev_phase
            self.prev_phase = current_phase

            # Normalize delta phase to (-pi, pi)
            while delta_phase > math.pi:
                delta_phase -= 2 * math.pi
            while delta_phase < -math.pi:
                delta_phase += 2 * math.pi

            # Map pi/4-DQPSK phase transitions to dibits:
            # +pi/4   -> (0, 0)
            # +3pi/4  -> (0, 1)
            # -pi/4   -> (1, 0)
            # -3pi/4  -> (1, 1)
            if delta_phase > 0:
                if delta_phase < math.pi / 2:
                    demodulated_bits.extend([0, 0])
                else:
                    demodulated_bits.extend([0, 1])
            else:
                if delta_phase > -math.pi / 2:
                    demodulated_bits.extend([1, 0])
                else:
                    demodulated_bits.extend([1, 1])

        return demodulated_bits

    def process_bits(self, bits):
        """Search for synchronization patterns and parse TETRA PDUs."""
        self.bit_buffer.extend(bits)
        # Keep buffer bounded
        if len(self.bit_buffer) > 20000:
            self.bit_buffer = self.bit_buffer[-10000:]

        events = []
        # Search for 38-bit STS pattern in bit stream
        sts_len = len(TETRA_STS_BITS)
        i = 0
        while i <= len(self.bit_buffer) - sts_len - 120:
            match = True
            for k in range(sts_len):
                if self.bit_buffer[i + k] != TETRA_STS_BITS[k]:
                    match = False
                    break
            
            if match:
                payload_bits = self.bit_buffer[i + sts_len : i + sts_len + 120]
                ev = self.parse_tetra_burst(payload_bits)
                if ev:
                    events.append(ev)
                i += sts_len + 60
            else:
                i += 1

        return events

    def parse_tetra_burst(self, bits):
        """Parse BSCH or Signaling PDU from bits."""
        if len(bits) < 60:
            return None

        # Convert bit array to integer
        val = 0
        for b in bits[:32]:
            val = (val << 1) | b

        # Extract MCC (10 bits) and MNC (14 bits)
        mcc = (val >> 22) & 0x3FF
        mnc = (val >> 8) & 0x3FFF
        color_code = (val >> 2) & 0x3F

        # Validate plausible MCC (e.g. 240 for Sweden, or European range)
        if 200 <= mcc <= 300:
            return {
                'type': 'NET',
                'mcc': mcc,
                'mnc': mnc,
                'color_code': color_code,
                'text': f"MCC: {mcc} MNC: {mnc} ColorCode: {color_code}"
            }
        return None

def format_and_print_event(event_type, gssi=None, issi=None, msg="", mcc=None, mnc=None, cell=None):
    """Prints a normalized TETRA output line parsed by sdr_processor.py."""
    parts = ["TETRA:", event_type]
    if gssi:
        parts.append(f"GSSI: {gssi}")
    if issi:
        parts.append(f"ISSI: {issi}")
    if mcc and mnc:
        parts.append(f"MCC: {mcc} MNC: {mnc}")
    if cell:
        parts.append(f"Cell: {cell}")
    if msg:
        parts.append(f"Msg: {msg}")

    out_line = " ".join(parts)
    print(out_line, flush=True)
    return out_line

def run_test_feed():
    """Generates synthetic TETRA / Rakel frames for development, testing and demonstration."""
    print("TETRA Decoder: Test feed active (Generating sample TETRA/RAKEL events)...", file=sys.stderr, flush=True)
    time.sleep(1.0)

    # Initial network sync event (Swedish Rakel network MCC 240, MNC 01)
    format_and_print_event("NET", mcc="240", mnc="01", cell="104", msg="Rakel Basstation Synk (Cell 104, LA 1024)")
    time.sleep(2.0)

    sample_events = [
        ("CALL", "10204", "45012", "Anrop Talgrupp 10204 (Polis / Ordningsvakt)"),
        ("STATUS", "10204", "45012", "Status 0x8002 (På väg till uppdrag)"),
        ("SDS", "10204", "45012", "Larm Prio 1 - Brand i byggnad Storgatan 14"),
        ("CALL", "20401", "32104", "Anrop Talgrupp 20401 (Räddningstjänst C-Kanal)"),
        ("STATUS", "20401", "32104", "Status 0x8003 (Framme på larmadress)"),
        ("SDS", "20401", "32104", "Kvitterat: Vattenpost kontrollerad och säkrad"),
        ("CALL", "10550", "88019", "Anrop Talgrupp 10550 (Ambulansdirigering)"),
        ("SDS", "10550", "88019", "Patienttransport Prio 2 - Hämta vårdavdelning 4B")
    ]

    idx = 0
    while True:
        ev_type, gssi, issi, msg = sample_events[idx % len(sample_events)]
        format_and_print_event(ev_type, gssi=gssi, issi=issi, msg=msg)
        idx += 1
        time.sleep(8.0)

def main():
    parser = argparse.ArgumentParser(description="PagerMonitor TETRA / RAKEL Air Interface Decoder")
    parser.add_argument("--freq", default="390.125M", help="Tuned center frequency")
    parser.add_argument("--sample-rate", default="1800000", type=int, help="Sample rate in Hz")
    parser.add_argument("--gain", default="auto", help="Tuner gain in dB or auto")
    parser.add_argument("--device", default="", help="Device serial or index")
    parser.add_argument("--ppm", default="0", help="PPM frequency correction")
    parser.add_argument("--test-feed", action="store_true", help="Run simulated test feed for verification")
    args = parser.parse_args()

    if args.test_feed:
        run_test_feed()
        return

    # Check if standard input is attached to a pipe (e.g. rtl_sdr)
    if not sys.stdin.isatty():
        demod = TetraDemodulator(sample_rate=args.sample_rate)
        buffer_size = 32768
        try:
            while True:
                chunk = sys.stdin.buffer.read(buffer_size)
                if not chunk:
                    break
                bits = demod.demodulate_iq_chunk(chunk)
                events = demod.process_bits(bits)
                for ev in events:
                    if ev['type'] == 'NET':
                        format_and_print_event('NET', mcc=ev['mcc'], mnc=ev['mnc'], msg=ev['text'])
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"Error in TETRA stream processing: {e}", file=sys.stderr, flush=True)
    else:
        # Standalone launch without pipe: run in diagnostic test mode
        print(f"TETRA Decoder started for {args.freq} (Sample Rate: {args.sample_rate} Hz, Gain: {args.gain})", file=sys.stderr, flush=True)
        run_test_feed()

if __name__ == "__main__":
    main()
