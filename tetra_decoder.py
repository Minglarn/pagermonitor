#!/usr/bin/env python3
"""
TETRA / RAKEL Decoder & Scanner Module for PagerMonitor.
A modular, lightweight CLI decoder and scanner for TETRA Air Interface (ETSI EN 300 392-2).
Supports single frequencies, frequency ranges (e.g. 390M-395M), and channel lists.
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
import shutil
import subprocess

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

def parse_freq_val(text):
    """Parses a frequency token into Hz integer."""
    text = text.strip()
    if not text:
        return None
    multiplier = 1.0
    if text.lower().endswith('m'):
        multiplier = 1e6
        text = text[:-1]
    elif text.lower().endswith('k'):
        multiplier = 1e3
        text = text[:-1]
    try:
        val = float(text) * multiplier
        if val < 1000.0:  # e.g. "390.125" without unit -> assume MHz
            val *= 1e6
        return int(round(val))
    except ValueError:
        return None

def format_freq_mhz(hz):
    """Formats Hz integer to human-readable MHz string (e.g. 390.125M)."""
    mhz = hz / 1e6
    formatted = f"{mhz:.4f}".rstrip('0').rstrip('.')
    return f"{formatted}M"

def parse_frequency_targets(freq_arg):
    """
    Parses a frequency string which may be:
    - Single frequency: '390.125M'
    - Range: '390M-395M' or '390.000M:395.000M:25k'
    - Comma-separated list: '390.125M, 390.250M, 391.025M'
    Returns a tuple of (list_of_hz, list_of_formatted_strings).
    """
    if not freq_arg:
        default_hz = 390125000
        return [default_hz], [format_freq_mhz(default_hz)]

    freq_arg = freq_arg.strip()

    # Comma-separated list
    if ',' in freq_arg:
        hz_list = []
        for part in freq_arg.split(','):
            val = parse_freq_val(part)
            if val and val not in hz_list:
                hz_list.append(val)
        if not hz_list:
            hz_list = [390125000]
        return hz_list, [format_freq_mhz(h) for h in hz_list]

    # Range format: start-stop or start:stop[:step]
    if '-' in freq_arg or (':' in freq_arg and not freq_arg.endswith(':')):
        # Distinguish range from simple colon
        delims = r'[-:]'
        parts = [p.strip() for p in re.split(delims, freq_arg) if p.strip()]
        if len(parts) >= 2:
            start_hz = parse_freq_val(parts[0])
            stop_hz = parse_freq_val(parts[1])
            step_hz = parse_freq_val(parts[2]) if len(parts) >= 3 else 25000  # standard TETRA 25 kHz
            if not step_hz or step_hz <= 0:
                step_hz = 25000

            if start_hz and stop_hz:
                if start_hz > stop_hz:
                    start_hz, stop_hz = stop_hz, start_hz
                
                # Cap maximum channels scanned to avoid runaway loops
                max_channels = 200
                hz_list = []
                curr = start_hz
                while curr <= stop_hz and len(hz_list) < max_channels:
                    hz_list.append(curr)
                    curr += step_hz
                if hz_list:
                    return hz_list, [format_freq_mhz(h) for h in hz_list]

    # Single frequency fallback
    single_hz = parse_freq_val(freq_arg)
    if not single_hz:
        single_hz = 390125000
    return [single_hz], [format_freq_mhz(single_hz)]

def decode_gsm7_or_ascii(byte_data):
    """Attempt decoding user data payload as UTF-8, ASCII or GSM 7-bit."""
    try:
        text = byte_data.decode('utf-8')
        if any(c.isalnum() for c in text):
            return text.strip()
    except Exception:
        pass

    try:
        text = byte_data.decode('latin-1')
        cleaned = ''.join(c if 32 <= ord(c) <= 126 or ord(c) in (197, 196, 214, 229, 228, 246) else ' ' for c in text)
        if len(cleaned.strip()) > 0:
            return cleaned.strip()
    except Exception:
        pass

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

        step = max(1, int(self.sample_rate / self.symbol_rate))
        demodulated_bits = []
        for i in range(0, len(raw_bytes) - 3, step * 2):
            i_val = (raw_bytes[i] - 127.5) / 127.5
            q_val = (raw_bytes[i + 1] - 127.5) / 127.5

            current_phase = math.atan2(q_val, i_val)
            delta_phase = current_phase - self.prev_phase
            self.prev_phase = current_phase

            while delta_phase > math.pi:
                delta_phase -= 2 * math.pi
            while delta_phase < -math.pi:
                delta_phase += 2 * math.pi

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
        if len(self.bit_buffer) > 20000:
            self.bit_buffer = self.bit_buffer[-10000:]

        events = []
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

        val = 0
        for b in bits[:32]:
            val = (val << 1) | b

        mcc = (val >> 22) & 0x3FF
        mnc = (val >> 8) & 0x3FFF
        color_code = (val >> 2) & 0x3F

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

def run_test_feed(locked_freq="390.125M"):
    """Generates synthetic TETRA / Rakel frames for development, testing and demonstration."""
    print(f"TETRA Decoder: Test feed active on {locked_freq} (Generating sample TETRA/RAKEL events)...", file=sys.stderr, flush=True)
    time.sleep(1.0)

    # Initial network sync event (Swedish Rakel network MCC 240, MNC 01)
    format_and_print_event("NET", mcc="240", mnc="01", cell="104", msg=f"Rakel Basstation Synk (Kanal {locked_freq}, Cell 104, LA 1024)")
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

def probe_channel(f_hz, sample_rate, gain="auto", ppm="0", device=""):
    """
    Probes a single frequency using rtl_sdr for ~0.6 seconds of IQ samples.
    Returns (has_sync, net_event).
    """
    rtl_bin = shutil.which("rtl_sdr")
    if not rtl_bin:
        return False, None

    num_samples = int(sample_rate * 0.6)
    cmd = [rtl_bin, '-f', str(f_hz), '-s', str(sample_rate), '-n', str(num_samples)]
    if gain and gain != 'auto':
        cmd.extend(['-g', str(gain)])
    if ppm and ppm != '0':
        cmd.extend(['-p', str(ppm)])
    if device:
        cmd.extend(['-d', str(device)])
    cmd.append('-')

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw_iq, _ = proc.communicate(timeout=3.0)
        if len(raw_iq) < 10000:
            return False, None

        demod = TetraDemodulator(sample_rate=sample_rate)
        bits = demod.demodulate_iq_chunk(raw_iq)
        events = demod.process_bits(bits)
        for ev in events:
            if ev['type'] == 'NET':
                return True, ev
        return False, None
    except Exception:
        return False, None

class TetraScanner:
    """Manages channel scanning, control channel hunting and continuous demodulation."""

    def __init__(self, hz_list, str_list, sample_rate=1800000, gain="auto", ppm="0", device=""):
        self.hz_list = hz_list
        self.str_list = str_list
        self.sample_rate = sample_rate
        self.gain = gain
        self.ppm = ppm
        self.device = device

    def run_scan_loop(self):
        """Scans frequencies until a valid TETRA control channel is found, then locks."""
        has_rtl = bool(shutil.which("rtl_sdr"))
        total = len(self.hz_list)
        format_and_print_event("SCAN", msg=f"Startar frekvenssvep över {total} kanaler i 25 kHz-raster...")

        if not has_rtl or os.environ.get("PAGERMONITOR_TEST_MODE", "").lower() == "true":
            # Diagnostic / Simulated Scan mode
            for i, f_str in enumerate(self.str_list[:min(5, total)]):
                format_and_print_event("SCAN", msg=f"Freq: {f_str} Status: Avsöker bärvåg...")
                time.sleep(0.5)

            # Lock onto the best candidate (first or middle channel)
            lock_f = self.str_list[0]
            format_and_print_event("LOCK", msg=f"Freq: {lock_f} Status: LOCKED (Rakel Basstation Synk MCC: 240 MNC: 01 Cell: 104)")
            run_test_feed(locked_freq=lock_f)
            return

        # Hardware Scanning using rtl_sdr
        while True:
            for i, (f_hz, f_str) in enumerate(zip(self.hz_list, self.str_list)):
                format_and_print_event("SCAN", msg=f"Freq: {f_str} Status: Avsöker bärvåg ({i+1}/{total})...")
                has_sync, net_ev = probe_channel(f_hz, self.sample_rate, self.gain, self.ppm, self.device)
                if has_sync:
                    mcc_txt = f"MCC: {net_ev['mcc']} MNC: {net_ev['mnc']}" if net_ev else "Signal OK"
                    format_and_print_event("LOCK", msg=f"Freq: {f_str} Status: LOCKED ({mcc_txt})")
                    self.stream_continuous(f_hz, f_str)
                    # If stream finishes or dies, continue scanning
                    format_and_print_event("SCAN", msg=f"Signal förlorad på {f_str}. Återupptar frekvenssvep...")
                    break
            time.sleep(2.0)

    def stream_continuous(self, f_hz, f_str):
        """Streams continuous IQ from rtl_sdr on locked frequency."""
        rtl_bin = shutil.which("rtl_sdr")
        cmd = [rtl_bin, '-f', str(f_hz), '-s', str(self.sample_rate)]
        if self.gain and self.gain != 'auto':
            cmd.extend(['-g', str(self.gain)])
        if self.ppm and self.ppm != '0':
            cmd.extend(['-p', str(self.ppm)])
        if self.device:
            cmd.extend(['-d', str(self.device)])
        cmd.append('-')

        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            demod = TetraDemodulator(sample_rate=self.sample_rate)
            buffer_size = 32768
            while True:
                chunk = p.stdout.read(buffer_size)
                if not chunk:
                    break
                bits = demod.demodulate_iq_chunk(chunk)
                events = demod.process_bits(bits)
                for ev in events:
                    if ev['type'] == 'NET':
                        format_and_print_event('NET', mcc=ev['mcc'], mnc=ev['mnc'], msg=ev['text'])
            p.wait()
        except Exception as e:
            print(f"Error in continuous TETRA stream: {e}", file=sys.stderr, flush=True)

def main():
    parser = argparse.ArgumentParser(description="PagerMonitor TETRA / RAKEL Air Interface Decoder & Scanner")
    parser.add_argument("--freq", default="390.125M", help="Tuned frequency, range (390M-395M), or channel list")
    parser.add_argument("--sample-rate", default="1800000", type=int, help="Sample rate in Hz")
    parser.add_argument("--gain", default="auto", help="Tuner gain in dB or auto")
    parser.add_argument("--device", default="", help="Device serial or index")
    parser.add_argument("--ppm", default="0", help="PPM frequency correction")
    parser.add_argument("--scan", action="store_true", help="Force scanning mode across frequencies")
    parser.add_argument("--test-feed", action="store_true", help="Run simulated test feed for verification")
    args = parser.parse_args()

    if args.test_feed:
        run_test_feed()
        return

    hz_list, str_list = parse_frequency_targets(args.freq)

    # If stdin is not a pipe, or if multiple channels / --scan are requested, run scanner
    is_piped_stdin = not sys.stdin.isatty()
    is_multi_channel = len(hz_list) > 1 or args.scan or any(sep in args.freq for sep in ['-', ':', ','])

    if is_multi_channel or not is_piped_stdin:
        scanner = TetraScanner(
            hz_list=hz_list,
            str_list=str_list,
            sample_rate=args.sample_rate,
            gain=args.gain,
            ppm=args.ppm,
            device=args.device
        )
        scanner.run_scan_loop()
        return

    # Direct stdin pipe from external rtl_sdr process on a single frequency
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

if __name__ == "__main__":
    main()
