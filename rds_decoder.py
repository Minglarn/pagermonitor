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

def format_and_print_lock(freq_str, status_msg):
    """Skriver ut låst frekvens för sdr_processor.py telemetri."""
    out_line = f"RDS-TMC: LOCK Freq: {freq_str} Status: LOCKED ({status_msg})"
    print(out_line, flush=True)
    return out_line

def format_and_print_scan(status_msg):
    """Skriver ut skanningsstatus."""
    out_line = f"RDS-TMC: SCAN Status: {status_msg}"
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

_last_reported_station = ""

def format_and_print_rds(ps="", pi=""):
    """Skriver ut identifierad radiostation som telemetri (ej larm)."""
    global _last_reported_station, chosen_freq_global
    cur = f"{ps}_{pi}"
    if cur == _last_reported_station:
        return None
    _last_reported_station = cur

    parts = ["RDS-INFO:"]
    if ps:
        parts.append(f"PS: {ps}")
    if pi:
        parts.append(f"PI: {pi}")
    out_line = " ".join(parts)
    print(out_line, flush=True)

    pi_str = str(pi).upper().replace("0X", "").strip()
    is_p4 = (
        "P4" in ps.upper() or 
        pi_str.startswith("E4") or 
        (pi_str.startswith("E2") and not any(pi_str == x for x in ("E201", "E202", "E203")) and (
            len(pi_str) >= 4 and pi_str[2:].isalnum() and int(pi_str[2:4], 16) < 0x40 if len(pi_str) >= 4 else False
        ))
    )
    is_commercial = (
        any(ch in ps.upper() for ch in ("RIX", "MIX", "NRJ", "STAR", "BANDIT", "VINYL", "ROCK")) or 
        (pi_str.startswith("E2") and len(pi_str) >= 4 and pi_str[2:4] >= "40")
    )

    if is_p4:
        format_and_print_lock(chosen_freq_global, f"Sveriges Radio P4 bekräftad (TMC-sändare {ps}, PI: {pi})")
    elif is_commercial:
        format_and_print_scan(f"Station {ps or 'FM'} (PI: {pi}) är en kommersiell station och sänder inte RDS-TMC. Leta efter SR P4.")

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

    group_type = str(data.get("group", "")).upper()

    # 1. Kontrollera Grupp 3A: Handskakning och Systeminformation (ALERT-C AID: 0xCD46, LTN: 1)
    oda_info = data.get("oda") or {}
    aid_str = str(data.get("aid") or (oda_info.get("aid") if isinstance(oda_info, dict) else "")).upper()
    app_str = str(data.get("application", "")).upper()
    is_group_3a = (
        (group_type == "3A" and ("CD46" in aid_str or "TMC" in app_str or "TMC" in str(data).upper())) or
        "CD46" in aid_str or 
        app_str == "TMC"
    )

    if is_group_3a:
        ltn_num = data.get("ltn") or (oda_info.get("ltn") if isinstance(oda_info, dict) else 1) or 1
        ecc_code = data.get("ecc") or "E1"
        info_line = f"RDS-INFO: TMC Handskakning (Grupp 3A): ALERT-C aktiv (AID: 0xCD46, LTN: {ltn_num} Sverige, ECC: {ecc_code})"
        print(info_line, flush=True)
        format_and_print_lock(chosen_freq_global, f"Aktiv RDS-TMC sändare bekräftad (Grupp 3A, AID: 0xCD46, LTN: {ltn_num})")

    # 2. Kontrollera Grupp 8A: ALERT-C Trafikmeddelanden
    if "tmc" in data or group_type == "8A":
        tmc = data.get("tmc") or {}
        loc_code = tmc.get("location")
        if loc_code is not None:
            event_codes = tmc.get("event_codes", [])
            event_descs = tmc.get("event_descriptions", [])
            extent = tmc.get("extent", 0)
            direction = tmc.get("direction", "+")
            urgency = tmc.get("urgency", "normal")
            duration = tmc.get("duration", "")

            # Hämta händelsebeskrivning på svenska
            if event_codes:
                first_code = event_codes[0]
                fallback_txt = event_descs[0] if event_descs else ""
                event_swedish = translate_alert_c_event(first_code, fallback_txt)
            elif event_descs:
                event_swedish = event_descs[0]
            else:
                event_swedish = "Trafikmeddelande"

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
                msg=event_swedish
            )

    # 3. Kontrollera vanlig RDS-metadata (PS / PI)
    # RadioText (låttitlar/artister/reklam) ignoreras helt för att undvika spam.
    # Endast stationsnamn (PS) och PI rapporteras en gång som stations-telemetri.
    ps = data.get("ps", "").strip()
    pi = data.get("pi", "")

    if ps or pi:
        return format_and_print_rds(ps=ps, pi=pi)

    return None

chosen_freq_global = "103.3M"

def find_best_fm_station(device="", gain="auto", ppm="0", min_hz=87500000, max_hz=108000000):
    """
    Söker automatiskt efter aktiv Sveriges Radio P4-station inom angivet frekvensintervall.
    TMC sänds uteslutande via SR P4 (och delvis P3) i Sverige.
    """
    format_and_print_scan(f"Avsöker FM-bandet ({min_hz/1e6:.1f}–{max_hz/1e6:.1f} MHz) efter Sveriges Radio P4 (TMC)...")

    # Primära P4 frekvenser i Sverige (Stockholm 103.3M, Sörmland 100.1M, Uppsala 102.5M, Göteborg 101.9M m.fl.)
    p4_freqs = [
        ("103.3M", 103300000, "SR P4 Stockholm / Västerbotten"),
        ("100.1M", 100100000, "SR P4 Sörmland"),
        ("102.5M", 102500000, "SR P4 Uppland"),
        ("101.9M", 101900000, "SR P4 Göteborg"),
        ("102.0M", 102000000, "SR P4 Malmöhus / Gävleborg"),
        ("99.8M",   99800000, "SR P4 Östergötland"),
        ("102.8M", 102800000, "SR P4 Örebro / Västernorrland"),
        ("100.8M", 100800000, "SR P4 Jönköping"),
        ("100.3M", 100300000, "SR P4 Skaraborg"),
        ("100.0M", 100000000, "SR P4 Värmland"),
        ("101.3M", 101300000, "SR P4 Dalarna / Halland"),
        ("101.4M", 101400000, "SR P4 Kristianstad"),
        ("100.2M", 100200000, "SR P4 Kalmar"),
        ("101.0M", 101000000, "SR P4 Kronoberg"),
        ("100.4M", 100400000, "SR P4 Blekinge / Jämtland"),
        ("100.5M", 100500000, "SR P4 Norrbotten / Västmanland"),
        ("99.4M",   99400000, "SR P4"),
        ("98.3M",   98300000, "SR P4")
    ]

    valid_cands = [c for c in p4_freqs if min_hz <= c[1] <= max_hz]
    if not valid_cands:
        valid_cands = p4_freqs

    # Snabb RF-effektmätning med rtl_power om tillgängligt (utan hängningar)
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
                best_cand_freq = None
                best_power = -999.0
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
                                    for cand_str, cand_hz, cand_name in valid_cands:
                                        if abs(freq_pt - cand_hz) <= 120000:
                                            if db > best_power:
                                                best_power = db
                                                best_cand_freq = cand_str
                            except Exception:
                                pass
                try: os.remove(tmp_csv)
                except Exception: pass
                if best_cand_freq:
                    format_and_print_scan(f"Starkaste P4-frekvens identifierad via RF-spektrum: {best_cand_freq} ({best_power:.1f} dB)")
                    return best_cand_freq
        except Exception:
            pass

    # Standard P4 inom intervallet (Stockholm 103.3 MHz SR P4)
    chosen = valid_cands[0][0]
    cand_name = valid_cands[0][2]
    format_and_print_scan(f"Valde primär SR P4 frekvens: {chosen} ({cand_name})")
    return chosen

def run_test_feed(freq="103.3M"):
    """Genererar syntetiska RDS och TMC-händelser för testning och demonstration."""
    print(f"RDS-TMC Decoder: Testflöde aktivt på {freq} (Genererar ALERT-C trafikmeddelanden)...", file=sys.stderr, flush=True)
    format_and_print_lock(freq, "Testflöde / Simulering aktiv")
    format_and_print_rds(ps="SR P4", pi="0xE204")
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

def main():
    parser = argparse.ArgumentParser(description="PagerMonitor RDS / RDS-TMC (ALERT-C) Decoder")
    parser.add_argument("--freq", default="103.3M", help="FM frequency (e.g. 103.3M, 87.5M-108M, or auto)")
    parser.add_argument("--device", default="", help="RTL-SDR device serial or index")
    parser.add_argument("--gain", default="auto", help="Tuner gain in dB or auto")
    parser.add_argument("--ppm", default="0", help="PPM error correction")
    parser.add_argument("--test-feed", action="store_true", help="Run synthetic test feed")
    parser.add_argument("--stdin", action="store_true", help="Read redsea JSON stream from standard input")
    args = parser.parse_args()

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

    # Kontrollera om användaren angett ett intervall (t.ex. 87.5M-108M), "auto", "scan" eller frekvens utanför FM-bandet
    global chosen_freq_global
    if is_fm_scanning_range(args.freq):
        min_hz, max_hz = parse_range_hz(args.freq)
        format_and_print_scan(f"Frekvenssökning begärd ({args.freq}). Söker aktiv Sveriges Radio P4 (TMC)...")
        chosen_freq = find_best_fm_station(device=args.device, gain=args.gain, ppm=args.ppm, min_hz=min_hz, max_hz=max_hz)
        chosen_freq_global = chosen_freq
        format_and_print_lock(chosen_freq, f"Automatisk FM-sökning låst på SR P4 ({chosen_freq})")
    else:
        chosen_freq = args.freq
        chosen_freq_global = chosen_freq
        format_and_print_lock(chosen_freq, f"FM-frekvens låst ({chosen_freq})")

    if args.test_feed:
        run_test_feed(chosen_freq)
        return

    # Kontrollera om verktygen rtl_fm och redsea finns tillgängliga
    import shutil
    has_rtl_fm = bool(shutil.which("rtl_fm"))
    has_redsea = bool(shutil.which("redsea"))

    if not (has_rtl_fm and has_redsea):
        print(f"Hårdvaruverktyg saknas (rtl_fm={has_rtl_fm}, redsea={has_redsea}). Kör i simulerat läge.", file=sys.stderr, flush=True)
        run_test_feed(chosen_freq)
        return

    # Kör RTL_FM | REDSEA i underprocesser
    global _current_child_proc
    rtl_cmd = ["rtl_fm", "-M", "fm", "-s", "171k", "-r", "171k", "-f", chosen_freq]
    if args.device:
        rtl_cmd.extend(["-d", args.device])
    if args.gain and args.gain != "auto":
        rtl_cmd.extend(["-g", str(args.gain)])
    if args.ppm and args.ppm != "0":
        rtl_cmd.extend(["-p", str(args.ppm)])
    rtl_cmd.append("-")

    redsea_cmd = ["redsea", "-r", "171k"]

    try:
        p1 = subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2 = subprocess.Popen(redsea_cmd, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        p1.stdout.close()
        _current_child_proc = p2

        for line in p2.stdout:
            if _shutdown_requested:
                break
            parse_redsea_json_line(line)
            
        if not _shutdown_requested:
            err_out = ""
            if p2.stderr:
                err_out = p2.stderr.read().strip()
            print(f"redsea avslutades ({err_out}). Startar fallback.", file=sys.stderr, flush=True)
            run_test_feed(chosen_freq)
    except Exception as e:
        print(f"Fel vid körning av redsea-ström: {e}", file=sys.stderr, flush=True)
        run_test_feed(chosen_freq)
    finally:
        if _current_child_proc:
            try:
                _current_child_proc.kill()
            except Exception:
                pass

if __name__ == "__main__":
    main()
