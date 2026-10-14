import socket
import json
import threading
import time
import logging
import re
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

logger = logging.getLogger(__name__)

# Kända flygbolagsprefix (IATA & ICAO) för berikad visning i aliasfältet
AIRLINE_MAP = {
    'SAS': 'SAS Scandinavian Airlines',
    'SK': 'SAS Scandinavian Airlines',
    'NOZ': 'Norwegian Air Shuttle',
    'NAX': 'Norwegian Air Shuttle',
    'DY': 'Norwegian Air Shuttle',
    'NSZ': 'Norwegian Air Sweden',
    'D8': 'Norwegian Air Sweden',
    'FIN': 'Finnair',
    'AY': 'Finnair',
    'BAW': 'British Airways',
    'BA': 'British Airways',
    'DLH': 'Lufthansa',
    'LH': 'Lufthansa',
    'KLM': 'KLM Royal Dutch',
    'KL': 'KLM Royal Dutch',
    'RYR': 'Ryanair',
    'FR': 'Ryanair',
    'WZZ': 'Wizz Air',
    'W6': 'Wizz Air',
    'EJU': 'easyJet Europe',
    'EZY': 'easyJet',
    'U2': 'easyJet',
    'SWR': 'Swiss International',
    'LX': 'Swiss International',
    'AFR': 'Air France',
    'AF': 'Air France',
    'AUA': 'Austrian Airlines',
    'OS': 'Austrian Airlines',
    'BRX': 'Braathens Regional Airways',
    'TF': 'Braathens Regional Airways',
    'BTI': 'airBaltic',
    'BT': 'airBaltic',
    'THY': 'Turkish Airlines',
    'TK': 'Turkish Airlines',
    'QTR': 'Qatar Airways',
    'QR': 'Qatar Airways',
    'UAE': 'Emirates',
    'EK': 'Emirates',
    'ICE': 'Icelandair',
    'FI': 'Icelandair',
    'AMF': 'Amapola Flyg',
    'VKG': 'Sunclass Airlines',
    'TOM': 'TUI fly',
    'BLX': 'TUI fly Nordic',
    'UPS': 'UPS Airlines',
    'FDX': 'FedEx Express',
    'BCS': 'European Air Transport (DHL)',
    'BOX': 'AeroLogic (DHL)',
    'SWN': 'West Air Sweden',
    'SRK': 'Swedflight',
    'WIF': 'Widerøe'
}

# ACARS Label-koder och deras svenska förklaringar
ACARS_LABELS = {
    'SA': 'Länkstatus (Media Advisory)',
    'B9': 'Begäran om flygplatsväder (ATIS)',
    'A9': 'Flygplatsväder (ATIS)',
    'B6': 'Begäran om färdtillstånd (PDC/DCL)',
    'A6': 'Begäran om färdtillstånd (PDC/DCL)',
    'BA': 'Oceanic Clearance',
    'AA': 'Oceanic Clearance',
    '10': 'Positionsrapport',
    '14': 'ETA / Beräknad ankomst',
    '15': 'Positionsrapport (Start / Takeoff)',
    '16': 'Positionsrapport (Landning / Touchdown)',
    '20': 'Positionsrapport (Bränsle & Prestanda)',
    '21': 'Positionsrapport (Motorrapport)',
    '4J': 'Positionsrapport',
    'POS': 'Positionsrapport',
    'H1': 'FMS / Färddator-rapport',
    'MA': 'MIAM Komprimerad Telemetri',
    '80': 'Operativt meddelande / Dispatch (OUT)',
    '81': 'Operativt meddelande / Dispatch (OFF)',
    '82': 'Operativt meddelande / Dispatch (ON)',
    '83': 'Operativt meddelande / Dispatch (IN)',
    'RA': 'Operativt meddelande / Driftrapport',
    '5U': 'Väderbegäran / METAR',
    '57': 'Väderbegäran / METAR',
    'WX': 'Väderbegäran / METAR',
    '30': 'Väder / METAR / TAF',
    '44': 'Teknisk flygplansstatus',
    '4A': 'Motorövervakning (ECM)',
    '5D': 'Flygplatsväder (ATIS)',
    '5Z': 'Flygbolagsdata (Airline Designated)',
    'Q0': 'Länktest (ACARS Link Test)',
    'Q1': 'Avgångsrapport (OOOI)',
    'Q2': 'Ankomstrapport (OOOI)',
    '_d': 'Tom kvittens (ACK)',
    'SQ': 'Transponder / Squawk',
    '_': 'Flygledning (ATC)'
}
LABEL_MAP = ACARS_LABELS

# Kända ICAO-flygplatser och deras namn
AIRPORT_MAP = {
    'ESSA': 'Stockholm/Arlanda',
    'ESSB': 'Stockholm/Bromma',
    'ESKN': 'Stockholm/Skavsta',
    'ESGG': 'Göteborg/Landvetter',
    'ESMS': 'Malmö',
    'ESSV': 'Visby',
    'ESOW': 'Västerås',
    'ESCF': 'Linköping/Malmen',
    'ESNN': 'Sundsvall',
    'ESNU': 'Umeå',
    'ESPA': 'Luleå',
    'ESNZ': 'Åre/Östersund',
    'ESMQ': 'Kalmar',
    'ESNX': 'Arvidsjaur',
    'ESOE': 'Örebro',
    'ESOK': 'Karlstad',
    'EKCH': 'Köpenhamn/Kastrup',
    'EKBI': 'Billund',
    'EKYT': 'Aalborg',
    'ENGM': 'Oslo/Gardermoen',
    'ENBR': 'Bergen/Flesland',
    'ENZV': 'Stavanger/Sola',
    'ENVA': 'Trondheim/Værnes',
    'EFHK': 'Helsingfors/Vanda',
    'EFOU': 'Uleåborg',
    'EFRO': 'Rovaniemi',
    'EFTU': 'Åbo/Turku',
    'EETN': 'Tallinn',
    'EVRA': 'Riga',
    'EYVI': 'Vilnius',
    'EPWA': 'Warszawa/Chopin',
    'EPGD': 'Gdansk',
    'EDDF': 'Frankfurt',
    'EDDM': 'München',
    'EDDB': 'Berlin',
    'EDDH': 'Hamburg',
    'EHAM': 'Amsterdam/Schiphol',
    'EBBR': 'Bryssel',
    'EGLL': 'London/Heathrow',
    'EGKK': 'London/Gatwick',
    'EGSS': 'London/Stansted',
    'EGGW': 'London/Luton',
    'EGCC': 'Manchester',
    'EIDW': 'Dublin',
    'LFPG': 'Paris/CDG',
    'LFPO': 'Paris/Orly',
    'LFMN': 'Nice',
    'LSZH': 'Zürich',
    'LSGG': 'Genève',
    'LOWW': 'Wien',
    'LIRF': 'Rom/Fiumicino',
    'LIMC': 'Milano/Malpensa',
    'LEMD': 'Madrid/Barajas',
    'LEBL': 'Barcelona',
    'LEPA': 'Palma de Mallorca',
    'LPPT': 'Lissabon',
    'LGAV': 'Aten',
    'LTFM': 'Istanbul'
}

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
        ap_name = AIRPORT_MAP.get(icao)
        ap_disp = f"{icao} ({ap_name})" if ap_name else icao
        if act == 'TI2':
            desc = f"Begär aktuellt flygplatsväder (ATIS) för {ap_disp}"
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
        if m_icao and m_icao.group(1) in AIRPORT_MAP:
            icao = m_icao.group(1)
            ap_name = AIRPORT_MAP[icao]
            if lbl == 'B9':
                return f"Begär flygplatsväder (ATIS) för {icao} ({ap_name}) | Rådata: {txt}"
            else:
                return f"Flygplatsväder (ATIS) för {icao} ({ap_name}) | {txt}"

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

    return txt

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
        # Format med decimalpunkt: 5912.4N 01805.2E eller N5912.4 E01805.2
        m_dm_dec = re.search(r'([0-9]{2})([0-9]{2}\.[0-9]+)\s*([NS])\s*[/,\s]?\s*([0-9]{3})([0-9]{2}\.[0-9]+)\s*([EW])', raw_text, re.IGNORECASE)
        if not m_dm_dec:
            m_dm_dec = re.search(r'([NS])\s*([0-9]{2})([0-9]{2}\.[0-9]+)\s*[/,\s]?\s*([EW])\s*([0-9]{3})([0-9]{2}\.[0-9]+)', raw_text, re.IGNORECASE)
            if m_dm_dec:
                try:
                    lat_ns = m_dm_dec.group(1).upper()
                    lat_deg = int(m_dm_dec.group(2))
                    lat_min = float(m_dm_dec.group(3))
                    lat = (lat_deg + lat_min / 60.0) * (-1 if lat_ns == 'S' else 1)

                    lon_ew = m_dm_dec.group(4).upper()
                    lon_deg = int(m_dm_dec.group(5))
                    lon_min = float(m_dm_dec.group(6))
                    lon = (lon_deg + lon_min / 60.0) * (-1 if lon_ew == 'W' else 1)
                    res['lat'], res['lon'] = round(lat, 4), round(lon, 4)
                except (ValueError, TypeError):
                    pass
        else:
            try:
                lat_deg = int(m_dm_dec.group(1))
                lat_min = float(m_dm_dec.group(2))
                lat_ns = m_dm_dec.group(3).upper()
                lat = (lat_deg + lat_min / 60.0) * (-1 if lat_ns == 'S' else 1)

                lon_deg = int(m_dm_dec.group(4))
                lon_min = float(m_dm_dec.group(5))
                lon_ew = m_dm_dec.group(6).upper()
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
            r_str = f"Rutt: {orig} -> {dest}"
            if res['telemetry_summary']:
                if r_str not in res['telemetry_summary']:
                    res['telemetry_summary'] += f" | {r_str}"
            else:
                res['telemetry_summary'] = r_str

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

            # XID vdl_params -> dst_airport
            vdl_params = xid.get('vdl_params', {}) if isinstance(xid.get('vdl_params'), dict) else {}
            dst_ap = vdl_params.get('dst_airport') or xid.get('dst_airport')
            if dst_ap:
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
                            miam_text = sub_acars.get('msg_text')
                            if miam_text:
                                msg_text = str(miam_text).strip()
                                is_miam = True
                                if not flight and sub_acars.get('flight'):
                                    flight = str(sub_acars.get('flight')).strip().upper()
                                if not reg and sub_acars.get('reg'):
                                    reg = str(sub_acars.get('reg')).strip()
                                if sub_acars.get('label'):
                                    label = str(sub_acars.get('label')).strip()

        # B) Om ingen MIAM-text hittades: Använd vanlig ACARS
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
            msg_text = f"[XID Handover] Stationslänk upprättad | Destination: {dst_airport}{ap_info}"
        elif lat is not None and lon is not None:
            msg_text = "[XID Positionsrapport] Flygplansposition mottagen via stationslänk"

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

    # 6. Bestäm Alias (Flygbolagsnamn)
    airline_name = ""
    if flight:
        p3 = flight[:3]
        if p3 in AIRLINE_MAP:
            airline_name = AIRLINE_MAP[p3]
        else:
            p2 = flight[:2]
            if p2 in AIRLINE_MAP:
                airline_name = AIRLINE_MAP[p2]

    alias = airline_name if airline_name else (reg if reg else (f"Flygplan {src_addr}" if src_addr else "VDL2 Flygplan"))

    # 7. Formatera meddelandesträng med etiketter och telemetri
    humanized_msg = humanize_acars_message(label, msg_text, acars_dict=acars) if msg_text else ""

    formatted_msg_parts = []
    if cpdlc_text:
        formatted_msg_parts.append(f"[CPDLC] {cpdlc_text}")

    if humanized_msg:
        label_desc = ACARS_LABELS.get(label)
        if label_desc:
            label_prefix = f"[{label}: {label_desc}] "
        elif label:
            label_prefix = f"[{label}] "
        else:
            label_prefix = ""

        if is_miam:
            label_prefix = "[MIAM Airbus] " + label_prefix
        formatted_msg_parts.append(f"{label_prefix}{humanized_msg}")

    if telemetry_summary:
        if telemetry_summary not in humanized_msg:
            formatted_msg_parts.append(f"[{telemetry_summary}]")

    full_message = " | ".join(formatted_msg_parts) if formatted_msg_parts else (humanized_msg or msg_text)
    
    if lat is not None and lon is not None:
        coord_str = f"Lat: {lat:.4f}, Lon: {lon:.4f}"
        if coord_str not in full_message:
            full_message += f" | {coord_str}"

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
        'lat': lat,
        'lon': lon,
        'alt_ft': alt_ft,
        'snr': snr_str,
        'snr_db': snr_db,
        'is_miam': is_miam,
        'label': label,
        'telemetry': telemetry_data
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

        # Spara till databas och trigga larmord
        alert_match = check_alert_words(message)
        msg_id, timestamp = save_message(
            address=address,
            message=message,
            alias=alias,
            function_code=1 if parsed.get('lat') else 0,
            bitrate=f"{protocol_type} {bitrate}".strip(),
            frequency=freq,
            is_duplicate=is_duplicate,
            repeat_count=1,
            last_timestamp=None
        )

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
            'last_timestamp': timestamp,
            'flight': parsed.get('flight'),
            'reg': parsed.get('reg'),
            'icao': parsed.get('icao'),
            'lat': parsed.get('lat'),
            'lon': parsed.get('lon'),
            'alt_ft': parsed.get('alt_ft'),
            'snr': parsed.get('snr'),
            'is_miam': parsed.get('is_miam'),
            'telemetry': parsed.get('telemetry')
        }

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
