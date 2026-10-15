import socket
import json
import threading
import time
import logging
import re
import base64
import zlib
from datetime import datetime
from database import (
    save_message, get_alias_info, check_alert_words, 
    get_settings, increment_message_repeat
)

try:
    from mqtt_client import publish_message
except ImportError:
    def publish_message(*args, **kwargs):
        pass

try:
    from acars_human_parser import (
        parse_human_acars, AIRLINE_MAP, GROUND_STATIONS, ACARS_LABELS as PARSER_ACARS_LABELS,
        lookup_airline, lookup_ground_station, lookup_label, build_acars_metadata_header,
        extract_acars_metadata, format_libacars_data
    )
except ImportError:
    AIRLINE_MAP = {}
    GROUND_STATIONS = {}
    PARSER_ACARS_LABELS = {}
    def parse_human_acars(msg, label=None, metadata=None, strip_prefix=False): return msg
    def lookup_airline(f): return ""
    def lookup_ground_station(a): return ""
    def lookup_label(l): return ""
    def build_acars_metadata_header(avlc=None, acars=None, vdl2_frame=None): return ""
    def extract_acars_metadata(avlc=None, acars=None, vdl2_frame=None): return {}
    def format_libacars_data(a=None, x=None, v=None): return ""

logger = logging.getLogger(__name__)

# ACARS Label-koder och deras förklaringar från acars_reference_data.json
ACARS_LABELS = dict(PARSER_ACARS_LABELS)
ACARS_LABELS['H2'] = 'Meteorologisk rapport (AMDAR)'
LABEL_MAP = ACARS_LABELS


# Kända ICAO-flygplatser och deras namn
AIRPORT_MAP = {
    # Norden:
    'ESSA': 'Stockholm/Arlanda',
    'ESSB': 'Stockholm/Bromma',
    'ESKN': 'Stockholm/Skavsta',
    'ESOW': 'Stockholm/Västerås',
    'ESGG': 'Göteborg/Landvetter',
    'ESMS': 'Malmö/Sturup',
    'ESSV': 'Visby',
    'ESDF': 'Ronneby/Kallinge',
    'ESCF': 'Linköping/Malmen',
    'ESSL': 'Linköping/Saab',
    'ESMQ': 'Kalmar',
    'ESMX': 'Växjö',
    'ESTA': 'Ängelholm',
    'ESMT': 'Halmstad',
    'ESGJ': 'Jönköping',
    'ESGT': 'Trollhättan',
    'ESOE': 'Örebro',
    'ESOK': 'Karlstad',
    'ESSD': 'Borlänge',
    'ESNN': 'Sundsvall',
    'ESNZ': 'Östersund/Åre',
    'ESNU': 'Umeå',
    'ESNK': 'Kramfors',
    'ESNS': 'Skellefteå',
    'ESPA': 'Luleå/Kallax',
    'ESPE': 'Vidsel',
    'ESNQ': 'Kiruna',
    'ESNG': 'Gällivare',
    'EKCH': 'Köpenhamn/Kastrup',
    'EKBI': 'Billund',
    'EKYT': 'Aalborg',
    'ENGM': 'Oslo/Gardermoen',
    'ENTO': 'Oslo/Torp',
    'ENBR': 'Bergen/Flesland',
    'ENVA': 'Trondheim/Værnes',
    'ENZV': 'Stavanger/Sola',
    'ENTC': 'Tromsø',
    'ENBO': 'Bodø',
    'EFHK': 'Helsingfors/Vanda',
    'EFTU': 'Åbo',
    'EFTP': 'Tammerfors',
    'EFOU': 'Uleåborg',
    'EFRO': 'Rovaniemi',
    'EFVA': 'Vasa',
    'BIKF': 'Reykjavik/Keflavik',

    # Baltikum & Polen:
    'EETN': 'Tallinn',
    'EVRA': 'Riga',
    'EYVI': 'Vilnius',
    'EYKA': 'Kaunas',
    'EPWA': 'Warszawa/Chopin',
    'EPMO': 'Warszawa/Modlin',
    'EPGD': 'Gdansk',
    'EPKK': 'Krakow',
    'EPWR': 'Wroclaw',
    'EPPO': 'Poznan',
    'EPKT': 'Katowice',

    # Övriga Europa & Världen:
    'EDDF': 'Frankfurt',
    'EDDM': 'München',
    'EDDB': 'Berlin/Brandenburg',
    'EDDL': 'Düsseldorf',
    'EDDH': 'Hamburg',
    'EDDK': 'Köln/Bonn',
    'EDDS': 'Stuttgart',
    'EDDP': 'Leipzig',
    'EHAM': 'Amsterdam/Schiphol',
    'EHEH': 'Eindhoven',
    'EBBR': 'Bryssel',
    'EBCI': 'Charleroi',
    'ELLX': 'Luxemburg',
    'EGLL': 'London/Heathrow',
    'EGKK': 'London/Gatwick',
    'EGSS': 'London/Stansted',
    'EGGW': 'London/Luton',
    'EGLC': 'London/City',
    'EGCC': 'Manchester',
    'EGPH': 'Edinburgh',
    'EIDW': 'Dublin',
    'LFPG': 'Paris/Charles de Gaulle',
    'LFPO': 'Paris/Orly',
    'LFMN': 'Nice',
    'LFLL': 'Lyon',
    'LSZH': 'Zürich',
    'LSGG': 'Genève',
    'LOWW': 'Wien/Schwechat',
    'LOWI': 'Innsbruck',
    'LKPR': 'Prag',
    'LHBP': 'Budapest',
    'LROP': 'Bukarest/Otopeni',
    'LBSF': 'Sofia',
    'LGAV': 'Aten',
    'LTFM': 'Istanbul',
    'LTFJ': 'Istanbul/Sabiha Gökçen',
    'LTAI': 'Antalya',
    'LEMD': 'Madrid/Barajas',
    'LEBL': 'Barcelona/El Prat',
    'LEMG': 'Málaga',
    'LEPA': 'Palma de Mallorca',
    'LPPT': 'Lissabon',
    'LIRF': 'Rom/Fiumicino',
    'LIMC': 'Milano/Malpensa',
    'LIME': 'Milano/Bergamo',
    'LIPZ': 'Venedig',
    'OMDB': 'Dubai',
    'OTHH': 'Doha/Hamad',
    'KJFK': 'New York/JFK',
    'KEWR': 'New York/Newark',
    'KORD': "Chicago/O'Hare",
    'ZBAA': 'Peking/Capital',
    'ZSPD': 'Shanghai/Pudong',
    'RJTT': 'Tokyo/Haneda',
    'VTBS': 'Bangkok/Suvarnabhumi'
}

def format_airport(icao: str) -> str:
    """Slår upp flygplatsnamn utifrån 4-ställig ICAO-kod och returnerar 'EKCH (Köpenhamn/Kastrup)'."""
    if not icao:
        return ""
    code = str(icao).strip().upper()
    ap_name = AIRPORT_MAP.get(code)
    return f"{code} ({ap_name})" if ap_name else code

# Länkkoder för Media Advisory (Label SA)
LINK_NAMES = {
    'V': 'VHF ACARS',
    '2': 'VDL2',
    'H': 'HF',
    'S': 'Satcom',
    'G': 'GlobalStar',
    'I': 'Iridium'
}

def humanize_acars_message(label, msg_text, acars_dict=None):
    """
    Tolkar kryptiska ACARS-koder till läsbar svenska (Media Advisory, ATIS, Clearance, FMS m.m.).
    """
    lbl = (label or '').strip().upper()
    txt = (msg_text or '').strip()

    # 1. Label SA (Media Advisory / Länkstatus)
    if lbl == 'SA' or txt.startswith('0E') or txt.startswith('0L'):
        media_adv = acars_dict.get('media_adv') if isinstance(acars_dict, dict) else None
        if isinstance(media_adv, dict):
            state_raw = str(media_adv.get('state') or '').lower()
            status_w = "Länk upprättad" if ("estab" in state_raw or state_raw == 'e') else ("Länk förlorad" if ("lost" in state_raw or state_raw == 'l') else "Länkstatus")
            curr_code = str(media_adv.get('curr_link') or media_adv.get('current_link') or '').upper()
            curr_link = LINK_NAMES.get(curr_code, curr_code or 'VDL2')
            tm_str = media_adv.get('time') or ''
            time_part = f" kl {tm_str} UTC" if tm_str else ""
            av_list = media_adv.get('avail_links') or []
            avail_names = [LINK_NAMES.get(str(x).upper(), str(x)) for x in av_list]
            avail_part = f" | Tillgängliga länkar: {', '.join(avail_names)}" if avail_names else ""
            raw_suffix = f" ({txt})" if txt else ""
            return f"{status_w} på {curr_link}{time_part}{avail_part}{raw_suffix}".strip()

        m_sa = re.search(r'0([EL])([V2HSGI])(\d{2})(\d{2})(\d{2})([V2HSGI]*)', txt)
        if m_sa:
            stat_code = m_sa.group(1).upper()
            status_w = "Länk upprättad" if stat_code == 'E' else "Länk förlorad"
            curr_code = m_sa.group(2).upper()
            curr_link = LINK_NAMES.get(curr_code, curr_code)
            hh, mm, ss = m_sa.group(3), m_sa.group(4), m_sa.group(5)
            avail_raw = m_sa.group(6).upper()
            avail_names = [LINK_NAMES.get(c, c) for c in avail_raw]
            avail_part = f" | Tillgängliga länkar: {', '.join(avail_names)}" if avail_names else ""
            return f"{status_w} på {curr_link} kl {hh}:{mm}:{ss} UTC{avail_part} ({txt})"
        elif lbl == 'SA' and txt:
            return f"Länkstatus (Media Advisory) | Rådata: {txt}"

    # 2. Begäran om ATIS och starttillstånd (/XXXX.TI2, /XXXX.DC1, /XXXX.OC1)
    m_action = re.search(r'/([A-Z]{4})\.(TI2|DC1|OC1)/?', txt, re.IGNORECASE)
    if m_action:
        icao = m_action.group(1).upper()
        act = m_action.group(2).upper()
        ap_disp = format_airport(icao)
        if act == 'TI2':
            m_ad = re.search(r'/([A-Z]{4})\.TI2/(?:\d{1,4}\1)?([AD])', txt, re.IGNORECASE)
            atis_type = (m_ad.group(2).upper()) if m_ad else ''
            if atis_type == 'A':
                desc = f"Begär landningsväder (Arrival ATIS) för {ap_disp}"
            elif atis_type == 'D':
                desc = f"Begär avgångsväder (Departure ATIS) för {ap_disp}"
            else:
                desc = f"Begär flygplatsväder (ATIS) för {ap_disp}"
        elif act == 'DC1':
            desc = f"Begär starttillstånd (Departure Clearance) för {ap_disp}"
        elif act == 'OC1':
            desc = f"Begär Oceanic Clearance via {ap_disp}"
        else:
            desc = f"Flygplatsanrop för {ap_disp}"
        return f"{desc} | Rådata: {txt}"

    # 2b. Label B9 eller A9 med flygplatskod
    if lbl in ('B9', 'A9') and txt:
        m_icao = re.search(r'\b([A-Z]{4})\b', txt)
        if m_icao:
            icao = m_icao.group(1).upper()
            ap_disp = format_airport(icao)
            if lbl == 'B9':
                return f"Begär flygplatsväder (ATIS) för {ap_disp} | Rådata: {txt}"
            else:
                return f"Flygplatsväder (ATIS) för {ap_disp} | {txt}"

    # 2c. Flygbolagens interna AOC-labels (Label 1L, 1A-4Z)
    m_aoc_seq = re.match(r'^(\d{10,12})([A-Z0-9.,\-/]+)$', txt)
    is_aoc_label = bool(lbl == '1L' or re.match(r'^[1-4][A-Z]$', lbl))
    if lbl == '1L' or (is_aoc_label and m_aoc_seq):
        seq_part = f", Seq: {m_aoc_seq.group(1)[:6]}" if m_aoc_seq else ""
        return f"[AOC Flygbolagsdata] Intern kodad drift-/telemetrirapport (Lufthansa Group{seq_part}) | Rådata: {txt}"

    # 3. Boeing / Honeywell FMS & CMC prefix
    if txt.startswith('#M1B'):
        if not txt.startswith('[Boeing/Honeywell FMS]'):
            txt = f"[Boeing/Honeywell FMS] {txt}"
    elif txt.startswith('#CFB'):
        if not txt.startswith('[Underhållsdata/CMC]'):
            txt = f"[Underhållsdata/CMC] {txt}"
    elif txt.startswith('#DFB'):
        if not txt.startswith('[Flygdata/DFDAU]'):
            txt = f"[Flygdata/DFDAU] {txt}"

    # 4. Label Q0 (Link Test Ping)
    if lbl == 'Q0':
        return f"ACARS Länktest (Link Test Ping) | Rådata: {txt}" if txt else "ACARS Länktest (Link Test Ping)"

    # 5. Label _d (ACK)
    if lbl == '_d' or not txt:
        return "Kvittens (ACK)" if not txt else f"Kvittens (ACK) | {txt}"

    # 6. Modulär Human ACARS Parser för specialiserade mönster (Label 38, H1 POSN, H1 RESREQ, 83 ETA, MM m.fl.)
    return parse_human_acars(txt, label=lbl, metadata=acars_dict)

def find_nested_key(data, target_key):
    """Söker rekursivt efter en nyckel i ett nästlat JSON-objekt eller lista."""
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for v in data.values():
            res = find_nested_key(v, target_key)
            if res is not None:
                return res
    elif isinstance(data, list):
        for item in data:
            res = find_nested_key(item, target_key)
            if res is not None:
                return res
    return None

def extract_position_and_telemetry(text, vdl2_obj=None):
    """
    Extraherar latitud, longitud, altitud och telemetri ur meddelandetext eller vdl2 JSON.
    Hanterar:
      Mönster 1: Airbus MIAM / FDIMU semikolon-format (PALAT, PALONG, PAALT m.fl.)
      Mönster 2: Standard decimalformat i ACARS (t.ex. Ryanair Label 16: N 56.955 E 17.322)
      Mönster 3: Kompakt DM-format i ACARS (t.ex. Finnair Label H1: POSN58525E018360)
      Mönster 4: XID / GSIF / ADS-C fallback ur JSON
    """
    res = {
        'lat': None,
        'lon': None,
        'alt_ft': None,
        'telemetry_summary': '',
        'telemetry': {}
    }

    raw_text = text or ''

    # --- Mönster 0a: AMDAR meteorologiska rapporter (Label H2 m.fl.) ---
    # Exempel: 02E15LOWWESSAN55287E01618406503096M407353048G   QN56167...
    amdar_matches = re.findall(
        r'([NS])(\d{2})(\d{3})([EW])(\d{3})(\d{3})(\d{4})(\d{4})([MP])(\d{3})(\d{3})(\d{3})G',
        raw_text
    )
    if amdar_matches:
        last_pt = amdar_matches[-1]
        ns, lat_d, lat_m, ew, lon_d, lon_m, t_str, alt_s, t_sign, temp_s, w_dir, w_spd = last_pt
        try:
            lat_val = int(lat_d) + (int(lat_m) / 600.0)
            if ns.upper() == 'S':
                lat_val = -lat_val
            lon_val = int(lon_d) + (int(lon_m) / 600.0)
            if ew.upper() == 'W':
                lon_val = -lon_val
            res['lat'] = round(lat_val, 4)
            res['lon'] = round(lon_val, 4)
            res['alt_ft'] = int(alt_s) * 10

            temp_val = int(temp_s) / 10.0
            temp_sign_char = '-' if t_sign.upper() == 'M' else '+'
            wind_dir_val = int(w_dir)
            wind_spd_val = int(w_spd)
            time_str = f"{t_str[:2]}:{t_str[2:]} UTC"
            alt_fmt = f"{res['alt_ft']:,} ft".replace(',', ' ')

            res['telemetry']['time'] = time_str
            res['telemetry']['temp_c'] = -temp_val if t_sign.upper() == 'M' else temp_val
            res['telemetry']['wind_dir'] = wind_dir_val
            res['telemetry']['wind_kt'] = wind_spd_val
            res['telemetry']['num_points'] = len(amdar_matches)

            m_hdr = re.search(r'02E\d{2}([A-Z]{4})([A-Z]{4})', raw_text)
            if m_hdr:
                orig_icao = m_hdr.group(1).upper()
                dest_icao = m_hdr.group(2).upper()
                res['dst_airport'] = dest_icao
                orig_fmt = format_airport(orig_icao)
                dest_fmt = format_airport(dest_icao)
                res['telemetry_summary'] = (
                    f"Rutt: {orig_fmt} → {dest_fmt} | "
                    f"Senaste ({time_str}): Pos {res['lat']:.4f}, {res['lon']:.4f} | "
                    f"Höjd: {alt_fmt} | Temp: {temp_sign_char}{temp_val:.1f}°C | "
                    f"Vind: {wind_dir_val}° / {wind_spd_val} kt ({len(amdar_matches)} mätpunkter)"
                )
            else:
                res['telemetry_summary'] = (
                    f"AMDAR Senaste ({time_str}): Pos {res['lat']:.4f}, {res['lon']:.4f} | "
                    f"Höjd: {alt_fmt} | Temp: {temp_sign_char}{temp_val:.1f}°C | "
                    f"Vind: {wind_dir_val}° / {wind_spd_val} kt ({len(amdar_matches)} mätpunkter)"
                )
            return res
        except (ValueError, TypeError):
            pass

    # --- Mönster 0b: Boeing CSV FMS / väderlogg (Label H1 m.fl.) ---
    # Exempel: N5611.4,E01728.9,150706,40003,-63.3,341,082,ER,00000,0,
    lot_matches = re.findall(
        r'([NS])(\d{2})(\d{2}\.\d+),([EW])(\d{3})(\d{2}\.\d+),(\d{6}),(-?\d+),(-?\d+\.\d+),(\d{3}),(\d{3}),([A-Z]{2})',
        raw_text
    )
    if lot_matches:
        last_pt = lot_matches[-1]
        ns, lat_d, lat_m, ew, lon_d, lon_m, t_str, alt_s, temp_s, w_dir, w_spd, phase = last_pt
        try:
            lat_val = int(lat_d) + (float(lat_m) / 60.0)
            if ns.upper() == 'S':
                lat_val = -lat_val
            lon_val = int(lon_d) + (float(lon_m) / 60.0)
            if ew.upper() == 'W':
                lon_val = -lon_val
            res['lat'] = round(lat_val, 4)
            res['lon'] = round(lon_val, 4)
            res['alt_ft'] = int(alt_s)

            temp_val = float(temp_s)
            wind_dir_val = int(w_dir)
            wind_spd_val = int(w_spd)
            time_str = f"{t_str[2:4]}:{t_str[4:6]} UTC"
            alt_fmt = f"{res['alt_ft']:,} ft".replace(',', ' ')

            res['telemetry']['time'] = time_str
            res['telemetry']['temp_c'] = temp_val
            res['telemetry']['wind_dir'] = wind_dir_val
            res['telemetry']['wind_kt'] = wind_spd_val
            res['telemetry']['flight_phase'] = phase
            res['telemetry']['num_points'] = len(lot_matches)

            m_hdr = re.search(
                r'[A-Z0-9_]+\s*,\s*([A-Z0-9]+)\s*,\s*(\d{6})\s*,\s*([A-Z0-9]+)\s*,\s*([A-Z]{4})\s*,\s*([A-Z]{4})',
                raw_text
            )
            if m_hdr:
                ac_type = m_hdr.group(1).strip()
                callsign = m_hdr.group(3).strip()
                orig_icao = m_hdr.group(4).strip().upper()
                dest_icao = m_hdr.group(5).strip().upper()
                res['dst_airport'] = dest_icao
                orig_fmt = format_airport(orig_icao)
                dest_fmt = format_airport(dest_icao)
                res['telemetry_summary'] = (
                    f"Flygplan: {ac_type} | Rutt: {orig_fmt} → {dest_fmt} | "
                    f"Senaste ({time_str}): Pos {res['lat']:.4f}, {res['lon']:.4f} | "
                    f"Höjd: {alt_fmt} | Temp: {temp_val:.1f}°C | "
                    f"Vind: {wind_dir_val}° / {wind_spd_val} kt ({len(lot_matches)} mätpunkter)"
                )
            else:
                res['telemetry_summary'] = (
                    f"FMS Logg Senaste ({time_str}): Pos {res['lat']:.4f}, {res['lon']:.4f} | "
                    f"Höjd: {alt_fmt} | Temp: {temp_val:.1f}°C | "
                    f"Vind: {wind_dir_val}° / {wind_spd_val} kt ({len(lot_matches)} mätpunkter)"
                )
            return res
        except (ValueError, TypeError):
            pass

    # --- Mönster 0: CSV-positionsrapport (t.ex. Label 83) ---
    # Exempel: ESSA,HAAB,142029, 58.54,  18.94,22605,305, 166.9, 43000
    if ',' in raw_text:
        m_csv = re.search(
            r'\b([A-Z]{3,4})\s*,\s*([A-Z]{3,4})\s*,\s*(\d{6})\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(\d+)\s*,\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*,\s*(\d+)',
            raw_text
        )
        if m_csv:
            try:
                res['lat'] = float(m_csv.group(4))
                res['lon'] = float(m_csv.group(5))
                res['alt_ft'] = int(m_csv.group(6))
                spd = float(m_csv.group(7))
                hdg = float(m_csv.group(8))
                fuel = m_csv.group(9)
                res['telemetry']['speed_kt'] = spd
                res['telemetry']['heading'] = hdg
                res['telemetry']['fuel_weight'] = fuel
                fl = round(res['alt_ft'] / 100)
                res['telemetry_summary'] = f"FL{fl} ({res['alt_ft']:,} ft) | Fart: {spd:.0f} kt | Kurs: {hdg:.0f}°"
                return res
            except (ValueError, TypeError):
                pass

    # --- Mönster 1: Airbus MIAM / FDIMU semikolon-format ---
    # Exempel: ;PAALT,41001;PALAT,5.875309E+01;PALONG,1.543292E+01;PASAT,-6.347548E+01;...
    if 'PALAT' in raw_text or 'PALONG' in raw_text or ';PA' in raw_text:
        kv = {}
        for token in raw_text.split(';'):
            token = token.strip()
            if ',' in token:
                parts = token.split(',', 1)
                k = parts[0].strip().upper()
                v = parts[1].strip()
                kv[k] = v

        if 'PALAT' in kv and 'PALONG' in kv:
            try:
                res['lat'] = float(kv['PALAT'])
                res['lon'] = float(kv['PALONG'])
            except (ValueError, TypeError):
                pass

        if 'PAALT' in kv:
            try:
                res['alt_ft'] = int(float(kv['PAALT']))
            except (ValueError, TypeError):
                pass

        summary_parts = []
        if res['alt_ft'] is not None:
            fl = round(res['alt_ft'] / 100)
            summary_parts.append(f"FL{fl}")

        if 'PAFMSAWID' in kv and kv['PAFMSAWID'].strip():
            w = kv['PAFMSAWID'].strip()
            res['telemetry']['waypoint'] = w
            summary_parts.append(f"Waypoint: {w}")

        if 'PAMN' in kv:
            try:
                mach = float(kv['PAMN'])
                res['telemetry']['mach'] = round(mach, 2)
                summary_parts.append(f"Mach {mach:.2f}")
            except (ValueError, TypeError):
                pass

        if 'PATHDG' in kv:
            try:
                hdg = float(kv['PATHDG'])
                res['telemetry']['heading'] = round(hdg, 1)
                summary_parts.append(f"Kurs: {hdg:.0f}°")
            except (ValueError, TypeError):
                pass

        if 'PASAT' in kv:
            try:
                sat = float(kv['PASAT'])
                res['telemetry']['temp_c'] = round(sat, 1)
                summary_parts.append(f"Temp: {sat:.1f}°C")
            except (ValueError, TypeError):
                pass

        if 'PAFOB' in kv:
            try:
                fob = float(kv['PAFOB'])
                res['telemetry']['fuel_kg'] = int(fob)
                summary_parts.append(f"Bränsle: {int(fob)} kg")
            except (ValueError, TypeError):
                pass

        if 'PAWS' in kv:
            try:
                ws = float(kv['PAWS'])
                res['telemetry']['wind_kt'] = round(ws, 1)
                summary_parts.append(f"Vind: {ws:.0f} kt")
            except (ValueError, TypeError):
                pass

        if 'PAGWTFQMS' in kv:
            try:
                gwt = float(kv['PAGWTFQMS'])
                res['telemetry']['gross_weight_kg'] = int(gwt)
            except (ValueError, TypeError):
                pass

        if summary_parts:
            res['telemetry_summary'] = " | ".join(summary_parts)

        if res['lat'] is not None and res['lon'] is not None:
            return res

    # --- Mönster 2: Standard decimalformat i ACARS (t.ex. Ryanair Label 16) ---
    # Exempel: 191331,37012,1946,  74,N 56.955 E 17.322
    m2 = re.search(r'([NS])\s*([0-9]{1,3}\.[0-9]{2,5})\s*([EW])\s*([0-9]{1,3}\.[0-9]{2,5})', raw_text, re.IGNORECASE)
    if not m2:
        m2 = re.search(r'([0-9]{1,3}\.[0-9]{2,5})\s*([NS])\s*([0-9]{1,3}\.[0-9]{2,5})\s*([EW])', raw_text, re.IGNORECASE)
        if m2:
            try:
                lat = float(m2.group(1)) * (-1 if m2.group(2).upper() == 'S' else 1)
                lon = float(m2.group(3)) * (-1 if m2.group(4).upper() == 'W' else 1)
                res['lat'], res['lon'] = lat, lon
            except (ValueError, TypeError):
                pass
    else:
        try:
            lat = float(m2.group(2)) * (-1 if m2.group(1).upper() == 'S' else 1)
            lon = float(m2.group(4)) * (-1 if m2.group(3).upper() == 'W' else 1)
            res['lat'], res['lon'] = lat, lon
        except (ValueError, TypeError):
            pass

    # Sök efter altitud i kommaseparerade fält (t.ex. 191331,37012,...)
    if res['lat'] is not None:
        comma_tokens = [t.strip() for t in raw_text.split(',')]
        for token in comma_tokens:
            if re.match(r'^[0-9]{4,5}$', token):
                alt_candidate = int(token)
                if 1000 <= alt_candidate <= 50000:
                    res['alt_ft'] = alt_candidate
                    fl = round(alt_candidate / 100)
                    res['telemetry_summary'] = f"FL{fl} ({alt_candidate:,} ft)"
                    break
        return res

    # --- Mönster 3: Kompakt DM-format i ACARS (t.ex. Finnair Label H1) och generella DM-format ---
    # Exempel: POSN58525E018360,... eller 5912.4N 01805.2E eller N5912.4 E01805.2
    m3 = re.search(r'(?:POS)?\s*([NS])([0-9]{2})([0-9]{2,3})\s*([EW])([0-9]{3})([0-9]{2,3})', raw_text, re.IGNORECASE)
    if m3:
        try:
            lat_ns = m3.group(1).upper()
            lat_deg = int(m3.group(2))
            lat_min_raw = m3.group(3)
            lat_min = int(lat_min_raw) / (600.0 if len(lat_min_raw) == 3 else 60.0)
            lat = (lat_deg + lat_min) * (-1 if lat_ns == 'S' else 1)

            lon_ew = m3.group(4).upper()
            lon_deg = int(m3.group(5))
            lon_min_raw = m3.group(6)
            lon_min = int(lon_min_raw) / (600.0 if len(lon_min_raw) == 3 else 60.0)
            lon = (lon_deg + lon_min) * (-1 if lon_ew == 'W' else 1)

            res['lat'], res['lon'] = round(lat, 4), round(lon, 4)
        except (ValueError, TypeError):
            pass

    if res['lat'] is None:
        # Format med decimalpunkt: t.ex. N5611.4, E01728.9 eller 5912.4N 01805.2E
        # Välj alltid sista förekomsten om flera punkter loggats
        dm_matches = re.findall(r'([NS])\s*([0-9]{2})([0-9]{2}\.[0-9]+)\s*[/,\s]?\s*([EW])\s*([0-9]{3})([0-9]{2}\.[0-9]+)', raw_text, re.IGNORECASE)
        if dm_matches:
            last_m = dm_matches[-1]
            try:
                lat_ns = last_m[0].upper()
                lat_deg = int(last_m[1])
                lat_min = float(last_m[2])
                lat = (lat_deg + lat_min / 60.0) * (-1 if lat_ns == 'S' else 1)

                lon_ew = last_m[3].upper()
                lon_deg = int(last_m[4])
                lon_min = float(last_m[5])
                lon = (lon_deg + lon_min / 60.0) * (-1 if lon_ew == 'W' else 1)
                res['lat'], res['lon'] = round(lat, 4), round(lon, 4)
            except (ValueError, TypeError):
                pass
        else:
            dm_matches_rev = re.findall(r'([0-9]{2})([0-9]{2}\.[0-9]+)\s*([NS])\s*[/,\s]?\s*([0-9]{3})([0-9]{2}\.[0-9]+)\s*([EW])', raw_text, re.IGNORECASE)
            if dm_matches_rev:
                last_m = dm_matches_rev[-1]
                try:
                    lat_deg = int(last_m[0])
                    lat_min = float(last_m[1])
                    lat_ns = last_m[2].upper()
                    lat = (lat_deg + lat_min / 60.0) * (-1 if lat_ns == 'S' else 1)

                    lon_deg = int(last_m[3])
                    lon_min = float(last_m[4])
                    lon_ew = last_m[5].upper()
                    lon = (lon_deg + lon_min / 60.0) * (-1 if lon_ew == 'W' else 1)
                    res['lat'], res['lon'] = round(lat, 4), round(lon, 4)
                except (ValueError, TypeError):
                    pass

    if res['lat'] is None:
        # Format: LAT 59.21 LON 18.08 eller LAT: 59.21, LON: 18.08
        m_latlon = re.search(r'LAT(?:ITUDE)?[:\s]+(-?[0-9]{1,3}\.[0-9]+)[,\s]+LON(?:GITUDE)?[:\s]+(-?[0-9]{1,3}\.[0-9]+)', raw_text, re.IGNORECASE)
        if m_latlon:
            try:
                res['lat'] = float(m_latlon.group(1))
                res['lon'] = float(m_latlon.group(2))
            except (ValueError, TypeError):
                pass

    # Sök efter FL / Altitud i texten om den inte redan är känd
    if res['alt_ft'] is None:
        m_fl = re.search(r'\b(?:FL|F)\s*([0-9]{2,3})\b', raw_text, re.IGNORECASE)
        if m_fl:
            fl_val = int(m_fl.group(1))
            res['alt_ft'] = fl_val * 100
            fl_str = f"FL{fl_val}"
            res['telemetry_summary'] = (fl_str + f" | {res['telemetry_summary']}").strip(' |') if res['telemetry_summary'] else fl_str
        else:
            m_alt_raw = re.search(r'\bALT[:\s]+([0-9]{4,5})\b', raw_text, re.IGNORECASE)
            if m_alt_raw:
                alt_num = int(m_alt_raw.group(1))
                res['alt_ft'] = alt_num
                fl_str = f"FL{round(alt_num / 100)}"
                res['telemetry_summary'] = (fl_str + f" | {res['telemetry_summary']}").strip(' |') if res['telemetry_summary'] else fl_str

    # Sök efter rutt/flygplatser i texten (t.ex. ESSA/EFHK eller ARN-HEL)
    m_route = re.search(r'\b([A-Z]{4})/([A-Z]{4})\b', raw_text)
    if not m_route:
        m_route = re.search(r'\b([A-Z]{3})[-/]([A-Z]{3})\b', raw_text)
    if m_route:
        orig = m_route.group(1).upper()
        dest = m_route.group(2).upper()
        if orig not in ('MIN', 'SEC', 'DEG', 'KMH') and dest not in ('MIN', 'SEC', 'DEG', 'KMH'):
            res['telemetry']['route'] = f"{orig} -> {dest}"
            r_str = f"Rutt: {format_airport(orig)} → {format_airport(dest)}"
            if res['telemetry_summary']:
                if r_str not in res['telemetry_summary']:
                    res['telemetry_summary'] += f" | {r_str}"
            else:
                res['telemetry_summary'] = r_str
            if not res.get('dst_airport'):
                res['dst_airport'] = dest

    # Sök efter FMS Destination och bana (PRG/DT..., INI/DT..., FTX/DT...)
    m_fms_dst = re.search(r'(?:PRG|INI|FTX)/DT([A-Z]{4})(?:,([0-9]{2}[LRC]?))?', raw_text)
    if m_fms_dst:
        dst_code = m_fms_dst.group(1).upper()
        res['dst_airport'] = dst_code
        rwy = m_fms_dst.group(2)
        rwy_part = f" Bana {rwy}" if rwy else ""
        dst_str = f"Dest: {format_airport(dst_code)}{rwy_part}"
        if res['telemetry_summary']:
            if dst_str not in res['telemetry_summary']:
                res['telemetry_summary'] = f"{dst_str} | {res['telemetry_summary']}"
        else:
            res['telemetry_summary'] = dst_str

    # Sök efter Arrival ATIS eller ATIS under flygning (t.ex. /EKCH.TI2/024EKCHA6237)
    m_atis_dst = re.search(r'/([A-Z]{4})\.TI2/(?:\d{1,4}\1)?([AD])?', raw_text, re.IGNORECASE)
    if m_atis_dst:
        atis_icao = m_atis_dst.group(1).upper()
        atis_type = (m_atis_dst.group(2) or '').upper()

        is_airborne = False
        if isinstance(vdl2_obj, dict):
            avlc = vdl2_obj.get('avlc', {}) if isinstance(vdl2_obj, dict) else {}
            src = avlc.get('src', {}) if isinstance(avlc, dict) else {}
            st = str(src.get('status') or '').lower()
            if 'air' in st:
                is_airborne = True

        if atis_type == 'A' or (atis_type != 'D' and is_airborne):
            res['dst_airport'] = atis_icao
            ap_str = f"Destination: {format_airport(atis_icao)}"
            if res['telemetry_summary']:
                if ap_str not in res['telemetry_summary']:
                    res['telemetry_summary'] = f"{ap_str} | {res['telemetry_summary']}"
            else:
                res['telemetry_summary'] = ap_str

    # --- Mönster 4: Fallback till XID / GSIF / ADS-C struktur ur JSON ---
    if isinstance(vdl2_obj, dict):
        avlc = vdl2_obj.get('avlc', {}) if isinstance(vdl2_obj, dict) else {}
        xid = avlc.get('xid', {}) if isinstance(avlc, dict) else {}
        if isinstance(xid, dict):
            # 1. XID ac_location
            ac_loc = xid.get('ac_location', {})
            loc = ac_loc.get('loc', {}) if isinstance(ac_loc, dict) else ac_loc
            if isinstance(loc, dict) and 'lat' in loc and 'lon' in loc:
                try:
                    res['lat'] = float(loc['lat'])
                    res['lon'] = float(loc['lon'])
                    if 'alt' in loc:
                        res['alt_ft'] = int(float(loc['alt']))
                        res['telemetry_summary'] = f"XID FL{round(res['alt_ft'] / 100)}"
                    elif not res['telemetry_summary']:
                        res['telemetry_summary'] = "XID Positionsrapport"
                except (ValueError, TypeError):
                    pass

            # XID vdl_params -> dst_airport (endast om inte redan satt av t.ex. FMS)
            vdl_params = xid.get('vdl_params', {}) if isinstance(xid.get('vdl_params'), dict) else {}
            dst_ap = vdl_params.get('dst_airport') or xid.get('dst_airport')
            if dst_ap and not res.get('dst_airport'):
                dst_code = str(dst_ap).strip().upper()
                res['dst_airport'] = dst_code
                ap_name = AIRPORT_MAP.get(dst_code, '')
                ap_str = f"Destination: {dst_code} ({ap_name})" if ap_name else f"Destination: {dst_code}"
                if res['telemetry_summary']:
                    if ap_str not in res['telemetry_summary']:
                        res['telemetry_summary'] += f" | {ap_str}"
                else:
                    res['telemetry_summary'] = ap_str

        # 2. ADS-C strukturer ur arinc622
        arinc = find_nested_key(vdl2_obj, 'arinc622')
        if isinstance(arinc, dict):
            adsc_node = arinc.get('adsc')
            if isinstance(adsc_node, dict):
                brep = adsc_node.get('basic_report', adsc_node)
                if isinstance(brep, dict) and 'lat' in brep and 'lon' in brep:
                    try:
                        res['lat'] = float(brep['lat'])
                        res['lon'] = float(brep['lon'])
                        if 'alt' in brep:
                            res['alt_ft'] = int(float(brep['alt']))
                            res['telemetry_summary'] = f"ADS-C FL{round(res['alt_ft'] / 100)}"
                        elif not res['telemetry_summary']:
                            res['telemetry_summary'] = "ADS-C Positionsrapport"
                    except (ValueError, TypeError):
                        pass

        # 3. Övriga ADS-C strukturer
        if res['lat'] is None:
            adsc = find_nested_key(vdl2_obj, 'adsc') or find_nested_key(vdl2_obj, 'basic_report')
            if isinstance(adsc, dict):
                lat_a = adsc.get('lat') or adsc.get('latitude')
                lon_a = adsc.get('lon') or adsc.get('longitude')
                if lat_a is not None and lon_a is not None:
                    try:
                        res['lat'] = float(lat_a)
                        res['lon'] = float(lon_a)
                        alt_a = adsc.get('alt') or adsc.get('altitude')
                        if alt_a:
                            res['alt_ft'] = int(float(alt_a))
                            res['telemetry_summary'] = f"ADS-C FL{round(res['alt_ft'] / 100)}"
                        elif not res['telemetry_summary']:
                            res['telemetry_summary'] = "ADS-C Positionsrapport"
                    except (ValueError, TypeError):
                        pass

        # 4. Top-level koordinater
        if res['lat'] is None:
            lat_top = vdl2_obj.get('lat') or vdl2_obj.get('latitude')
            lon_top = vdl2_obj.get('lon') or vdl2_obj.get('longitude')
            if lat_top is not None and lon_top is not None:
                try:
                    res['lat'] = float(lat_top)
                    res['lon'] = float(lon_top)
                except (ValueError, TypeError):
                    pass

    return res

def format_cpdlc(cpdlc_obj):
    """Extraherar och sammanfattar CPDLC flygledningsmeddelanden till läsbar text."""
    if isinstance(cpdlc_obj, str):
        return cpdlc_obj.strip()
    if not isinstance(cpdlc_obj, dict):
        return ""
    
    parts = []
    msg_type = cpdlc_obj.get('msg_type') or cpdlc_obj.get('direction') or ''
    if msg_type:
        parts.append(f"[{msg_type.upper()}]")
        
    elements = cpdlc_obj.get('elements') or []
    if isinstance(elements, list):
        for el in elements:
            if isinstance(el, dict):
                desc = el.get('description') or el.get('text') or el.get('name') or ''
                val = el.get('val') or el.get('value') or ''
                if desc and val:
                    parts.append(f"{desc}: {val}")
                elif desc:
                    parts.append(desc)
                elif val:
                    parts.append(str(val))
            elif isinstance(el, str):
                parts.append(el)
    elif isinstance(elements, str):
        parts.append(elements)
        
    raw_text = cpdlc_obj.get('text') or cpdlc_obj.get('msg_text') or ''
    if raw_text and not parts:
        parts.append(raw_text)
        
    return " ".join(parts).strip()

def decode_miam_base85(raw_text: str):
    """
    Försöker Base85-avkoda (RFC 1924) och dekomprimera (zlib / raw deflate)
    en komprimerad MIAM Single Transfer payload (Label: MA / T01 / T02).
    
    Returnerar:
      - Uppackad ASCII-textsträng om framgångsrik och läsbar text
      - Formaterad '[MIAM Binär Flygdata] ...' om uppackat men binär telemetri
      - None om avkodning/dekomprimering misslyckas (t.ex. fragment/ofullständig)
    """
    if not raw_text or not isinstance(raw_text, str):
        return None

    clean = re.sub(r'[\r\n\s]+', '', raw_text)
    if not clean:
        return None

    # MIAM Single Transfer header kan vara 3-8 tecken lång (t.ex. T02!, T01, T02## etc.)
    # Testa kandidatoffset från 3 till 8 samt 0-2 vid trunkerad/ren Base85
    if clean.startswith(('T01', 'T02', 'T')):
        offsets = [4, 3, 5, 6, 7, 8, 0, 1, 2]
    else:
        offsets = [0, 1, 2, 3, 4, 5, 6, 7, 8]

    decompressed_bytes = None
    for off in offsets:
        if off >= len(clean):
            continue
        sub = clean[off:]
        try:
            raw_bytes = base64.b85decode(sub.encode('ascii', errors='ignore'))
        except Exception:
            continue

        if not raw_bytes:
            continue

        # Prova dekomprimering:
        # 1. Standard zlib header (wbits=0 default)
        # 2. Raw deflate utan zlib wrapper (wbits=-zlib.MAX_WBITS)
        # 3. Gzip/auto wrapper (wbits=32 + zlib.MAX_WBITS)
        for wbits in [0, -zlib.MAX_WBITS, 32 + zlib.MAX_WBITS]:
            try:
                if wbits == 0:
                    decomp = zlib.decompress(raw_bytes)
                else:
                    decomp = zlib.decompress(raw_bytes, wbits)
                if decomp:
                    decompressed_bytes = decomp
                    break
            except Exception:
                pass
        if decompressed_bytes:
            break

    if not decompressed_bytes:
        return None

    # Undersök om uppackade bytes är läsbar text eller binär Airbus SAR/FDIMU-telemetri
    text_cand = None
    try:
        text_cand = decompressed_bytes.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text_cand = decompressed_bytes.decode('latin-1')
        except Exception:
            pass

    if text_cand:
        # Kontrollera andelen utskrivbara tecken
        printable_count = sum(1 for c in text_cand if c.isprintable() or c in '\r\n\t')
        ratio = printable_count / max(len(text_cand), 1)
        if ratio >= 0.80:
            return text_cand.strip('\x00\r\n\t ')

    # Om det är binär Airbus SAR/FDIMU-telemetri:
    size_bytes = len(decompressed_bytes)
    raw_latin = decompressed_bytes.decode('latin-1', errors='ignore')
    ascii_matches = re.findall(r'[A-Za-z0-9.,/:;_\-]{4,}', raw_latin)
    readable_strings = [m.strip() for m in ascii_matches if len(m.strip()) >= 4]

    header_line = f"[MIAM Binär Flygdata] Airbus komprimerat telemetripaket ({size_bytes} bytes uppackat)"
    if readable_strings:
        parts = ", ".join(readable_strings[:6])
        return f"{header_line}\nParametrar: {parts}"
    return header_line

def parse_vdl2_frame(data, filter_empty=True, filter_links=False):
    """
    Parsar ett JSON-paket från dumpvdl2 eller acars_router och returnerar ett strukturerat meddelande.
    Implementerar prioriteringsordning för MIAM, ACARS, CPDLC och telemetri samt läsbar avkodning.
    """
    if not isinstance(data, dict):
        return None

    vdl2 = data.get('vdl2', data)
    
    # 1. Frekvens i MHz
    freq_val = vdl2.get('freq') or data.get('freq') or data.get('channel')
    freq_str = '136.975M'
    freq_mhz_val = None
    if freq_val:
        try:
            f_num = float(freq_val)
            if f_num > 1000000:
                freq_mhz_val = f_num / 1e6
                freq_str = f"{freq_mhz_val:.3f}M"
            elif f_num > 0:
                freq_mhz_val = f_num
                freq_str = f"{f_num:.3f}M"
        except (ValueError, TypeError):
            freq_str = str(freq_val)

    # Signalnivå & SNR
    sig_level = vdl2.get('sig_level') if isinstance(vdl2, dict) else data.get('sig_level')
    noise_level = vdl2.get('noise_level') if isinstance(vdl2, dict) else data.get('noise_level')
    snr_db = None
    snr_str = ""
    if sig_level is not None and noise_level is not None:
        try:
            snr_db = round(float(sig_level) - float(noise_level), 1)
            snr_str = f"{snr_db:+.1f} dB"
        except (ValueError, TypeError):
            pass

    # 2. Adressering och ICAO
    avlc = vdl2.get('avlc', {}) if isinstance(vdl2, dict) else {}
    src = avlc.get('src', {}) if isinstance(avlc, dict) else {}
    src_addr = ''
    src_type = 'Aircraft'
    if isinstance(src, dict):
        src_addr = str(src.get('addr') or '').strip().upper()
        src_type = src.get('type') or 'Aircraft'
    elif isinstance(src, str):
        src_addr = src.strip().upper()
    if not src_addr:
        src_addr = str(data.get('icao') or data.get('hex') or data.get('addr') or '').strip().upper()

    dst = avlc.get('dst', {}) if isinstance(avlc, dict) else {}
    dst_addr = dst.get('addr') if isinstance(dst, dict) else str(dst)
    dst_type = dst.get('type') if isinstance(dst, dict) else 'Ground station'

    # 3. ACARS-objekt
    acars = avlc.get('acars') if isinstance(avlc, dict) else None
    if not acars:
        acars = find_nested_key(data, 'acars')

    flight = ''
    reg = ''
    label = ''
    msg_text = ''
    is_miam = False

    # PRIORITERINGSORDNING FÖR TEXT:
    # A) MIAM (Uppackad Airbus-telemetri):
    if isinstance(acars, dict):
        flight = str(acars.get('flight') or '').strip().upper()
        reg = str(acars.get('reg') or '').strip()
        label = str(acars.get('label') or '').strip()

        # 1. Undersök alla fält i dumpvdl2:s miam-träd
        miam_obj = acars.get('miam')
        if isinstance(miam_obj, dict):
            st = miam_obj.get('single_transfer')
            if isinstance(st, dict):
                core = st.get('miam_core')
                if isinstance(core, dict):
                    m_data = core.get('data')
                    if isinstance(m_data, dict):
                        sub_acars = m_data.get('acars')
                        if isinstance(sub_acars, dict):
                            miam_text = sub_acars.get('msg_text') or sub_acars.get('text')
                            if miam_text:
                                msg_text = str(miam_text).strip()
                                is_miam = True
                                if not flight and sub_acars.get('flight'):
                                    flight = str(sub_acars.get('flight')).strip().upper()
                                if not reg and sub_acars.get('reg'):
                                    reg = str(sub_acars.get('reg')).strip()
                                if sub_acars.get('label'):
                                    label = str(sub_acars.get('label')).strip()
                        if not msg_text:
                            raw_val = m_data.get('raw') or m_data.get('text') or m_data.get('msg_text')
                            if raw_val:
                                msg_text = str(raw_val).strip()
                                is_miam = True
                    elif isinstance(m_data, str) and m_data.strip():
                        msg_text = m_data.strip()
                        is_miam = True

                    if not msg_text:
                        raw_core = core.get('raw') or core.get('text')
                        if raw_core:
                            msg_text = str(raw_core).strip()
                            is_miam = True

                if not msg_text:
                    st_data = st.get('data') or st.get('raw') or st.get('text')
                    if isinstance(st_data, str) and st_data.strip():
                        msg_text = st_data.strip()
                        is_miam = True
                    elif isinstance(st_data, dict):
                        sub_text = st_data.get('msg_text') or st_data.get('text') or st_data.get('raw')
                        if sub_text:
                            msg_text = str(sub_text).strip()
                            is_miam = True

            if not msg_text:
                miam_fallback = miam_obj.get('data') or miam_obj.get('raw') or miam_obj.get('text')
                if isinstance(miam_fallback, str) and miam_fallback.strip():
                    msg_text = miam_fallback.strip()
                    is_miam = True

        # B) Om ingen MIAM-text hittades: Hämta rå ACARS-text
        if not msg_text:
            raw_acars_text = acars.get('msg_text') or acars.get('text')
            if raw_acars_text:
                msg_text = str(raw_acars_text).strip()

    # Fallback till rotnivå (t.ex. normaliserad JSON från router)
    if not flight:
        flight = str(data.get('flight') or '').strip().upper()
    if not reg:
        reg = str(data.get('tail') or data.get('reg') or '').strip()
    if not msg_text:
        msg_text = str(data.get('text') or data.get('msg_text') or '').strip()
    if not label and data.get('label'):
        label = str(data.get('label') or '').strip()

    # C) Kontroll och avkodning av råa MIAM Base85-strängar (Label: MA eller T01/T02 Single Transfer)
    is_miam_packet = (
        (label.upper() == 'MA') or 
        msg_text.startswith('T01') or 
        msg_text.startswith('T02') or
        (isinstance(acars, dict) and bool(acars.get('miam')))
    )
    if is_miam_packet and msg_text:
        is_already_decoded = (
            is_miam and 
            not msg_text.startswith(('T01', 'T02', 'z!')) and 
            (';' in msg_text or 'PALAT' in msg_text or msg_text.startswith('[MIAM'))
        )
        if not is_already_decoded:
            decoded_try = decode_miam_base85(msg_text)
            if decoded_try:
                msg_text = decoded_try
                is_miam = True
            else:
                # Ofullständigt/fragmenterat paket (eller acars.more == True)
                # Krav 3: Ersätt Base85-vägg med snygg statusrad
                clean_raw = msg_text.strip()
                raw_len = len(clean_raw)
                preview = clean_raw[:16] + ('...' if raw_len > 16 else '')
                msg_text = f"[MIAM Komprimerad Telemetri] Krypterat/fragmenterat Airbus-datapaket ({raw_len} B, delpaket) ({preview})"
                is_miam = True

    # Fallback till rotnivå (t.ex. normaliserad JSON från router)
    if not flight:
        flight = str(data.get('flight') or '').strip().upper()
    if not reg:
        reg = str(data.get('tail') or data.get('reg') or '').strip()
    if not msg_text:
        msg_text = str(data.get('text') or data.get('msg_text') or '').strip()
    if not label and data.get('label'):
        label = str(data.get('label') or '').strip()

    # Rensa inledande punkter i reg (t.ex. ".OH-LWI" -> "OH-LWI")
    if reg:
        reg = re.sub(r'^\.+', '', reg).strip().upper()

    # Filter för länktest (Label Q0) om filter_links är på
    if filter_links and label.upper() == 'Q0':
        return None

    # C) CPDLC (Flygledningsmeddelanden):
    cpdlc_data = None
    if isinstance(avlc, dict) and isinstance(avlc.get('x25'), dict):
        x25 = avlc['x25']
        if isinstance(x25.get('clnp'), dict):
            cotp = x25['clnp'].get('cotp')
            if isinstance(cotp, dict):
                cpdlc_data = cotp.get('cpdlc')
    if not cpdlc_data and isinstance(avlc, dict):
        cpdlc_data = avlc.get('cpdlc')
    if not cpdlc_data and isinstance(acars, dict) and isinstance(acars.get('arinc622'), dict):
        cpdlc_data = acars['arinc622'].get('cpdlc')
    if not cpdlc_data:
        cpdlc_data = find_nested_key(data, 'cpdlc')

    cpdlc_text = format_cpdlc(cpdlc_data) if cpdlc_data else ""

    # Extrahera position och telemetri ur msg_text och vdl2
    pos_res = extract_position_and_telemetry(msg_text, vdl2_obj=vdl2)
    lat = pos_res['lat']
    lon = pos_res['lon']
    alt_ft = pos_res['alt_ft']
    dst_airport = pos_res.get('dst_airport')
    telemetry_summary = pos_res['telemetry_summary']
    telemetry_data = pos_res['telemetry']

    # 4. Filtrering av tomma paket (AVLC Receive Ready, COTP Ack etc.)
    has_payload = bool(msg_text or cpdlc_text or (lat is not None and lon is not None) or dst_airport)
    if not has_payload:
        if filter_empty:
            return None
        msg_text = f"VDL2 Signallänk: {src_type} ({src_addr or 'Okänd'}) -> {dst_type} ({dst_addr or 'Okänd'})"
    elif not msg_text and not cpdlc_text:
        if dst_airport:
            ap_desc = AIRPORT_MAP.get(dst_airport, '')
            ap_info = f" ({ap_desc})" if ap_desc else ""
            msg_text = f"Stationslänk upprättad (XID Handover)   Destination: {dst_airport}{ap_info}"
        elif lat is not None and lon is not None:
            msg_text = "Positionsrapport mottagen (XID Handover)"

    # 5. Konstruera Avsändare / Adress:
    addr_parts = []
    if flight:
        addr_parts.append(flight)
    if reg:
        addr_parts.append(f"({reg})")
    if src_addr:
        addr_parts.append(f"[{src_addr}]")

    if addr_parts:
        address = " ".join(addr_parts)
    else:
        address = "VDL2"

    # 6. Bestäm Alias (Flygbolagsnamn) och extrahera strukturerad metadata
    meta = extract_acars_metadata(avlc=avlc, acars=acars, vdl2_frame=vdl2)
    if not flight and meta.get('flight'):
        flight = meta['flight']
    if not reg and meta.get('reg'):
        reg = meta['reg']

    airline_name = meta.get('airline') or (lookup_airline(flight) if flight else "")
    alias = airline_name if airline_name else (reg if reg else (f"Flygplan {src_addr}" if src_addr else "VDL2 Flygplan"))

    station_name = meta.get('station') or ""
    ground_status = meta.get('ground_status') or ""
    label_desc = meta.get('label_desc') or lookup_label(label)

    # 7. Formatera meddelandesträng rent utan | och utan inledande [Label]-prefix
    message_lines = []
    if cpdlc_text:
        message_lines.append(f"CPDLC: {cpdlc_text}")

    if msg_text:
        if msg_text.startswith('[MIAM'):
            parsed_human = msg_text
        else:
            # Parsa genom acars_human_parser med strip_prefix=True för ren text
            parsed_human = parse_human_acars(msg_text, label=label, metadata=acars, strip_prefix=True)
        if parsed_human:
            message_lines.append(parsed_human)

    # Om FMS eller en regel extraherade eller uppdaterade dst_airport i acars-metadata
    if not dst_airport and isinstance(acars, dict) and acars.get('dst_airport'):
        dst_airport = str(acars['dst_airport']).strip().upper()

    # Kontrollera även i parse_vdl2_frame om Arrival ATIS (eller ATIS när Airborne) begärs
    m_atis_chk = re.search(r'/([A-Z]{4})\.TI2/(?:\d{1,4}\1)?([AD])?', msg_text, re.IGNORECASE)
    if m_atis_chk:
        atis_icao = m_atis_chk.group(1).upper()
        atis_type = (m_atis_chk.group(2) or '').upper()
        if atis_type == 'A' or (atis_type != 'D' and ground_status == 'Airborne'):
            dst_airport = atis_icao

    # Om en destinationsflygplats är känd (FMS, Arrival ATIS eller XID), uppdatera station_name så den gröna badgen visar rätt destination
    if dst_airport:
        station_name = format_airport(dst_airport)

    # Om ingen text genererades, men telemetrisammanfattning finns
    if not message_lines:
        if telemetry_summary:
            clean_summary = telemetry_summary.replace(' | ', '   ')
            message_lines.append(clean_summary)

    # Lägg till koordinater om de inte redan specificerats i meddelandet
    if lat is not None and lon is not None:
        coord_line = f"Position: {lat:.4f}, {lon:.4f}"
        joined_txt = "\n".join(message_lines)
        if "Position:" not in joined_txt and "Pos:" not in joined_txt and "Pos " not in joined_txt:
            message_lines.append(coord_line)

    full_message = "\n".join(message_lines).strip()
    if not full_message:
        if dst_airport:
            ap_desc = AIRPORT_MAP.get(dst_airport, '')
            ap_info = f" ({ap_desc})" if ap_desc else ""
            full_message = f"Stationslänk upprättad   Destination: {dst_airport}{ap_info}"
        elif lat is not None and lon is not None:
            full_message = f"Positionsrapport mottagen   Position: {lat:.4f}, {lon:.4f}"
        else:
            full_message = f"VDL2 Signallänk: {src_type} ({src_addr or 'Okänd'}) -> {dst_type} ({dst_addr or 'Okänd'})"

    bitrate_str = "VDL2-CPDLC" if cpdlc_text else ("VDL2-MIAM" if is_miam else ("VDL2-ACARS" if label else "VDL2"))

    return {
        'address': address,
        'alias': alias,
        'message': full_message,
        'frequency': freq_str,
        'protocol': 'VDL2',
        'bitrate': bitrate_str,
        'flight': flight,
        'reg': reg,
        'icao': src_addr,
        'station': station_name,
        'ground_status': ground_status,
        'label': label,
        'label_desc': label_desc,
        'lat': lat,
        'lon': lon,
        'alt_ft': alt_ft,
        'snr': snr_str,
        'snr_db': snr_db,
        'is_miam': is_miam,
        'telemetry': telemetry_data,
        'dst_airport': dst_airport
    }


class VDL2Receiver:
    """Hanterar TCP-klientanslutning till dumpvdl2 / acars_router och matar Pager-Monitor."""
    def __init__(self):
        self.host = '192.168.1.242'
        self.port = 15555
        self.filter_empty = True
        self.filter_links = False
        self.enabled = True
        self.thread = None
        self.running = False
        self.sock = None
        self.lock = threading.Lock()
        self.callback = None
        
        # Telemetri och statistik
        self.stats = {
            'connected': False,
            'host': self.host,
            'port': self.port,
            'packets_received': 0,
            'messages_decoded': 0,
            'last_message_time': None,
            'last_flight': None,
            'last_error': None,
            'status_text': 'Initierar...'
        }
        
        # Cache för duplikathantering
        self.recent_cache = {}
        self.cache_lock = threading.Lock()

    def set_callback(self, cb):
        self.callback = cb

    def start(self, host=None, port=None, filter_empty=None, filter_links=None, enabled=None):
        with self.lock:
            if host is not None: self.host = str(host).strip()
            if port is not None:
                try: self.port = int(port)
                except (ValueError, TypeError): self.port = 15555
            if filter_empty is not None:
                self.filter_empty = (str(filter_empty).lower() == 'true')
            if filter_links is not None:
                self.filter_links = (str(filter_links).lower() == 'true')
            if enabled is not None:
                self.enabled = (str(enabled).lower() == 'true')

            self.stats['host'] = self.host
            self.stats['port'] = self.port

            if not self.enabled:
                self.stats['connected'] = False
                self.stats['status_text'] = 'Inaktiverad i inställningar'
                logger.info("[VDL2] Mottagare är inaktiverad.")
                return

            if self.running:
                logger.info("[VDL2] Mottagaren körs redan.")
                return

            self.running = True
            self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="VDL2-Receiver-Thread")
            self.thread.start()
            logger.info(f"[VDL2] Startar mottagare mot {self.host}:{self.port}...")

    def stop(self):
        with self.lock:
            self.running = False
            self.stats['connected'] = False
            self.stats['status_text'] = 'Stoppad'
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
        logger.info("[VDL2] Mottagare stoppad.")

    def restart(self, host=None, port=None, filter_empty=None, filter_links=None, enabled=None):
        logger.info("[VDL2] Startar om mottagare...")
        self.stop()
        time.sleep(0.5)
        self.start(host=host, port=port, filter_empty=filter_empty, filter_links=filter_links, enabled=enabled)

    def get_status(self):
        with self.lock:
            return dict(self.stats)

    def _worker_loop(self):
        backoff = 3
        while self.running:
            try:
                self.stats['status_text'] = f"Ansluter till {self.host}:{self.port}..."
                logger.info(f"[VDL2] Försöker ansluta till tcp://{self.host}:{self.port}...")
                
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(15.0)
                s.connect((self.host, self.port))
                s.settimeout(None)  # Blockera vid läsning
                
                with self.lock:
                    self.sock = s
                    self.stats['connected'] = True
                    self.stats['status_text'] = f"Ansluten till {self.host}:{self.port}"
                    self.stats['last_error'] = None
                
                backoff = 3
                logger.info(f"[VDL2] Ansluten till dumpvdl2/acars_router på {self.host}:{self.port}!")
                
                file_obj = s.makefile('r', encoding='utf-8', errors='replace')
                for line in file_obj:
                    if not self.running:
                        break
                    line_str = line.strip()
                    if not line_str:
                        continue
                    
                    self.stats['packets_received'] += 1
                    try:
                        raw_json = json.loads(line_str)
                    except json.JSONDecodeError:
                        continue
                    
                    self._handle_frame(raw_json)

            except Exception as e:
                err_msg = str(e)
                with self.lock:
                    self.stats['connected'] = False
                    self.stats['last_error'] = err_msg
                    self.stats['status_text'] = f"Frånkopplad ({err_msg}). Försöker igen om {backoff}s..."
                logger.warning(f"[VDL2] Nätverksavbrott mot {self.host}:{self.port}: {err_msg}. Nytt försök om {backoff}s.")
            finally:
                with self.lock:
                    if self.sock:
                        try: self.sock.close()
                        except Exception: pass
                        self.sock = None

            # Paus med backoff vid fel
            for _ in range(backoff):
                if not self.running:
                    break
                time.sleep(1.0)
            backoff = min(backoff * 2, 30)

    def _handle_frame(self, raw_json):
        parsed = parse_vdl2_frame(raw_json, filter_empty=self.filter_empty, filter_links=self.filter_links)
        if not parsed:
            return

        address = parsed['address']
        message = parsed['message']
        alias = parsed['alias']
        freq = parsed['frequency']
        protocol_type = parsed['protocol']
        bitrate = parsed['bitrate']
        flight = parsed.get('flight')

        # Kontrollera om användaren konfigurerat ett specifikt alias i Pager-Monitor
        alias_info = get_alias_info(address)
        if not alias_info and flight:
            alias_info = get_alias_info(flight)
        if not alias_info and parsed.get('reg'):
            alias_info = get_alias_info(parsed.get('reg'))

        if alias_info and alias_info.get('alias'):
            alias = alias_info['alias']
            if alias_info.get('is_hidden'):
                return

        # Duplikathantering
        settings = get_settings()
        try:
            dup_window = int(settings.get('duplicate_window', '120'))
        except (ValueError, TypeError):
            dup_window = 120
        dup_handling = settings.get('duplicate_handling', 'merge')

        now = time.time()
        msg_key = (address, message)
        is_duplicate = False
        cached_entry = None

        with self.cache_lock:
            if msg_key in self.recent_cache:
                entry = self.recent_cache[msg_key]
                last_time = entry['time'] if isinstance(entry, dict) else entry
                if (now - last_time) <= dup_window:
                    is_duplicate = True
                    cached_entry = entry if isinstance(entry, dict) else {'time': last_time, 'id': None, 'repeat_count': 1}

            if len(self.recent_cache) > 500:
                cutoff = now - max(300, dup_window * 2)
                to_del = [k for k, v in self.recent_cache.items() if (v['time'] if isinstance(v, dict) else v) < cutoff]
                for k in to_del: del self.recent_cache[k]

        if is_duplicate and dup_handling == 'merge' and cached_entry and cached_entry.get('id'):
            cached_id = cached_entry['id']
            now_iso = datetime.now().isoformat()
            new_count = increment_message_repeat(cached_id, now_iso)
            cached_entry['time'] = now
            cached_entry['repeat_count'] = new_count
            logger.info(f"[VDL2] MERGED: Repeat count {new_count}x på ID {cached_id} ({address})")
            
            repeat_data = {
                'type': 'repeat_update',
                'id': cached_id,
                'repeat_count': new_count,
                'last_timestamp': now_iso,
                'frequency': freq,
                'address': address
            }
            if self.callback:
                try: self.callback(repeat_data)
                except Exception: pass
            return

        if is_duplicate and dup_handling == 'discard':
            return

        # Kontrollera larmord (endast på själva meddelandetexten med helordsmatchning)
        alert_match = check_alert_words(message)
        now_iso = datetime.now().isoformat()

        # Förbered metadata för databas, SSE och MQTT
        metadata = {
            'protocol': protocol_type,
            'bitrate': bitrate,
            'function': 1 if parsed.get('lat') else 0,
            'frequency': freq,
            'alert_word': alert_match['word'] if alert_match else None,
            'alert_color': alert_match['color'] if alert_match else None,
            'sdr_name': 'VDL2-Mätning',
            'is_duplicate': is_duplicate,
            'repeat_count': 1,
            'last_timestamp': now_iso,
            'flight': parsed.get('flight'),
            'reg': parsed.get('reg'),
            'icao': parsed.get('icao'),
            'station': parsed.get('station'),
            'ground_status': parsed.get('ground_status'),
            'label': parsed.get('label'),
            'label_desc': parsed.get('label_desc'),
            'lat': parsed.get('lat'),
            'lon': parsed.get('lon'),
            'alt_ft': parsed.get('alt_ft'),
            'snr': parsed.get('snr'),
            'is_miam': parsed.get('is_miam'),
            'telemetry': parsed.get('telemetry')
        }

        # Spara till databas
        msg_id, timestamp = save_message(
            address=address,
            message=message,
            alias=alias,
            function_code=1 if parsed.get('lat') else 0,
            bitrate=f"{protocol_type} {bitrate}".strip(),
            frequency=freq,
            is_duplicate=is_duplicate,
            repeat_count=1,
            last_timestamp=None,
            metadata=metadata
        )
        metadata['last_timestamp'] = timestamp

        with self.cache_lock:
            self.recent_cache[msg_key] = {
                'time': now,
                'id': msg_id,
                'repeat_count': 1
            }

        # Uppdatera intern statistik
        self.stats['messages_decoded'] += 1
        self.stats['last_message_time'] = timestamp
        if flight:
            self.stats['last_flight'] = flight
        elif parsed.get('reg'):
            self.stats['last_flight'] = parsed.get('reg')

        logger.info(f"[VDL2 DECODED] -> [{address}] {alias} | {message}")

        # Skicka till MQTT
        publish_message(address, message, timestamp, alias, metadata=metadata)

        # Skicka via SSE till webbklienter
        msg_data = {
            'type': 'message',
            'id': msg_id,
            'timestamp': timestamp,
            'address': address,
            'message': message,
            'alias': alias,
            'is_duplicate': is_duplicate,
            'repeat_count': 1,
            'last_timestamp': timestamp
        }
        msg_data.update(metadata)

        if self.callback:
            try:
                self.callback(msg_data)
            except Exception as e:
                logger.error(f"[VDL2] Fel vid anrop till klient-callback: {e}")

# Global singleton instans
vdl2_receiver = VDL2Receiver()

def init_vdl2(notify_callback=None):
    """Initierar VDL2-mottagaren från databasinställningar."""
    settings = get_settings()
    host = settings.get('vdl2_host', '192.168.1.242')
    port = settings.get('vdl2_port', '15555')
    filter_empty = settings.get('vdl2_filter_empty', 'true')
    filter_links = settings.get('vdl2_filter_links', 'false')
    enabled = settings.get('vdl2_enabled', 'true')

    if notify_callback:
        vdl2_receiver.set_callback(notify_callback)

    vdl2_receiver.start(host=host, port=port, filter_empty=filter_empty, filter_links=filter_links, enabled=enabled)

def restart_vdl2():
    """Startar om VDL2-mottagaren med uppdaterade inställningar."""
    settings = get_settings()
    vdl2_receiver.restart(
        host=settings.get('vdl2_host', '192.168.1.242'),
        port=settings.get('vdl2_port', '15555'),
        filter_empty=settings.get('vdl2_filter_empty', 'true'),
        filter_links=settings.get('vdl2_filter_links', 'false'),
        enabled=settings.get('vdl2_enabled', 'true')
    )

def get_vdl2_status():
    """Returnerar aktuell status och telemetri för VDL2."""
    return vdl2_receiver.get_status()

def send_test_vdl2_message():
    """Skapar och injicerar ett realistiskt testmeddelande för VDL2/ACARS i databasen och liveflödet."""
    test_frame = {
        "vdl2": {
            "freq": 136975000,
            "sig_level": -14.2,
            "noise_level": -46.5,
            "station": "SE-MINGLARN-ESSB-1",
            "avlc": {
                "src": { "addr": "461F50", "type": "Aircraft" },
                "dst": { "addr": "123456", "type": "Ground station" },
                "acars": {
                    "reg": ".OH-LWI",
                    "flight": "AY1338",
                    "label": "H1",
                    "msg_text": "POSN58525E018360,FL350,ARN,HEL"
                }
            }
        }
    }
    vdl2_receiver._handle_frame(test_frame)
    return {
        "status": "success",
        "message": "Syntetiskt VDL2-testmeddelande skickat (AY1338 / OH-LWI)",
        "address": "AY1338 (OH-LWI) [461F50]",
        "alias": "Finnair",
        "frequency": "136.975M"
    }
