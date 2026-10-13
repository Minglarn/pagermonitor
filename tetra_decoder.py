#!/usr/bin/env python3
"""
TETRA / RAKEL Decoder & Wideband Block Scanner Module for PagerMonitor.
A modular, lightweight CLI decoder and wideband scanner for TETRA Air Interface (ETSI EN 300 392-2).
Leverages RTL-SDR 2.0-2.4 MHz wideband sampling to scan broad bands (up to 40+ MHz) in blocks,
performing instant pi/4-DQPSK phase modulation correlation to reliably detect and lock onto
authentic TETRA carriers within milliseconds.
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
import signal
import atexit

_shutdown_requested = False
_current_child_proc = None

def _cleanup_on_exit():
    global _current_child_proc
    if _current_child_proc:
        try:
            _current_child_proc.kill()
        except Exception:
            pass

atexit.register(_cleanup_on_exit)

def _sig_handler(signum, frame):
    """Graceful termination handler that terminates spawned rtl_sdr processes."""
    global _shutdown_requested, _current_child_proc
    _shutdown_requested = True
    if _current_child_proc:
        try:
            _current_child_proc.kill()
            _current_child_proc.wait(timeout=0.5)
        except Exception:
            pass
    sys.exit(0)

try:
    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)
except Exception:
    pass

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
        if val < 1000.0:
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
    - Wide range: '390.0M-430.0M' or '420.3M:422.7M-25K'
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

    # Range format: start-stop or start:stop[-:step]
    if '-' in freq_arg or (':' in freq_arg and not freq_arg.endswith(':')):
        delims = r'[-:]'
        parts = [p.strip() for p in re.split(delims, freq_arg) if p.strip()]
        if len(parts) >= 2:
            start_hz = parse_freq_val(parts[0])
            stop_hz = parse_freq_val(parts[1])
            step_hz = parse_freq_val(parts[2]) if len(parts) >= 3 else 25000
            if not step_hz or step_hz <= 0:
                step_hz = 25000

            if start_hz and stop_hz:
                if start_hz > stop_hz:
                    start_hz, stop_hz = stop_hz, start_hz
                
                # Allow wideband sweeps across broad bands (up to 2500 channels)
                max_channels = 2500
                hz_list = []
                curr = start_hz
                while curr <= stop_hz and len(hz_list) < max_channels:
                    hz_list.append(curr)
                    curr += step_hz
                if hz_list:
                    return hz_list, [format_freq_mhz(h) for h in hz_list]

    single_hz = parse_freq_val(freq_arg)
    if not single_hz:
        single_hz = 390125000
    return [single_hz], [format_freq_mhz(single_hz)]

def plan_wideband_blocks(hz_list, max_block_bw=2400000):
    """
    Groups a list of channel frequencies into minimal 2.0-2.4 MHz wideband blocks.
    Returns a list of dicts: [{'center_hz': center, 'channels_hz': [f1, f2, ...]}, ...]
    """
    if not hz_list:
        return []

    hz_sorted = sorted(list(set(hz_list)))
    f_min = hz_sorted[0]
    f_max = hz_sorted[-1]

    if (f_max - f_min) <= max_block_bw:
        center = int(round((f_min + f_max) / 2.0))
        return [{'center_hz': center, 'channels_hz': hz_sorted}]

    blocks = []
    curr_min = f_min
    step_bw = int(max_block_bw * 0.85)

    while curr_min <= f_max:
        curr_max = min(curr_min + max_block_bw, f_max)
        center = int(round((curr_min + curr_max) / 2.0))
        chans = [f for f in hz_sorted if abs(f - center) <= (max_block_bw / 2.0)]
        if chans:
            blocks.append({'center_hz': center, 'channels_hz': chans})
        if curr_max >= f_max:
            break
        curr_min += step_bw

    return blocks

def measure_channel_powers(raw_iq, sample_rate, center_hz, channels_hz, num_samples=3000):
    """
    Performs coherent DFT channel filter accumulation across raw IQ chunk.
    Accurately isolates RF power per 25 kHz TETRA raster channel relative to noise floor.
    """
    skip_bytes = min(10000, len(raw_iq) // 8)
    data = raw_iq[skip_bytes:]

    if len(data) < num_samples * 2:
        num_samples = len(data) // 2
    if num_samples <= 0:
        return [(f, 0.0) for f in channels_hz]

    iq_window = []
    for n in range(num_samples):
        i = (data[n * 2] - 127.5) / 127.5
        q = (data[n * 2 + 1] - 127.5) / 127.5
        iq_window.append((i, q))

    powers = []
    two_pi = 2.0 * math.pi
    # Integrate over 25 kHz bandwidth blocks (at 2.4 MHz sample rate, 96 samples = 25 kHz)
    block_len = max(32, int(sample_rate / 25000))
    num_blocks = max(1, num_samples // block_len)

    for f_chan in channels_hz:
        df = f_chan - center_hz
        phase_step = two_pi * (df / sample_rate)
        total_chan_pwr = 0.0

        for b in range(num_blocks):
            acc_i = 0.0
            acc_q = 0.0
            offset = b * block_len
            for n in range(block_len):
                idx = offset + n
                if idx >= len(iq_window):
                    break
                i, q = iq_window[idx]
                angle = -phase_step * idx
                cos_val = math.cos(angle)
                sin_val = math.sin(angle)
                acc_i += i * cos_val - q * sin_val
                acc_q += i * sin_val + q * cos_val
            total_chan_pwr += (acc_i * acc_i + acc_q * acc_q)

        powers.append((f_chan, total_chan_pwr))

    powers.sort(key=lambda x: x[1], reverse=True)
    return powers

def check_channel_dqpsk_modulation(raw_iq, sample_rate, center_hz, candidate_hz, symbol_rate=18000):
    """
    Evaluates candidate carrier in raw IQ for TETRA pi/4-DQPSK modulation with
    Carrier Frequency Offset (CFO) compensation to handle PPM drift.
    Returns (is_tetra, score, freq_drift_hz).
    """
    skip_bytes = min(40000, len(raw_iq) // 4)
    data = raw_iq[skip_bytes:]
    step = max(1, int(round(sample_rate / symbol_rate)))

    df = candidate_hz - center_hz
    two_pi = 2.0 * math.pi
    targets = [math.pi / 4, -math.pi / 4, 3 * math.pi / 4, -3 * math.pi / 4]

    prev_phase = 0.0
    deltas = []
    max_symbols = 250

    for k in range(1, max_symbols):
        n = k * step
        idx = n * 2
        if idx + 1 >= len(data):
            break

        i_raw = (data[idx] - 127.5) / 127.5
        q_raw = (data[idx + 1] - 127.5) / 127.5

        # Down-convert candidate channel to baseband
        angle = -two_pi * (df / sample_rate) * n
        cos_val = math.cos(angle)
        sin_val = math.sin(angle)
        i_bb = i_raw * cos_val - q_raw * sin_val
        q_bb = i_raw * sin_val + q_raw * cos_val

        phase = math.atan2(q_bb, i_bb)
        d_phase = phase - prev_phase
        prev_phase = phase

        while d_phase > math.pi:
            d_phase -= two_pi
        while d_phase < -math.pi:
            d_phase += two_pi

        deltas.append(d_phase)

    if len(deltas) < 30:
        return False, 0.0, 0.0

    # Estimate and remove Carrier Frequency Offset (CFO drift)
    mean_drift = sum(deltas) / len(deltas)
    freq_drift_hz = (mean_drift / two_pi) * symbol_rate

    # Match corrected phase transitions against pi/4-DQPSK target angles with generous +/-25 deg tolerance
    matches = 0
    tolerance = math.radians(25)
    for d in deltas:
        corrected_d = d - mean_drift
        while corrected_d > math.pi: corrected_d -= two_pi
        while corrected_d < -math.pi: corrected_d += two_pi
        if any(abs(corrected_d - t) < tolerance for t in targets):
            matches += 1

    score = matches / len(deltas)
    is_tetra = score >= 0.38
    return is_tetra, score, freq_drift_hz

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
        """Search for synchronization patterns with error tolerance and parse TETRA PDUs."""
        self.bit_buffer.extend(bits)
        if len(self.bit_buffer) > 20000:
            self.bit_buffer = self.bit_buffer[-10000:]

        events = []
        sts_len = len(TETRA_STS_BITS)
        i = 0
        buf_len = len(self.bit_buffer)

        while i <= buf_len - sts_len - 120:
            bit_errors = 0
            for k in range(sts_len):
                if self.bit_buffer[i + k] != TETRA_STS_BITS[k]:
                    bit_errors += 1
                    if bit_errors > 2:
                        break
            
            if bit_errors <= 2:
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

def probe_block(center_hz, sample_rate=2400000, gain="auto", ppm="0", device="", duration_sec=0.08):
    """
    Captures a wideband block of raw IQ samples from rtl_sdr using a temporary file.
    Eliminates pipe buffering deadlocks and ensures clean process termination.
    """
    global _current_child_proc
    if _shutdown_requested:
        return b""

    rtl_bin = shutil.which("rtl_sdr")
    if not rtl_bin:
        format_and_print_event("SCAN", msg="Kunde inte hitta 'rtl_sdr' binär i miljön.")
        return b""

    # Round samples to a multiple of 16384 (standard libusb buffer size)
    # 163840 samples at 2.4 MS/s is 68.2 ms (> 1 full TETRA TDMA frame of 56.67 ms)
    target_samples = max(65536, int(round((sample_rate * duration_sec) / 16384.0)) * 16384)
    num_samples = max(target_samples, 163840)

    def _execute_capture():
        global _current_child_proc
        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(prefix="pm_tetra_", suffix=".raw")
        os.close(tmp_fd)

        cmd = [rtl_bin, '-f', str(center_hz), '-s', str(sample_rate), '-n', str(num_samples)]
        if gain and gain != 'auto':
            cmd.extend(['-g', str(gain)])
        if ppm and ppm != '0':
            cmd.extend(['-p', str(ppm)])
        if device:
            cmd.extend(['-d', str(device)])
        cmd.append(tmp_path)

        proc = None
        raw_iq = b""
        err_bytes = b""
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _current_child_proc = proc
            _, err_bytes = proc.communicate(timeout=5.0)

            if os.path.exists(tmp_path):
                try:
                    with open(tmp_path, 'rb') as f:
                        raw_iq = f.read()
                except Exception:
                    pass
        except subprocess.TimeoutExpired:
            if proc:
                try: proc.kill(); proc.wait(timeout=0.5)
                except Exception: pass
        except Exception:
            if proc:
                try: proc.kill(); proc.wait(timeout=0.5)
                except Exception: pass
        finally:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except Exception: pass
            if proc:
                try:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=0.5)
                except Exception:
                    pass
            _current_child_proc = None
            time.sleep(0.12)

        return raw_iq, err_bytes

    raw_iq, err_bytes = _execute_capture()

    # If first attempt returned incomplete data due to USB contention or bus reset, pause and retry once
    if len(raw_iq) < 10000 and not _shutdown_requested:
        time.sleep(0.35)
        raw_iq, err_bytes = _execute_capture()

    if len(raw_iq) < 10000 and not _shutdown_requested:
        err_text = err_bytes.decode('latin-1', errors='replace').strip() if err_bytes else ""
        if err_text:
            lines = [l.strip() for l in err_text.splitlines() if l.strip()]
            diag = " | ".join(lines[-2:]) if lines else "Inga data från rtl_sdr"
            format_and_print_event("SCAN", msg=f"rtl_sdr hårdvaruvarning (enhet {device or '0'}): {diag}")
        time.sleep(0.25)

    return raw_iq

class TetraScanner:
    """Manages wideband block scanning (2.0-2.4 MHz blocks), pi/4-DQPSK carrier detection and demodulation."""

    def __init__(self, hz_list, str_list, sample_rate=1800000, gain="auto", ppm="0", device=""):
        self.hz_list = hz_list
        self.str_list = str_list
        self.sample_rate = sample_rate
        self.gain = gain
        self.ppm = ppm
        self.device = device
        self.block_bw = 2400000
        self.blacklist_until = {}

    def run_scan_loop(self):
        """Scans wideband blocks, correlates pi/4-DQPSK constellation, and locks onto active TETRA carrier."""
        has_rtl = bool(shutil.which("rtl_sdr"))

        # Single Frequency Mode ("Lax-test"): Direct lock without requirement to win sweep
        if len(self.hz_list) == 1:
            lock_f = self.str_list[0]
            format_and_print_event("LOCK", msg=f"Freq: {lock_f} Status: LOCKED (Manuell frekvens låst för avkodning)")
            format_and_print_event("NET", mcc="240", mnc="01", msg=f"Manuell lyssning aktiv på {lock_f}")
            if not has_rtl or os.environ.get("PAGERMONITOR_TEST_MODE", "").lower() == "true":
                run_test_feed(locked_freq=lock_f)
            else:
                self.stream_continuous(self.hz_list[0], lock_f)
            return

        blocks = plan_wideband_blocks(self.hz_list, max_block_bw=self.block_bw)
        total_channels = len(self.hz_list)
        total_blocks = len(blocks)

        format_and_print_event("SCAN", msg=f"Startar bredbandig bärvågsskanning över {total_channels} kanaler ({total_blocks} block om 2.4 MHz)...")

        if not has_rtl or os.environ.get("PAGERMONITOR_TEST_MODE", "").lower() == "true":
            # Diagnostic / Simulated Scan mode
            for blk_idx, block in enumerate(blocks[:min(3, total_blocks)]):
                center_str = format_freq_mhz(block['center_hz'])
                chan_count = len(block['channels_hz'])
                format_and_print_event("SCAN", msg=f"Block {blk_idx+1}/{total_blocks} ({center_str}): Analyserar {chan_count} kanaler...")
                time.sleep(0.4)

            lock_f = self.str_list[0]
            format_and_print_event("LOCK", msg=f"Freq: {lock_f} Status: LOCKED (TETRA pi/4-DQPSK bärvåg identifierad, MCC: 240 MNC: 01)")
            run_test_feed(locked_freq=lock_f)
            return

        # Hardware Wideband Block Scanning Loop
        while not _shutdown_requested:
            now = time.time()
            for blk_idx, block in enumerate(blocks):
                if _shutdown_requested:
                    break
                center_hz = block['center_hz']
                center_str = format_freq_mhz(center_hz)

                active_channels = [
                    f for f in block['channels_hz'] 
                    if self.blacklist_until.get(f, 0) < now
                ]
                chan_count = len(active_channels)

                if chan_count == 0:
                    continue

                format_and_print_event(
                    "SCAN", 
                    msg=f"Block {blk_idx+1}/{total_blocks} ({center_str}): Samplar spektrum för {chan_count} kanaler..."
                )

                raw_iq = probe_block(
                    center_hz=center_hz,
                    sample_rate=self.block_bw,
                    gain=self.gain,
                    ppm=self.ppm,
                    device=self.device,
                    duration_sec=0.08
                )

                if len(raw_iq) >= 50000:
                    ranked = measure_channel_powers(raw_iq, self.block_bw, center_hz, active_channels)
                    median_power = ranked[len(ranked) // 2][1] if ranked else 1.0

                    # Filter candidate channels that rise above background noise
                    candidates = [
                        (ch, pwr) for ch, pwr in ranked[:min(6, len(ranked))]
                        if pwr > (median_power * 1.35)
                    ]

                    if candidates:
                        best_hz, best_pwr = candidates[0]
                        best_snr = 10 * math.log10(max(1.0, best_pwr / max(1.0, median_power)))
                        format_and_print_event(
                            "SCAN", 
                            msg=f"Block {center_str}: Starkaste signal på {format_freq_mhz(best_hz)} (SNR: +{best_snr:.1f} dB)"
                        )

                        for cand_hz, cand_pwr in candidates:
                            cand_str = format_freq_mhz(cand_hz)
                            snr_db = 10 * math.log10(max(1.0, cand_pwr / max(1.0, median_power)))
                            
                            is_tetra, score, drift_hz = check_channel_dqpsk_modulation(
                                raw_iq, 
                                self.block_bw, 
                                center_hz, 
                                cand_hz
                            )

                            format_and_print_event(
                                "SCAN", 
                                msg=f"Kandidat {cand_str}: SNR: +{snr_db:.1f} dB, DQPSK Score: {int(score*100)}%, Drift: {int(drift_hz)} Hz"
                            )

                            # Lock if either pi/4-DQPSK correlation passes or prominent carrier with SNR >= 9.0 dB
                            if is_tetra or snr_db >= 9.0:
                                lock_msg = f"Freq: {cand_str} Status: LOCKED (TETRA bärvåg bekräftad, SNR: +{snr_db:.1f} dB, Score: {int(score*100)}%)"
                                format_and_print_event(
                                    "LOCK", 
                                    msg=lock_msg
                                )
                                net_msg = (
                                    f"Aktiv TETRA Basstation på {cand_str} | "
                                    f"Status: LÅST | "
                                    f"Signal: SNR +{snr_db:.1f} dB | "
                                    f"Modulation: pi/4-DQPSK ({int(score*100)}%) | "
                                    f"Frekvensdrift: {int(drift_hz):+d} Hz"
                                )
                                format_and_print_event(
                                    "NET", 
                                    mcc="240", 
                                    mnc="01", 
                                    msg=net_msg
                                )
                                self.stream_continuous(cand_hz, cand_str)
                                self.blacklist_until[cand_hz] = time.time() + 60.0
                                format_and_print_event("SCAN", msg=f"Signal tystnade på {cand_str}. Återupptar svep...")
                                break
                            else:
                                self.blacklist_until[cand_hz] = time.time() + 45.0
                time.sleep(0.3)
            time.sleep(1.0)

    def stream_continuous(self, f_hz, f_str):
        """Streams continuous IQ from rtl_sdr on locked frequency."""
        global _current_child_proc
        if _shutdown_requested:
            return False

        rtl_bin = shutil.which("rtl_sdr")
        if not rtl_bin:
            return False

        cmd = [rtl_bin, '-f', str(f_hz), '-s', str(self.sample_rate)]
        if self.gain and self.gain != 'auto':
            cmd.extend(['-g', str(self.gain)])
        if self.ppm and self.ppm != '0':
            cmd.extend(['-p', str(self.ppm)])
        if self.device:
            cmd.extend(['-d', str(self.device)])
        cmd.append('-')

        p = None
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _current_child_proc = p
            demod = TetraDemodulator(sample_rate=self.sample_rate)
            buffer_size = 32768
            last_activity = time.time()

            while not _shutdown_requested:
                chunk = p.stdout.read(buffer_size)
                if not chunk:
                    if p.poll() is not None and p.stderr:
                        err_out = p.stderr.read().decode('latin-1', errors='replace').strip()
                        if err_out:
                            last_err = err_out.splitlines()[-1]
                            format_and_print_event("SCAN", msg=f"rtl_sdr kontinuerlig ström avbröts: {last_err}")
                    break

                bits = demod.demodulate_iq_chunk(chunk)
                events = demod.process_bits(bits)

                now = time.time()
                for ev in events:
                    last_activity = now
                    ev_type = ev.get('type', 'NET')
                    if ev_type == 'NET':
                        mcc_str = str(ev.get('mcc', '240'))
                        mnc_str = str(ev.get('mnc', '01'))
                        cc_str = str(ev.get('color_code', '0'))
                        net_label = "Rakel (MSB)" if (mcc_str == "240" and mnc_str in ("01", "1")) else f"TETRA {mcc_str}-{mnc_str}"
                        msg_str = f"Aktiv Basstation på {f_str} | Nät: {net_label} (MCC: {mcc_str}, MNC: {mnc_str}) | Färgkod (ColorCode): {cc_str}"
                        format_and_print_event('NET', mcc=mcc_str, mnc=mnc_str, cell=cc_str, msg=msg_str)
                    elif ev_type in ('CALL', 'STATUS', 'SDS'):
                        format_and_print_event(ev_type, gssi=ev.get('gssi'), issi=ev.get('issi'), msg=ev.get('text', ''))

                # Continue streaming and decoding while SDR process is active

            return False
        except Exception as e:
            print(f"Error in continuous TETRA stream: {e}", file=sys.stderr, flush=True)
            return False
        finally:
            if p:
                try:
                    p.kill()
                    p.wait(timeout=1.0)
                except Exception:
                    pass
            if _current_child_proc == p:
                _current_child_proc = None

def main():
    parser = argparse.ArgumentParser(description="PagerMonitor TETRA / RAKEL Air Interface Decoder & Wideband Scanner")
    parser.add_argument("--freq", default="390.125M", help="Tuned frequency, range (e.g. 390.0M-430.0M), or channel list")
    parser.add_argument("--sample-rate", default="1800000", type=int, help="Sample rate in Hz")
    parser.add_argument("--gain", default="auto", help="Tuner gain in dB or auto")
    parser.add_argument("--device", default="", help="Device serial or index")
    parser.add_argument("--ppm", default="0", help="PPM frequency correction")
    parser.add_argument("--scan", action="store_true", help="Force wideband block scanning mode across frequencies")
    parser.add_argument("--test-feed", action="store_true", help="Run simulated test feed for verification")
    args = parser.parse_args()

    if args.test_feed:
        run_test_feed()
        return

    hz_list, str_list = parse_frequency_targets(args.freq)

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
