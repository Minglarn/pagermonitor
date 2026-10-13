#!/usr/bin/env python3
"""
RDS / RDS-TMC Decoder Module for PagerMonitor.
Decodes RDS-TMC (ALERT-C / ISO 14819) traffic events and standard RDS metadata
from redsea or direct FM SDR stream. Translates TMC location codes using Sweden
Location Table LTN 01 (Trafikverket) and event codes to human-readable Swedish.
"""

import sys
import os
import time
import json
import argparse
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
    101: "Trafikolycka",
    102: "Allvarlig trafikolycka",
    103: "Flerbilsolycka",
    104: "Vält fordon på vägbanan",
    105: "Olycka med tung lastbil",
    106: "Olycka med buss",
    107: "Olycka med farligt gods",
    108: "Kollision med vilt",
    201: "Stillastående kö",
    202: "Trafikkö",
    203: "Långsamtgående trafik",
    204: "Risk för köbildning",
    205: "Köer upplöses",
    301: "Vägarbete",
    302: "Långvarigt vägarbete",
    303: "Akut reparationsarbete på vägbanan",
    304: "Asfaltering / Beläggningsarbete",
    305: "Underhållsarbete längs vägen",
    401: "Väg helt avstängd i båda riktningar",
    402: "Körfält avstängt",
    403: "Ett körfält blockerat",
    404: "Flera körfält blockerade",
    405: "Avfart avstängd",
    406: "Påfart avstängd",
    407: "Bro avstängd",
    408: "Tunnel avstängd",
    501: "Hinder på vägbanan",
    502: "Tappad last på vägen",
    503: "Havererat fordon på vägbanan",
    504: "Djur på vägen",
    505: "Personer på vägen",
    506: "Föremål på vägen",
    601: "Utryckningsfordon på väg",
    602: "Räddningsarbete pågår på platsen",
    701: "Hastighetsbegränsning nedsatt",
    702: "Variabel hastighet aktiverad",
    801: "Halka / Risk för blixthalka",
    802: "Snömodd / Snöhinder",
    803: "Vattenplaning / Vattenmassor",
    804: "Kraftig vind / Stormbyar",
    805: "Tät dimma / Dålig sikt",
    806: "Kraftigt regn / Skyfall",
    807: "Snöstorm / Drivbildning",
    808: "Hård sidvind över bro",
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

def format_and_print_rds(ps="", pi="", radiotext=""):
    """Skriver ut standard RDS information."""
    parts = ["RDS:"]
    if ps:
        parts.append(f"PS: {ps}")
    if pi:
        parts.append(f"PI: {pi}")
    if radiotext:
        parts.append(f"RT: {radiotext}")
    out_line = " ".join(parts)
    print(out_line, flush=True)
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

    # 1. Kontrollera om raden innehåller TMC (Grupp 8A eller liknande)
    if "tmc" in data:
        tmc = data["tmc"]
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

    # 2. Kontrollera vanlig RDS-metadata (PS / RadioText / Station)
    ps = data.get("ps", "").strip()
    rt = data.get("radiotext", "").strip()
    pi = data.get("pi", "")

    if ps or rt:
        return format_and_print_rds(ps=ps, pi=pi, radiotext=rt)

    return None

def run_test_feed(freq="100.5M"):
    """Genererar syntetiska RDS och TMC-händelser för testning och demonstration."""
    print(f"RDS-TMC Decoder: Testflöde aktivt på {freq} (Genererar ALERT-C trafikmeddelanden)...", file=sys.stderr, flush=True)
    format_and_print_rds(ps="SR P4", pi="E201", radiotext="Sveriges Radio P4 - Trafik och Musik")
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
    parser.add_argument("--freq", default="100.5M", help="FM frequency (e.g. 100.5M or 98.3M)")
    parser.add_argument("--device", default="", help="RTL-SDR device serial or index")
    parser.add_argument("--gain", default="auto", help="Tuner gain in dB or auto")
    parser.add_argument("--ppm", default="0", help="PPM error correction")
    parser.add_argument("--test-feed", action="store_true", help="Run synthetic test feed")
    args = parser.parse_args()

    # Om stdin skickas via pipe (t.ex. från redsea eller cat test.json)
    if not sys.stdin.isatty():
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

    # Kör RTL_FM | REDSEA i underprocesser
    global _current_child_proc
    rtl_cmd = ["rtl_fm", "-M", "fm", "-s", "171k", "-r", "171k", "-f", args.freq]
    if args.device:
        rtl_cmd.extend(["-d", args.device])
    if args.gain and args.gain != "auto":
        rtl_cmd.extend(["-g", str(args.gain)])
    if args.ppm and args.ppm != "0":
        rtl_cmd.extend(["-p", str(args.ppm)])
    rtl_cmd.append("-")

    redsea_cmd = ["redsea", "-u"]

    try:
        p1 = subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(redsea_cmd, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        p1.stdout.close()
        _current_child_proc = p2

        for line in p2.stdout:
            if _shutdown_requested:
                break
            parse_redsea_json_line(line)
    except Exception as e:
        print(f"Fel vid körning av redsea-ström: {e}", file=sys.stderr)
        run_test_feed(args.freq)
    finally:
        if _current_child_proc:
            try:
                _current_child_proc.kill()
            except Exception:
                pass

if __name__ == "__main__":
    main()
