#!/usr/bin/env python3
"""
RDS / RDS-TMC Decoder Module for PagerMonitor.
Decodes RDS-TMC (ALERT-C / ISO 14819) traffic events and standard RDS metadata
from redsea or direct FM SDR stream. Translates TMC location codes using Sweden
Location Table LTN 01 (Trafikverket) and event codes to human-readable Swedish.
Features automatic FM band scanning and station hunting (SR P4 / P3).
"""

import sys
import os
import time
import json
import argparse
import subprocess
import signal
import atexit
import re
import threading
import queue

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

_shutdown_requested = False
_current_child_proc = None

# Heartbeat / Pulsmätare för RDS-mottagning
_heartbeat_lock = threading.Lock()
_heartbeat_stats = {
    'last_frame_time': time.time(),
    'last_pi': None,
    'last_ps': None,
    'frames_since_last_pulse': 0,
    'last_pulse_log_time': time.time(),
    'heartbeat_interval': 10.0,
    'heartbeat_timeout': 5.0,
    'gain': 'auto',
    'freq': '103.3M',
    'has_received_any_frame': False,
    'groups_seen': set(),
    'has_seen_tmc_3a': False,
    'has_seen_tmc_8a': False
}
_heartbeat_thread_started = False

def record_rds_frame(pi=None, ps=None, group=None, count=1):
    """
    Registrerar en eller flera giltiga mottagna RDS-ramar med korrekt checksumma.
    Uppdaterar timestamp för senaste aktivitet och sparar senaste kända PI, PS och grupper.
    """
    now = time.time()
    with _heartbeat_lock:
        _heartbeat_stats['last_frame_time'] = now
        _heartbeat_stats['frames_since_last_pulse'] += count
        _heartbeat_stats['has_received_any_frame'] = True
        if pi:
            pi_clean = str(pi).strip()
            if not pi_clean.startswith("0x") and not pi_clean.startswith("0X"):
                pi_clean = f"0x{pi_clean.upper()}"
            _heartbeat_stats['last_pi'] = pi_clean
        if ps:
            ps_clean = str(ps).strip()
            if ps_clean:
                _heartbeat_stats['last_ps'] = ps_clean
        if group:
            grp_clean = str(group).strip().upper()
            if grp_clean:
                _heartbeat_stats['groups_seen'].add(grp_clean)

def _heartbeat_worker():
    """
    Trådsäker bakgrundsövervakare som periodiskt kontrollerar och loggar
    RDS-mottagningens puls, synkstatus, signalkvalitet och tuner-gain.
    """
    while not _shutdown_requested:
        time.sleep(0.5)
        now = time.time()
        with _heartbeat_lock:
            interval = _heartbeat_stats['heartbeat_interval']
            timeout = _heartbeat_stats['heartbeat_timeout']
            last_log = _heartbeat_stats['last_pulse_log_time']
            last_frame = _heartbeat_stats['last_frame_time']
            has_received = _heartbeat_stats['has_received_any_frame']
            count = _heartbeat_stats['frames_since_last_pulse']
            pi = _heartbeat_stats['last_pi']
            ps = _heartbeat_stats['last_ps']
            freq_val = _heartbeat_stats.get('freq') or chosen_freq_global or "FM"
            gain_val = _heartbeat_stats.get('gain', 'auto')

            if (now - last_log) < interval:
                continue

            time_since_last_frame = now - last_frame
            time_window = max(0.1, now - last_log)

            # Nollställ räknare för nästa intervall
            _heartbeat_stats['last_pulse_log_time'] = now
            _heartbeat_stats['frames_since_last_pulse'] = 0

        # Formatera gain-beskrivning
        gain_str = str(gain_val).strip() if gain_val is not None else "auto"
        if not gain_str or gain_str.lower() == "auto":
            gain_display = "auto"
        elif "db" not in gain_str.lower():
            gain_display = f"{gain_str} dB"
        else:
            gain_display = gain_str

        # Kontrollera mottagningens synk och aktivitet
        if has_received and time_since_last_frame <= timeout:
            rate = count / time_window
            # Teoretisk maxhastighet för RDS är ~11.41 grupper/ramar per sekund (1187.5 bit/s / 104 bitar/grupp)
            quality_pct = int(round((rate / 11.41) * 100))
            quality_pct = max(0, min(100, quality_pct))

            if quality_pct >= 90:
                qual_desc = "Perfekt mottagning"
                status_str = "SYNKERAD"
                hb_type = "OK"
            elif quality_pct >= 70:
                qual_desc = "God mottagning"
                status_str = "SYNKERAD"
                hb_type = "OK"
            elif quality_pct >= 40:
                qual_desc = "Acceptabel (enstaka paketfel)"
                status_str = "SYNKERAD"
                hb_type = "OK"
            else:
                qual_desc = "Svag signal / Prova justera Gain"
                status_str = "SVAG SIGNAL"
                hb_type = "LOW"

            groups_seen = sorted(list(_heartbeat_stats.get('groups_seen', set())))
            groups_display = ", ".join(groups_seen) if groups_seen else "-"

            station_str = ps if ps else "FM"
            pi_str = pi if pi else "0x0000"

            # Tydlig indikator för TMC-status baserat på mottagna RDS-grupper och validerad ALERT-C data
            has_8a_alarm = _heartbeat_stats.get('has_seen_tmc_8a', False)
            has_3a_tmc = _heartbeat_stats.get('has_seen_tmc_3a', False)
            clean_pi = str(pi if pi else "").upper().replace("0X", "").strip()
            station_u = str(ps if ps else "").upper()
            is_non_tmc_sr = clean_pi in ("E201", "E202") or any(x in station_u for x in ("P1", "P2"))

            if has_8a_alarm:
                tmc_status = "Aktiv (ALERT-C 8A-larm mottagna)"
            elif has_3a_tmc:
                if "8A" in groups_seen:
                    tmc_status = "Synkad (Grupp 3A aktiv, tar emot 8A-paket)"
                else:
                    tmc_status = "Synkad (Grupp 3A ALERT-C bekräftad, avvaktar 8A-larm)"
            elif "8A" in groups_seen:
                tmc_status = "Aktiv (Grupp 8A trafikdataström i luften)"
            elif is_non_tmc_sr:
                tmc_status = f"Ej TMC-sändare ({station_str} sänder ej TMC, välj SR P3/P4)"
            elif "3A" in groups_seen:
                tmc_status = "Ej TMC (Grupp 3A är RadioText+, ej ALERT-C)"
            else:
                tmc_status = "Söker handskakning (3A/8A ALERT-C)"
            print(
                f"RDS-HEARTBEAT: {hb_type} Station: {station_str} (PI: {pi_str}) | Frekvens: {freq_val} | "
                f"Status: {status_str} | Kvalitet: {quality_pct}% ({rate:.1f}/11.4 ramar/s - {qual_desc}) | "
                f"RDS-grupper: {groups_display} | "
                f"TMC: {tmc_status} | "
                f"Gain: {gain_display} | Senaste aktivitet: {time_since_last_frame:.1f}s sedan",
                flush=True
            )
        else:
            print(
                f"RDS-HEARTBEAT: LOST Ingen RDS-signal detekterad på {time_since_last_frame:.1f}s [Frekvens: {freq_val}] (Signalbortfall eller frekvens saknar RDS)",
                flush=True
            )

def start_heartbeat_monitor(interval=10.0, timeout=5.0, gain='auto', freq='103.3M'):
    """Startar bakgrundstråden för RDS-pulsövervakning."""
    global _heartbeat_thread_started
    with _heartbeat_lock:
        _heartbeat_stats['heartbeat_interval'] = float(interval)
        _heartbeat_stats['heartbeat_timeout'] = float(timeout)
        _heartbeat_stats['gain'] = str(gain) if gain else 'auto'
        if freq:
            _heartbeat_stats['freq'] = str(freq).strip()
        _heartbeat_stats['last_pulse_log_time'] = time.time()
        _heartbeat_stats['last_frame_time'] = time.time()
        if not _heartbeat_thread_started:
            t = threading.Thread(target=_heartbeat_worker, daemon=True)
            t.start()
            _heartbeat_thread_started = True

def _cleanup_on_exit():
    global _current_child_proc
    if _current_child_proc:
        try:
            _current_child_proc.kill()
        except Exception:
            pass

atexit.register(_cleanup_on_exit)

def _sig_handler(signum, frame):
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

# ALERT-C Händelsekoder (ISO 14819-2) översatta till svenska
ALERT_C_EVENTS = {
    1: "Trafikproblem / Störning",
    11: "Trafikstockning",
    12: "Mycket långsam trafik",
    13: "Köbildning",
    22: "Risk för tvärstopp",
    101: "Trafikolycka",
    102: "Allvarlig trafikolycka",
    103: "Flerbilsolycka",
    104: "Vält fordon på vägbanan",
    105: "Olycka med tung lastbil",
    106: "Olycka med buss",
    107: "Olycka med farligt gods",
    108: "Kollision med vilt",
    111: "Olycka i båda riktningar",
    201: "Stillastående kö",
    202: "Trafikkö",
    203: "Långsamtgående trafik",
    204: "Risk för köbildning",
    205: "Köer upplöses",
    206: "Lång kö med lång väntetid",
    301: "Vägarbete",
    302: "Långvarigt vägarbete",
    303: "Akut reparationsarbete på vägbanan",
    304: "Asfaltering / Beläggningsarbete",
    305: "Underhållsarbete längs vägen",
    306: "Belysningsarbete längs vägen",
    307: "Broarbete",
    401: "Väg helt avstängd i båda riktningar",
    402: "Körfält avstängt",
    403: "Ett körfält blockerat",
    404: "Flera körfält blockerade",
    405: "Avfart avstängd",
    406: "Påfart avstängd",
    407: "Bro avstängd",
    408: "Tunnel avstängd",
    409: "Vägen åter öppen efter tidigare hinder",
    410: "Körfält åter öppna",
    501: "Hinder på vägbanan",
    502: "Tappad last på vägen",
    503: "Havererat fordon på vägbanan",
    504: "Djur på vägen",
    505: "Personer på vägen",
    506: "Föremål på vägen",
    510: "Halt väglag / Risk för olyckor",
    601: "Utryckningsfordon på väg",
    602: "Räddningsarbete pågår på platsen",
    701: "Hastighetsbegränsning nedsatt",
    702: "Variabel hastighet aktiverad",
    703: "Rekommenderad lägre hastighet",
    801: "Halka / Risk för blixthalka",
    802: "Snömodd / Snöhinder",
    803: "Vattenplaning / Vattenmassor",
    804: "Kraftig vind / Stormbyar",
    805: "Tät dimma / Dålig sikt",
    806: "Kraftigt regn / Skyfall",
    807: "Snöstorm / Drivbildning",
    808: "Hård sidvind över bro",
    809: "Snöfall och nedsatt sikt",
    810: "Svår halka",
    811: "Underkylt regn / Farligt väglag",
    901: "Demonstration / Folksamling",
    902: "Större idrotts- eller folkevenemang",
    1001: "Broöppning",
    1002: "Färjestörning / Inställd färja",
    1003: "Tunnel stängd pga tekniskt fel",
    1004: "Signalhaveri / Trafikljus ur funktion",
    1005: "Spårhinder vid plankorsning",
    1006: "Översvämning på vägbanan",
    1007: "Träd fallit över vägbanan",
    1008: "Jordskred / Stenras över väg",
    1999: "Tidigare varning avblåst / Normal framkomlighet"
}

# Sveriges Platstabell (Location Table LTN 01 - Trafikverket)
# Primära vägar, trafikplatser och knutpunkter med WGS84-koordinater
SWEDEN_LTN01 = {
    # E4 Södergående / Norrgående
    14101: {"road": "E4", "name": "Essingeleden / Stora Essingen", "lat": 59.3218, "lon": 18.0054},
    14102: {"road": "E4", "name": "Fredhällstunneln Stockholm", "lat": 59.3289, "lon": 18.0125},
    14103: {"road": "E4", "name": "Eugeniatunneln / Norrtull", "lat": 59.3512, "lon": 18.0432},
    14110: {"road": "E4", "name": "Trafikplats Järva Krog / Solna", "lat": 59.3791, "lon": 18.0112},
    14120: {"road": "E4", "name": "Trafikplats Sollentuna (Avfart 171)", "lat": 59.4312, "lon": 17.9421},
    14130: {"road": "E4", "name": "Trafikplats Upplands Väsby", "lat": 59.5182, "lon": 17.9123},
    14150: {"road": "E4", "name": "Trafikplats Arlanda (Avfart 181)", "lat": 59.6489, "lon": 17.9298},
    14160: {"road": "E4", "name": "Trafikplats Knivsta", "lat": 59.7214, "lon": 17.8012},
    14170: {"road": "E4", "name": "Trafikplats Uppsala Södra", "lat": 59.8321, "lon": 17.6712},
    14180: {"road": "E4", "name": "Trafikplats Uppsala Norra", "lat": 59.8912, "lon": 17.6212},
    14201: {"road": "E4", "name": "Trafikplats Salem (Avfart 145)", "lat": 59.2145, "lon": 17.7562},
    14205: {"road": "E4", "name": "Trafikplats Moraberg / Södertälje", "lat": 59.2012, "lon": 17.6521},
    14208: {"road": "E4", "name": "Trafikplats Järna (Avfart 139)", "lat": 59.0831, "lon": 17.5672},
    14210: {"road": "E4", "name": "Trafikplats Vagnhärad / Trosa (Avfart 137)", "lat": 58.9567, "lon": 17.4891},
    14502: {"road": "E4", "name": "Trafikplats Nyköping Norra (Avfart 134)", "lat": 58.7612, "lon": 17.0211},
    14520: {"road": "E4", "name": "Norrköping Klockaretorpet (Avfart 119)", "lat": 58.5721, "lon": 16.1412},
    14540: {"road": "E4", "name": "Linköping Östra (Avfart 113)", "lat": 58.4112, "lon": 15.6812},
    14601: {"road": "E4", "name": "Jönköping Södra / Asecs", "lat": 57.7612, "lon": 14.1612},
    14701: {"road": "E4", "name": "Helsingborg Norra / Trafikplats Kropp", "lat": 56.0912, "lon": 12.7812},
    14300: {"road": "E4", "name": "Gävle Södra", "lat": 60.6512, "lon": 17.1321},
    14400: {"road": "E4", "name": "Sundsvall / Sundsvallsbron", "lat": 62.3912, "lon": 17.3312},

    # E20
    12101: {"road": "E20", "name": "Göteborg / Olskroken", "lat": 57.7121, "lon": 12.0012},
    12120: {"road": "E20", "name": "Alingsås Västra", "lat": 57.9251, "lon": 12.5121},
    12201: {"road": "E20", "name": "Örebro Gustavsvik", "lat": 59.2612, "lon": 15.1912},
    12250: {"road": "E20", "name": "Eskilstuna Väster", "lat": 59.3712, "lon": 16.4812},
    12280: {"road": "E20", "name": "Strängnäs Bresshammar", "lat": 59.3512, "lon": 17.0112},

    # E18
    13101: {"road": "E18", "name": "Västerås Rocklunda", "lat": 59.6212, "lon": 16.5312},
    13150: {"road": "E18", "name": "Enköping Romberga", "lat": 59.6412, "lon": 17.0712},
    13201: {"road": "E18", "name": "Karlstad Våxnäs", "lat": 59.3812, "lon": 13.4812},
    13250: {"road": "E18", "name": "Täby Kyrkby / Arninge", "lat": 59.4612, "lon": 18.1312},
    13280: {"road": "E18", "name": "Norrtälje Södra", "lat": 59.7412, "lon": 18.6812},

    # E6
    11101: {"road": "E6", "name": "Malmö / Trafikplats Sunnanå", "lat": 55.5812, "lon": 13.1012},
    11150: {"road": "E6", "name": "Hallandsås / Östra Karup", "lat": 56.4212, "lon": 12.9412},
    11180: {"road": "E6", "name": "Halmstad Norra", "lat": 56.6912, "lon": 12.8712},
    11201: {"road": "E6", "name": "Kungsbacka Nord", "lat": 57.5112, "lon": 12.0812},
    11250: {"road": "E6", "name": "Tingstadstunneln Göteborg", "lat": 57.7212, "lon": 11.9812},
    11301: {"road": "E6", "name": "Uddevalla Torp", "lat": 58.3512, "lon": 11.8112},
    11350: {"road": "E6", "name": "Svinesundsbron Gränsen", "lat": 59.0981, "lon": 11.2512},

    # E22
    17101: {"road": "E22", "name": "Lund Norra", "lat": 55.7212, "lon": 13.2212},
    17150: {"road": "E22", "name": "Kristianstad Härlöv", "lat": 56.0212, "lon": 14.1312},
    17200: {"road": "E22", "name": "Karlskrona Väst", "lat": 56.1912, "lon": 15.5812},
    17250: {"road": "E22", "name": "Kalmar Södra", "lat": 56.6612, "lon": 16.3312},

    # Riksvägar
    15101: {"road": "Riksväg 73", "name": "Handen / Jordbro", "lat": 59.1512, "lon": 18.1412},
    15102: {"road": "Riksväg 73", "name": "Nynäshamn / Älgviken", "lat": 58.9112, "lon": 17.9312},
    16101: {"road": "Riksväg 40", "name": "Borås Viared", "lat": 57.7012, "lon": 12.8412},
    16150: {"road": "Riksväg 40", "name": "Landvetter Flygplats", "lat": 57.6689, "lon": 12.2891}
}

def parse_freq_to_hz(freq_str):
    """Konverterar frekvenssträng till Hz heltal."""
    s = str(freq_str).strip().lower()
    if any(sep in s for sep in ('-', ',', ':', '..')):
        parts = re.split(r'[\-,:\.]+', s)
        parts = [p.strip() for p in parts if p.strip()]
        if parts:
            s = parts[0]

    if s.endswith('mhz'):
        s = s[:-3]
        multiplier = 1e6
    elif s.endswith('m'):
        s = s[:-1]
        multiplier = 1e6
    elif s.endswith('khz'):
        s = s[:-3]
        multiplier = 1e3
    elif s.endswith('k'):
        s = s[:-1]
        multiplier = 1e3
    else:
        multiplier = 1.0

    try:
        val = float(s) * multiplier
        if val < 1000.0:
            val *= 1e6
        return int(round(val))
    except (ValueError, TypeError):
        return 103300000

def parse_range_hz(freq_str):
    """Returnerar (min_hz, max_hz) om strängen är ett intervall som 87.5M-108M."""
    s = str(freq_str).strip().lower()
    if any(sep in s for sep in ('-', ':', '..')):
        parts = re.split(r'[\-:\.]+', s)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 2:
            h1 = parse_freq_to_hz(parts[0])
            h2 = parse_freq_to_hz(parts[1])
            if h1 and h2:
                return min(h1, h2), max(h1, h2)
    return 87500000, 108000000

def is_fm_scanning_range(freq_str):
    """Avgör om frekvenssträngen är ett skanningsintervall eller automatisk sökning."""
    if not freq_str:
        return True
    s = str(freq_str).strip().lower()
    if s in ("auto", "scan", "fm", "all"):
        return True
    if any(sep in s for sep in ("-", ",", ":", "..")):
        return True
    hz = parse_freq_to_hz(s)
    if not (87500000 <= hz <= 108000000):
        return True
    return False

def load_custom_location_table(filepath=None):
    """Loads external JSON location table if provided or found in workspace."""
    table = dict(SWEDEN_LTN01)
    target_path = filepath
    if not target_path:
        default_file = os.path.join(os.path.dirname(__file__), 'sweden_ltn01.json')
        if os.path.exists(default_file):
            target_path = default_file

    if target_path and os.path.exists(target_path):
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for k, v in data.items():
                    try:
                        table[int(k)] = v
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            print(f"Kunde inte läsa extern platstabell ({target_path}): {e}", file=sys.stderr)
    return table

_location_db = load_custom_location_table()

def lookup_location(loc_code):
    """Slår upp en platskod i Sveriges platstabell."""
    try:
        code_int = int(loc_code)
    except (ValueError, TypeError):
        return None
    return _location_db.get(code_int)

def translate_alert_c_event(event_code, fallback_desc=""):
    """Översätter ALERT-C händelsekod till svenska."""
    try:
        code_int = int(event_code)
        if code_int in ALERT_C_EVENTS:
            return ALERT_C_EVENTS[code_int]
    except (ValueError, TypeError):
        pass

    if fallback_desc:
        return fallback_desc
    return f"Trafikhändelse (kod {event_code})"

_last_locked_output = ""
_last_scan_output = ""
_last_reported_ps = ""
_last_reported_pi = ""
_channel_lock_printed = False
_current_channel_tmc_active = False
_current_channel_is_commercial = False
_current_channel_p4_confirmed = False
_group_3a_confirmed = False

def reset_station_state():
    """Nollställer stationsstatus och låsningsindikatorer inför ny frekvens."""
    global _last_reported_ps, _last_reported_pi, _channel_lock_printed, _last_locked_output, _last_scan_output
    global _current_channel_tmc_active, _current_channel_is_commercial, _current_channel_p4_confirmed, _group_3a_confirmed
    _last_reported_ps = ""
    _last_reported_pi = ""
    _channel_lock_printed = False
    _last_locked_output = ""
    _last_scan_output = ""
    _current_channel_tmc_active = False
    _current_channel_is_commercial = False
    _current_channel_p4_confirmed = False
    _group_3a_confirmed = False
    with _heartbeat_lock:
        _heartbeat_stats['groups_seen'] = set()
        _heartbeat_stats['has_seen_tmc_3a'] = False
        _heartbeat_stats['has_seen_tmc_8a'] = False
        _heartbeat_stats['has_received_any_frame'] = False
        _heartbeat_stats['frames_since_last_pulse'] = 0
        _heartbeat_stats['last_frame_time'] = time.time()

def format_and_print_lock(freq_str, status_msg):
    """Skriver ut låst frekvens för sdr_processor.py telemetri (deduplicerad)."""
    global _last_locked_output
    out_line = f"RDS-TMC: LOCK Freq: {freq_str} Status: LOCKED ({status_msg})"
    if out_line == _last_locked_output:
        return None
    _last_locked_output = out_line
    print(out_line, flush=True)
    return out_line

def format_and_print_scan(status_msg):
    """Skriver ut skanningsstatus (deduplicerad)."""
    global _last_scan_output
    out_line = f"RDS-TMC: SCAN Status: {status_msg}"
    if out_line == _last_scan_output:
        return None
    _last_scan_output = out_line
    print(out_line, flush=True)
    return out_line

def format_and_print_tmc(loc_code, road, name, lat, lon, extent, direction, urgency, duration, msg):
    """Skriver ut en formaterad RDS-TMC rad för sdr_processor.py."""
    parts = [
        "RDS-TMC:",
        f"LOC: {loc_code}",
        f"ROAD: {road}",
        f"NAME: {name}"
    ]
    if lat is not None and lon is not None:
        parts.append(f"LAT: {lat:.4f}")
        parts.append(f"LON: {lon:.4f}")
    if extent is not None:
        parts.append(f"EXTENT: {extent}")
    if direction:
        parts.append(f"DIR: {direction}")
    if urgency:
        parts.append(f"URGENCY: {urgency}")
    if duration:
        parts.append(f"DURATION: {duration}")
    parts.append(f"MSG: {msg}")

    out_line = " ".join(parts)
    print(out_line, flush=True)
    return out_line

class AlertCDecoder:
    """
    Inbyggd ALERT-C parser för ISO 14819-1 (Grupp 8A).
    Avkodar både single-group och multi-group meddelanden direkt från råa RDS-block (asHex)
    även om redsea ännu inte tagit emot Grupp 3A ODA handskakning.
    """
    def __init__(self):
        self._multi_parts = {}

    def decode_group(self, raw_data_val):
        if not raw_data_val:
            return None
        if isinstance(raw_data_val, list):
            blocks = [str(x).strip() for x in raw_data_val]
        elif isinstance(raw_data_val, str):
            blocks = raw_data_val.strip().split()
        else:
            return None
        if len(blocks) < 4:
            return None
        try:
            b1 = int(blocks[0], 16)
            b2 = int(blocks[1], 16)
            b3 = int(blocks[2], 16)
            b4 = int(blocks[3], 16)
        except (ValueError, TypeError):
            return None

        # Validera att Block 2 är Grupp 8A (bits 15-11 == 1000 0)
        group_num = (b2 >> 12) & 0xF
        group_ver = (b2 >> 11) & 0x1
        if group_num != 8 or group_ver != 0:
            return None

        # Bit 4: 0 = Användarmeddelande, 1 = Tuning info
        if (b2 >> 4) & 1:
            return None

        is_single = bool((b2 >> 3) & 1)
        if is_single:
            direction = "-" if ((b3 >> 14) & 1) else "+"
            extent = (b3 >> 11) & 0x7
            event_code = b3 & 0x7FF
            loc_code = b4
            return {
                "location": loc_code,
                "event_codes": [event_code],
                "extent": extent,
                "direction": direction,
                "urgency": "normal",
                "duration": ""
            }
        else:
            # Multi-group
            continuity_index = b2 & 0x7
            is_first = bool((b3 >> 15) & 1)
            if is_first:
                direction = "-" if ((b3 >> 14) & 1) else "+"
                extent = (b3 >> 11) & 0x7
                event_code = b3 & 0x7FF
                loc_code = b4
                msg_entry = {
                    "location": loc_code,
                    "event_codes": [event_code],
                    "extent": extent,
                    "direction": direction,
                    "urgency": "normal",
                    "duration": "",
                    "first_seen": time.time()
                }
                self._multi_parts[continuity_index] = msg_entry
                return msg_entry
            else:
                # Fortsättningsgrupp
                entry = self._multi_parts.get(continuity_index)
                if entry:
                    gsi = (b3 >> 12) & 0x3
                    if gsi == 0:
                        self._multi_parts.pop(continuity_index, None)
                    return None
        return None

_raw_alert_c_decoder = AlertCDecoder()

def is_sr_tmc_station(ps_str, pi_str):
    """Avgör om stationen är Sveriges Radio TMC-distributör (SR P3 eller SR P4)."""
    ps_u = str(ps_str or "").upper().strip()
    pi_clean = str(pi_str or "").upper().replace("0X", "").strip()

    if "P3" in ps_u or "P4" in ps_u or "SR" in ps_u:
        return True
    if pi_clean == "E203": # SR P3 (Rikstäckande RDS-TMC nät)
        return True
    # P4 distriktskoder (Sörmland: 0xEA24, Uppland: 0xE404, m.fl.)
    if any(pi_clean.startswith(pfx) for pfx in ("EA", "EB", "EC", "ED", "E4", "E204")):
        return True
    if pi_clean.startswith("E2") and not any(pi_clean == x for x in ("E201", "E202")):
        return True
    return False

def is_sr_p4_station(ps_str, pi_str):
    return is_sr_tmc_station(ps_str, pi_str)

def is_commercial_station(ps_str, pi_str):
    """Avgör om stationen är kommersiell radio som saknar RDS-TMC."""
    ps_u = str(ps_str or "").upper().strip()
    pi_clean = str(pi_str or "").upper().replace("0X", "").strip()

    if any(ch in ps_u for ch in ("RIX", "MIX", "NRJ", "STAR", "BANDIT", "VINYL", "ROCK", "RETRO", "LUGNA")):
        return True
    if pi_clean.startswith("E2") and len(pi_clean) >= 4 and pi_clean[2:4].isalnum():
        try:
            if int(pi_clean[2:4], 16) >= 0x40:
                return True
        except ValueError:
            pass
    return False

def format_and_print_rds(ps="", pi=""):
    """Skriver ut identifierad radiostation som telemetri (ej larm, strikt deduplicerad mot spam)."""
    global _last_reported_ps, _last_reported_pi, _channel_lock_printed, chosen_freq_global
    global _current_channel_p4_confirmed, _current_channel_tmc_active, _current_channel_is_commercial

    ps_str = str(ps or "").strip()
    pi_str = str(pi or "").upper().replace("0X", "").strip()

    has_new_info = False
    if ps_str and ps_str != _last_reported_ps:
        _last_reported_ps = ps_str
        has_new_info = True
    if pi_str and pi_str != _last_reported_pi:
        _last_reported_pi = pi_str
        has_new_info = True

    # Om ingen ny information mottagits, avbryt direkt för att förhindra logg-spam
    if not has_new_info:
        return None

    parts = ["RDS-INFO:"]
    if _last_reported_ps:
        parts.append(f"PS: {_last_reported_ps}")
    if _last_reported_pi:
        parts.append(f"PI: 0x{_last_reported_pi}")
    out_line = " ".join(parts)
    print(out_line, flush=True)

    if is_sr_tmc_station(_last_reported_ps, _last_reported_pi):
        _current_channel_p4_confirmed = True
        _current_channel_tmc_active = True
        stn_label = "SR P3" if ("P3" in (_last_reported_ps or "").upper() or _last_reported_pi == "E203") else "SR P4"
        stn_name = _last_reported_ps or stn_label
        format_and_print_lock(chosen_freq_global, f"Bekräftad Sveriges Radio TMC-kanal ({stn_name}, PI: 0x{_last_reported_pi or '0000'})")
    elif is_commercial_station(_last_reported_ps, _last_reported_pi):
        _current_channel_is_commercial = True
        format_and_print_scan(f"Station {_last_reported_ps or 'FM'} (PI: 0x{_last_reported_pi}) är en kommersiell station och sänder inte RDS-TMC.")
    elif _last_reported_pi in ("E201", "E202") or any(x in (_last_reported_ps or "").upper() for x in ("P1", "P2")):
        format_and_print_scan(f"Station {_last_reported_ps or 'SR'} (PI: 0x{_last_reported_pi}) sänder inte RDS-TMC (TMC sänds på SR P3 och SR P4).")

    return out_line

def parse_redsea_json_line(line_str):
    """Tolkar en JSON-rad från redsea och skriver ut formaterat meddelande."""
    line_str = line_str.strip()
    if not line_str or not (line_str.startswith('{') and line_str.endswith('}')):
        return None

    try:
        data = json.loads(line_str)
    except json.JSONDecodeError:
        return None

    # Registrera giltig mottagen RDS-ram/grupp i pulsmätaren
    pi_val = data.get("pi")
    ps_val = data.get("ps")
    group_type = str(data.get("group", "")).upper()
    record_rds_frame(pi=pi_val, ps=ps_val, group=group_type, count=1)

    # 1. Kontrollera Grupp 3A: Handskakning och Systeminformation (ALERT-C AID: 0xCD46/0xCD47, LTN: 1)
    raw_oda = data.get("oda") or data.get("open_data_app")
    oda_info = raw_oda if isinstance(raw_oda, dict) else {}
    raw_aid = data.get("aid") or oda_info.get("aid") or ""
    aid_str = str(raw_aid or "").upper().replace("0X", "").strip()
    if aid_str in ("NONE", "NULL"):
        aid_str = ""

    app_val = data.get("application") or oda_info.get("application") or oda_info.get("app_name") or ""
    app_str = str(app_val or "").upper()
    tmc_raw = data.get("tmc")
    tmc_dict = tmc_raw if isinstance(tmc_raw, dict) else {}
    has_system_info = isinstance(tmc_dict.get("system_info"), dict)

    # Strikt identifiering av äkta ALERT-C / TMC (inte vanlig RadioText+ eller andra ODA-appar)
    is_alert_c_tmc = (
        ("CD46" in aid_str and aid_str != "") or
        ("CD47" in aid_str and aid_str != "") or
        has_system_info or
        ("ALERT-C" in app_str) or
        ("TMC" in app_str and "RADIOTEXT" not in app_str) or
        (isinstance(raw_oda, dict) and any(x in str(oda_info).upper() for x in ("CD46", "CD47", "ALERT-C")))
    )

    is_group_3a = is_alert_c_tmc and (group_type == "3A" or bool(raw_oda) or has_system_info)

    if is_group_3a:
        global _group_3a_confirmed, _current_channel_tmc_active
        _current_channel_tmc_active = True
        with _heartbeat_lock:
            _heartbeat_stats['has_seen_tmc_3a'] = True

        ltn_num = (
            tmc_dict.get("system_info", {}).get("location_table") or
            data.get("ltn") or
            oda_info.get("ltn") or
            1
        )
        aid_disp = f"0x{aid_str}" if aid_str else "0xCD46"
        status_disp = "AKTIV"

        if not _group_3a_confirmed:
            _group_3a_confirmed = True
            # Logga vid INFO-nivå en gång när grupp 3A (TMC System Information) detekteras
            info_3a_line = f"INFO: [RDS-TMC] TMC SYNK (Grupp 3A) → AID: {aid_disp} | LTN: {ltn_num} (Sverige) | Systemstatus: {status_disp}"
            print(info_3a_line, flush=True)
            ecc_code = data.get("ecc") or oda_info.get("ecc") or "E1"
            info_line = f"RDS-INFO: TMC Handskakning (Grupp 3A): ALERT-C aktiv (AID: {aid_disp}, LTN: {ltn_num} Sverige, ECC: {ecc_code})"
            print(info_line, flush=True)
            format_and_print_lock(chosen_freq_global, f"Aktiv RDS-TMC sändare bekräftad (Grupp 3A, AID: {aid_disp}, LTN: {ltn_num})")

    # 2. Kontrollera Grupp 8A: ALERT-C Trafikmeddelanden
    tmc_root = tmc_dict if tmc_dict else data
    has_tmc_message = (
        (bool(tmc_dict) and ("message" in tmc_dict or "user_message" in tmc_dict)) or
        (bool(tmc_dict) and "location" in tmc_dict) or
        ("location" in data and ("event_codes" in data or "events" in data))
    )
    is_group_8a = (group_type == "8A") or has_tmc_message
    if is_group_8a:
        # Redsea kapslar in TMC-data inuti ett inre 'message'- eller 'user_message'-objekt
        if isinstance(tmc_root.get("message"), dict):
            tmc = tmc_root.get("message")
        elif isinstance(tmc_root.get("user_message"), dict):
            tmc = tmc_root.get("user_message")
        else:
            tmc = tmc_root

        # Extrahera numeriskt plats-ID från tmc, tmc_root eller rotnivån
        loc_code = tmc.get("location") if isinstance(tmc, dict) else None
        if loc_code is None and isinstance(tmc_root, dict):
            loc_code = tmc_root.get("location")
        if loc_code is None:
            loc_code = data.get("location")

        raw_parsed = None
        raw_data_val = data.get("raw_data")
        if loc_code is None and raw_data_val:
            raw_parsed = _raw_alert_c_decoder.decode_group(raw_data_val)
            if raw_parsed and raw_parsed.get("location") is not None:
                loc_code = raw_parsed["location"]

        if loc_code is not None:
            global _channel_lock_printed
            _current_channel_tmc_active = True
            with _heartbeat_lock:
                _heartbeat_stats['has_seen_tmc_8a'] = True
            if not _channel_lock_printed:
                _channel_lock_printed = True
                format_and_print_lock(chosen_freq_global, "Aktiv RDS-TMC trafikdataström bekräftad (Grupp 8A)")
            event_codes = []
            event_descs = []

            if raw_parsed:
                event_codes = raw_parsed.get("event_codes", [])
                extent = raw_parsed.get("extent", 0)
                direction = raw_parsed.get("direction", "+")
                urgency = raw_parsed.get("urgency", "normal")
                duration = raw_parsed.get("duration", "")
            else:
                # Stöd både redseas events-array med objekt och generiska listor
                raw_events = (tmc.get("events") if isinstance(tmc, dict) else None) or (tmc_root.get("events") if isinstance(tmc_root, dict) else None) or data.get("events") or []
                if isinstance(raw_events, list):
                    for ev in raw_events:
                        if isinstance(ev, dict):
                            ec = ev.get("event_code") or ev.get("code") or ev.get("event")
                            if ec is not None:
                                try: event_codes.append(int(ec))
                                except Exception: pass
                            desc = ev.get("description") or ev.get("event_description") or ev.get("text")
                            if desc:
                                event_descs.append(str(desc))
                        elif isinstance(ev, int):
                            event_codes.append(ev)
                        elif isinstance(ev, str) and ev.isdigit():
                            event_codes.append(int(ev))

                raw_ec = (tmc.get("event_codes") if isinstance(tmc, dict) else None) or (tmc_root.get("event_codes") if isinstance(tmc_root, dict) else None) or data.get("event_codes")
                if raw_ec:
                    if isinstance(raw_ec, list):
                        for ec in raw_ec:
                            try: event_codes.append(int(ec))
                            except Exception: pass
                    elif isinstance(raw_ec, int):
                        event_codes.append(raw_ec)

                raw_ed = (tmc.get("event_descriptions") if isinstance(tmc, dict) else None) or (tmc_root.get("event_descriptions") if isinstance(tmc_root, dict) else None) or data.get("event_descriptions")
                if raw_ed:
                    if isinstance(raw_ed, list):
                        event_descs.extend([str(x) for x in raw_ed if str(x)])
                    elif isinstance(raw_ed, str):
                        event_descs.append(raw_ed)

                direct_desc = (tmc.get("description") if isinstance(tmc, dict) else None) or (tmc_root.get("description") if isinstance(tmc_root, dict) else None) or data.get("description")
                if direct_desc and str(direct_desc) not in event_descs:
                    event_descs.append(str(direct_desc))

                extent = (tmc.get("extent") if isinstance(tmc, dict) else None) or (tmc_root.get("extent") if isinstance(tmc_root, dict) else None) or data.get("extent", 0)
                dir_raw = str((tmc.get("direction") if isinstance(tmc, dict) else None) or (tmc_root.get("direction") if isinstance(tmc_root, dict) else None) or data.get("direction", "+")).lower()
                direction = "-" if ("neg" in dir_raw or "-" in dir_raw) else "+"
                urgency = (tmc.get("urgency") if isinstance(tmc, dict) else None) or (tmc_root.get("urgency") if isinstance(tmc_root, dict) else None) or data.get("urgency", "normal")
                duration = (tmc.get("duration") if isinstance(tmc, dict) else None) or (tmc_root.get("duration") if isinstance(tmc_root, dict) else None) or data.get("duration", "")

            # Hämta händelsebeskrivning på svenska
            fallback_txt = event_descs[0] if event_descs else ""
            if event_codes:
                first_code = event_codes[0]
                event_swedish = translate_alert_c_event(first_code, fallback_txt)
            elif fallback_txt:
                event_swedish = fallback_txt
            else:
                event_swedish = "Trafikmeddelande"

            if fallback_txt and fallback_txt.lower() != event_swedish.lower():
                event_desc = f"{event_swedish} ({fallback_txt})"
            else:
                event_desc = event_swedish

            # Skapa ett strukturerat event/loggmeddelande när 8A tas emot:
            larm_log_line = (
                f"INFO: [RDS-TMC] LARM MOTTAGET → Plats-ID: {loc_code} | "
                f"Händelse: {event_desc} | Riktning: {direction} | "
                f"Omfattning: {extent} | Råkod: {event_codes}"
            )
            print(larm_log_line, flush=True)

            loc_info = lookup_location(loc_code)
            if loc_info:
                road = loc_info.get("road", "Väg")
                name = loc_info.get("name", f"Plats {loc_code}")
                lat = loc_info.get("lat")
                lon = loc_info.get("lon")
            else:
                road = "Väg"
                name = f"Platskod {loc_code}"
                lat = None
                lon = None

            return format_and_print_tmc(
                loc_code=loc_code,
                road=road,
                name=name,
                lat=lat,
                lon=lon,
                extent=extent,
                direction=direction,
                urgency=urgency,
                duration=duration,
                msg=event_desc
            )
        else:
            # Partiell 8A grupp (t.ex. pågående flerblocks-sekvens i luften)
            # Logga enbart om stationen faktiskt är bekräftad TMC-station (Grupp 3A aktiv)
            if _group_3a_confirmed:
                global _last_raw_8a_log
                now = time.time()
                if '_last_raw_8a_log' not in globals() or now - _last_raw_8a_log > 15.0:
                    _last_raw_8a_log = now
                    print("INFO: [RDS-TMC] ALERT-C Grupp 8A block mottaget (Inväntar komplett sekvens)", flush=True)

    # 3. Kontrollera vanlig RDS-metadata (PS / PI)
    # RadioText (låttitlar/artister/reklam) ignoreras helt för att undvika spam.
    # Endast stationsnamn (PS) och PI rapporteras en gång som stations-telemetri.
    raw_ps = data.get("ps")
    ps = str(raw_ps).strip() if raw_ps is not None else ""
    raw_pi = data.get("pi")
    pi = str(raw_pi).strip() if raw_pi is not None else ""

    if ps or pi:
        return format_and_print_rds(ps=ps, pi=pi)

    return None

chosen_freq_global = "103.3M"

SR_TMC_STATIONS = [
    ("88.7M",   88700000, "SR P4 Sörmland (Nyköping / Kisa slavsändare)"),
    ("100.1M", 100100000, "SR P4 Sörmland (60 kW)"),
    ("99.3M",   99300000, "SR P3 Trafik / Riks (Stockholm Nacka & Kisa 60 kW)"),
    ("103.3M", 103300000, "SR P4 Stockholm / Västerbotten (Nacka 60 kW)"),
    ("93.8M",   93800000, "SR P4 Södertälje"),
    ("102.5M", 102500000, "SR P4 Uppland (Uppsala 60 kW)"),
    ("96.6M",   96600000, "SR P3 Uppsala (20 kW)"),
    ("94.8M",   94800000, "SR P3 Norrköping (60 kW)"),
    ("99.8M",   99800000, "SR P4 Östergötland"),
    ("102.2M", 102200000, "SR P4 Östergötland"),
    ("100.5M", 100500000, "SR P4 Västmanland / Norrbotten"),
    ("102.8M", 102800000, "SR P4 Örebro / Västernorrland"),
    ("99.4M",   99400000, "SR P3 Göteborg (60 kW)"),
    ("101.9M", 101900000, "SR P4 Göteborg (60 kW)"),
    ("97.0M",   97000000, "SR P3 Skåne / Hörby (60 kW)"),
    ("102.0M", 102000000, "SR P4 Malmöhus / Gävleborg"),
    ("87.9M",   87900000, "SR P4 Malmöhus"),
    ("101.3M", 101300000, "SR P4 Dalarna / Halland"),
    ("103.8M", 103800000, "SR P4 Halland"),
    ("100.8M", 100800000, "SR P4 Jönköping"),
    ("101.0M", 101000000, "SR P4 Kronoberg"),
    ("100.2M", 100200000, "SR P4 Kalmar / Gotland"),
    ("100.4M", 100400000, "SR P4 Blekinge / Jämtland"),
    ("101.4M", 101400000, "SR P4 Kristianstad"),
    ("100.3M", 100300000, "SR P4 Skaraborg"),
    ("100.0M", 100000000, "SR P4 Värmland"),
    ("104.2M", 104200000, "SR P4 Västerbotten"),
    ("102.9M", 102900000, "SR P4 Norrbotten")
]
P4_STATIONS = SR_TMC_STATIONS

def get_p4_candidates(freq_arg, device="", min_hz=87500000, max_hz=108000000):
    """
    Returnerar en prioriterad lista över kandidatfrekvenser att prova för RDS-TMC.
    Om användaren har ställt in en fast frekvens (inte auto/scan/intervall) gäller
    denna strikt utan att söka vidare till andra frekvenser.
    Vid skanningsläge genereras kända SR-stationer följt av fullständig stegvis
    genomsökning av hela FM-bandet (200 kHz raster).
    """
    is_scan = is_fm_scanning_range(freq_arg)
    if not is_scan:
        target_hz = parse_freq_to_hz(freq_arg)
        return [(str(freq_arg).strip(), target_hz, f"Fast frekvens {freq_arg}")]

    min_hz, max_hz = parse_range_hz(freq_arg)

    # 1. Kända primära SR P3 och P4 sändare i det angivna intervallet
    known_cands = [c for c in SR_TMC_STATIONS if min_hz <= c[1] <= max_hz]
    known_freqs_set = {c[1] for c in known_cands}

    # 2. Utöka med hela FM-bandet (200 kHz steg) för att fånga alla lokala repeatrar och slavsändare
    all_cands = list(known_cands)
    curr = min_hz
    while curr <= max_hz:
        curr_round = int(round(curr / 100000.0) * 100000)
        if curr_round not in known_freqs_set:
            f_mhz = curr_round / 1e6
            all_cands.append((f"{f_mhz:.1f}M", curr_round, f"FM {f_mhz:.1f} MHz"))
            known_freqs_set.add(curr_round)
        curr += 200000

    # Försök RF-effektsortera kandidater om rtl_power finns
    import shutil
    if shutil.which("rtl_power"):
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tf:
                tmp_csv = tf.name

            p_cmd = ["rtl_power", "-f", f"{min_hz/1e6:.1f}M:{max_hz/1e6:.1f}M:200k", "-i", "1", "-e", "1s"]
            if device: p_cmd.extend(["-d", device])
            p_cmd.append(tmp_csv)

            res = subprocess.run(p_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.5)
            if res.returncode == 0 and os.path.exists(tmp_csv):
                cand_powers = {}
                with open(tmp_csv, 'r') as f:
                    for r in f:
                        parts = [p.strip() for p in r.split(',')]
                        if len(parts) >= 7:
                            try:
                                f_low = float(parts[2])
                                f_step = float(parts[4])
                                db_vals = [float(x) for x in parts[6:] if x]
                                for idx, db in enumerate(db_vals):
                                    freq_pt = f_low + idx * f_step
                                    for cand in all_cands:
                                        if abs(freq_pt - cand[1]) <= 120000:
                                            if cand[0] not in cand_powers or db > cand_powers[cand[0]]:
                                                cand_powers[cand[0]] = db
                            except Exception:
                                pass
                try: os.remove(tmp_csv)
                except Exception: pass

                if cand_powers:
                    sorted_cands = sorted(all_cands, key=lambda c: cand_powers.get(c[0], -999.0), reverse=True)
                    best_f = sorted_cands[0]
                    format_and_print_scan(f"RF-spektrum identifierade starkaste FM-frekvens: {best_f[0]} ({best_f[2]}, {cand_powers.get(best_f[0], 0):.1f} dB)")
                    return sorted_cands
        except Exception:
            pass

    return all_cands

def run_rds_session(freq_str, device="", gain="auto", ppm="0", dwell_timeout=10.0, is_scan=True):
    """
    Kör rtl_fm | redsea på angiven frekvens.
    - Vid fast frekvens (is_scan=False): Låser strikt på frekvensen och stannar kvar oavsett timeout eller signal.
    - Vid skanningsläge (is_scan=True):
      - Avbryter omedelbart om en kommersiell station utan TMC detekteras.
      - Avbryter om ingen RDS-TMC detekteras inom dwell_timeout sekunder.
      - Låser och förblir aktiv så länge mottagningen har aktiv TMC-synk.
    """
    global _current_child_proc, chosen_freq_global
    chosen_freq_global = freq_str
    reset_station_state()
    with _heartbeat_lock:
        _heartbeat_stats['freq'] = str(freq_str)
        if gain:
            _heartbeat_stats['gain'] = str(gain)

    rtl_cmd = ["rtl_fm", "-M", "fm", "-s", "171k", "-r", "171k", "-f", freq_str]
    if device:
        rtl_cmd.extend(["-d", device])
    if gain and gain != "auto":
        rtl_cmd.extend(["-g", str(gain)])
    if ppm and ppm != "0":
        rtl_cmd.extend(["-p", str(ppm)])
    rtl_cmd.append("-")

    # Kör redsea i europeiskt RDS-läge (-r 171k)
    redsea_cmd = ["redsea", "-r", "171k"]

    line_queue = queue.Queue()
    reader_stop = threading.Event()
    p1 = None
    p2 = None

    try:
        p1 = subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(redsea_cmd, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        p1.stdout.close()
        _current_child_proc = p2

        def stdout_reader():
            try:
                for line in iter(p2.stdout.readline, ''):
                    if reader_stop.is_set() or _shutdown_requested:
                        break
                    if line:
                        line_queue.put(line)
            except Exception:
                pass

        reader_t = threading.Thread(target=stdout_reader, daemon=True)
        reader_t.start()

        start_time = time.time()
        is_locked = False

        while not _shutdown_requested:
            try:
                line = line_queue.get(timeout=0.3)
                try:
                    parse_redsea_json_line(line)
                except Exception as parse_err:
                    print(f"DEBUG: [RDS-TMC] Fel vid JSON-parsning: {parse_err}", file=sys.stderr, flush=True)
            except queue.Empty:
                pass

            if p2.poll() is not None or (p1 and p1.poll() is not None):
                break

            # 1. Kontrollera om aktiv RDS-TMC (Grupp 3A eller 8A) bekräftats på denna frekvens
            if _current_channel_tmc_active:
                if not is_locked:
                    is_locked = True
                
                # Om låst och i skanningsläge: övervaka om signalen varit borta i mer än 30s
                if is_scan:
                    with _heartbeat_lock:
                        lost_for = time.time() - _heartbeat_stats['last_frame_time']
                    if lost_for > 30.0 and _heartbeat_stats['has_received_any_frame']:
                        format_and_print_scan(f"RDS-signal förlorad på {freq_str} i {lost_for:.1f}s. Återupptar frekvenssökning...")
                        break
                continue

            # 2. Bekräftad Sveriges Radio TMC-kanal (SR P3 eller SR P4):
            # SR P3 distribuerar det nationella TMC-nätet och SR P4 regional TMC.
            # När mottagaren identifierat stationen via PI/PS och tar emot giltiga RDS-ramar låser vi direkt!
            if is_scan and _current_channel_p4_confirmed and not is_locked:
                with _heartbeat_lock:
                    has_frames = _heartbeat_stats.get('has_received_any_frame', False)
                if has_frames:
                    is_locked = True
                    _current_channel_tmc_active = True
                    stn_name = _last_reported_ps or "SR P3/P4"
                    format_and_print_lock(chosen_freq_global, f"Bekräftad Sveriges Radio TMC-kanal ({stn_name}, PI: 0x{_last_reported_pi or '0000'})")
                    continue

            # 3. Kontrollera om stationen är kommersiell (endast vid skanningsläge)
            if is_scan and _current_channel_is_commercial:
                format_and_print_scan(f"Frekvens {freq_str} sänder kommersiell radio utan RDS-TMC ({_last_reported_ps or 'FM'}). Söker vidare...")
                return False

            # 4. Snabbavbrott på 2.5s om ingen RDS-signal alls detekteras (tom bärvåg/brus)
            elapsed = time.time() - start_time
            if is_scan and not is_locked and elapsed > 2.5:
                with _heartbeat_lock:
                    has_frames = _heartbeat_stats.get('has_received_any_frame', False)
                if not has_frames:
                    format_and_print_scan(f"Ingen RDS-signal detekterad på {freq_str} inom 2.5s. Söker vidare...")
                    return False

            # 5. Tidsgräns vid okänd signal som sänder RDS men inte identifierats som SR P3/P4
            if is_scan and not is_locked and elapsed > dwell_timeout:
                format_and_print_scan(f"Ingen bekräftad SR TMC-station på {freq_str} inom {int(dwell_timeout)}s. Söker vidare...")
                return False

        return is_locked
    finally:
        reader_stop.set()
        if p2:
            try:
                p2.kill()
                p2.wait(timeout=0.4)
            except Exception:
                pass
        if p1:
            try:
                p1.kill()
                p1.wait(timeout=0.4)
            except Exception:
                pass
        _current_child_proc = None
        time.sleep(0.3)

def run_test_feed(freq="103.3M"):
    """Genererar syntetiska RDS och TMC-händelser för testning och demonstration."""
    print(f"RDS-TMC Decoder: Testflöde aktivt på {freq} (Genererar ALERT-C trafikmeddelanden)...", file=sys.stderr, flush=True)
    format_and_print_lock(freq, "Testflöde / Simulering aktiv")
    format_and_print_rds(ps="SR P4", pi="0xE204")
    record_rds_frame(pi="0xE204", ps="SR P4", count=1)
    time.sleep(1.0)

    sample_events = [
        (14210, 101, "urgent", "1-2h", 1, "+"),   # Vagnhärad E4, Trafikolycka
        (14101, 201, "urgent", "30m-1h", 2, "+"), # Essingeleden E4, Stillastående kö
        (12201, 301, "normal", "Idag", 0, "+"),   # Örebro E20, Vägarbete
        (14150, 801, "urgent", "2-4h", 1, "-"),   # Arlanda E4, Risk för blixthalka
        (11250, 402, "urgent", "1-2h", 1, "+"),   # Tingstadstunneln E6, Körfält avstängt
        (13101, 501, "urgent", "30m", 0, "+"),    # Västerås E18, Hinder på vägen
        (15101, 202, "normal", "1h", 1, "+")      # Handen Riksväg 73, Trafikkö
    ]

    idx = 0
    while not _shutdown_requested:
        # Simulera kontinuerlig mottagen RDS-puls (t.ex. ~11.2 ramar/sekund över 4 sekunder = 45 ramar)
        record_rds_frame(pi="0xE204", ps="SR P4", count=45)
        loc_code, ev_code, urgency, duration, extent, dir_val = sample_events[idx % len(sample_events)]
        loc_info = lookup_location(loc_code)
        ev_text = translate_alert_c_event(ev_code)
        road = loc_info.get("road", "Väg")
        name = loc_info.get("name", f"Plats {loc_code}")
        lat = loc_info.get("lat")
        lon = loc_info.get("lon")

        format_and_print_tmc(
            loc_code=loc_code,
            road=road,
            name=name,
            lat=lat,
            lon=lon,
            extent=extent,
            direction=dir_val,
            urgency=urgency,
            duration=duration,
            msg=ev_text
        )
        idx += 1
        time.sleep(4.0)

def run_test_tmc(save_db=False):
    """Injicerar syntetiska Grupp 3A och 8A JSON-meddelanden direkt i parse_redsea_json_line."""
    print("RDS-TMC: Startar syntetiskt testläge (--test-tmc)...", flush=True)
    
    # 1. Injicera Grupp 3A (Handskakning och ODA System Information)
    sample_3a = {
        "group": "3A",
        "pi": "0xEA24",
        "ps": "P4 Sörml",
        "oda": {
            "aid": "CD46",
            "application": "TMC",
            "ltn": 1
        }
    }
    print("[TEST] Injicerar Grupp 3A (TMC System Information)...", flush=True)
    parse_redsea_json_line(json.dumps(sample_3a))

    # 2. Injicera Grupp 8A (ALERT-C Trafikmeddelande)
    sample_8a = {
        "group": "8A",
        "pi": "0xEA24",
        "ps": "P4 Sörml",
        "tmc": {
            "event_codes": [101],
            "event_descriptions": ["Stationary traffic for 2 km"],
            "extent": 1,
            "direction": "+",
            "location": 14502,
            "urgency": "urgent",
            "duration": "1-2 hours"
        }
    }
    print("[TEST] Injicerar Grupp 8A (ALERT-C Trafikmeddelande)...", flush=True)
    res_8a = parse_redsea_json_line(json.dumps(sample_8a))

    if save_db:
        try:
            # 1. Prova först att anropa webbserverns interna REST API så att webbläsare meddelas i realtid via SSE
            import urllib.request
            try:
                req = urllib.request.Request("http://127.0.0.1:5000/api/test/tmc", data=b"{}", headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        print("[TEST] Larmet har skickats till applikationen och aktiverats i realtidsflödet!", flush=True)
                        print("RDS-TMC: Testläge slutfört framgångsrikt.", flush=True)
                        return res_8a
            except Exception:
                pass

            # 2. Fallback: spara direkt i SQLite databasfilen om webbservern inte svarar på port 5000
            from database import save_message, init_db, DB_PATH
            import os
            db_dir = os.path.dirname(DB_PATH)
            if os.path.exists(db_dir):
                init_db()
                save_message(
                    address="E4:14502",
                    message="Trafikolycka (Stationary traffic for 2 km) (Trafikplats Nyköping Norra (Avfart 134)) | Lat: 58.7612, Lon: 17.0211",
                    alias="Trafikplats Nyköping Norra (Avfart 134)",
                    function_code=3,
                    bitrate="RDS-TMC",
                    frequency="103.3M"
                )
                print("[TEST] Larmet har sparats i databasen messages.db (ladda om sidan i webbläsaren för att se det)!", flush=True)
            else:
                print(f"[TEST] Databasmapp hittades inte: {db_dir}", flush=True)
        except Exception as e:
            print(f"[TEST] Kunde inte spara i databas: {e}", flush=True)

    print("RDS-TMC: Testläge slutfört framgångsrikt.", flush=True)
    return res_8a

def main():
    parser = argparse.ArgumentParser(description="PagerMonitor RDS / RDS-TMC (ALERT-C) Decoder")
    parser.add_argument("--freq", default="103.3M", help="FM frequency (e.g. 103.3M, 87.5M-108M, or auto)")
    parser.add_argument("--device", default="", help="RTL-SDR device serial or index")
    parser.add_argument("--gain", default="auto", help="Tuner gain in dB or auto")
    parser.add_argument("--ppm", default="0", help="PPM error correction")
    parser.add_argument("--test-feed", action="store_true", help="Run synthetic test feed")
    parser.add_argument("--test-tmc", action="store_true", help="Kör syntetisk TMC-injektion (Grupp 3A och Grupp 8A) utan hårdvara")
    parser.add_argument("--save-db", action="store_true", help="Spara syntetiskt testlarm i applikationens databas (messages.db)")
    parser.add_argument("--stdin", action="store_true", help="Read redsea JSON stream from standard input")
    parser.add_argument("--heartbeat-interval", type=float, default=10.0, help="Intervall i sekunder mellan pulskontroller (default: 10.0)")
    parser.add_argument("--heartbeat-timeout", type=float, default=5.0, help="Tidsgräns i sekunder innan puls anses förlorad (default: 5.0)")
    args = parser.parse_args()

    if args.test_tmc:
        run_test_tmc(save_db=args.save_db)
        return

    # Starta bakgrundstråd för realtidspuls
    start_heartbeat_monitor(interval=args.heartbeat_interval, timeout=args.heartbeat_timeout, gain=args.gain, freq=args.freq)

    # Om stdin skickas explicit via flagga --stdin
    if args.stdin:
        try:
            for line in sys.stdin:
                if _shutdown_requested:
                    break
                parse_redsea_json_line(line)
        except (KeyboardInterrupt, SystemExit):
            pass
        return

    if args.test_feed:
        run_test_feed(args.freq)
        return

    # Kontrollera om verktygen rtl_fm och redsea finns tillgängliga
    import shutil
    has_rtl_fm = bool(shutil.which("rtl_fm"))
    has_redsea = bool(shutil.which("redsea"))

    if not (has_rtl_fm and has_redsea):
        print(f"Hårdvaruverktyg saknas (rtl_fm={has_rtl_fm}, redsea={has_redsea}). Kör i simulerat läge.", file=sys.stderr, flush=True)
        run_test_feed(args.freq)
        return

    is_scan = is_fm_scanning_range(args.freq)

    if not is_scan:
        format_and_print_lock(args.freq, f"Mottagare låst på fast inställd frekvens {args.freq} (Skanning inaktiv)")
        while not _shutdown_requested:
            try:
                run_rds_session(args.freq, device=args.device, gain=args.gain, ppm=args.ppm, dwell_timeout=0, is_scan=False)
            except Exception as e:
                import traceback
                print(f"DEBUG: [RDS-TMC] Fel vid fast frekvens {args.freq}: {e}", file=sys.stderr, flush=True)
                traceback.print_exc()
            if _shutdown_requested:
                break
            time.sleep(1.0)
        return

    # Skapa lista med kandidatfrekvenser för automatisk sökning / skanning
    candidates = get_p4_candidates(args.freq, device=args.device)
    candidate_idx = 0

    format_and_print_scan(f"Startar RDS-TMC skanningsmotor ({len(candidates)} kandidatstationer i sökkön).")

    while not _shutdown_requested:
        cand = candidates[candidate_idx % len(candidates)]
        cand_freq = cand[0]
        cand_name = cand[2] if len(cand) > 2 else "SR P4"

        format_and_print_scan(f"Avlyssnar frekvens {cand_freq} ({cand_name}). Kontrollerar RDS-TMC aktivitet...")
        
        # Kör session med 10 sekunders dwell-timeout för att bekräfta TMC
        try:
            locked = run_rds_session(cand_freq, device=args.device, gain=args.gain, ppm=args.ppm, dwell_timeout=10.0, is_scan=True)
        except Exception as sess_err:
            print(f"DEBUG: [RDS-TMC] Fel under session på {cand_freq}: {sess_err}", file=sys.stderr, flush=True)
        
        if _shutdown_requested:
            break
            
        candidate_idx += 1
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except Exception as fatal_e:
        import traceback
        print(f"FATAL: [RDS-DECODER] Ohanterat fel: {fatal_e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        time.sleep(2.0)
        sys.exit(1)
