import socket
import json
import threading
import time
import logging
import re
from datetime import datetime
from database import (
    save_message, get_settings, check_alert_words
)

try:
    from mqtt_client import publish_message
except ImportError:
    def publish_message(*args, **kwargs):
        pass

try:
    from acars_human_parser import (
        lookup_label, parse_human_acars, ACARS_LABELS
    )
except ImportError:
    def lookup_label(l): return ""
    def parse_human_acars(m, **kw): return m
    ACARS_LABELS = {}

logger = logging.getLogger(__name__)

# Omfattande flygbolagsordbok (ICAO 3-bokstav och IATA 2-bokstav)
HFDL_AIRLINES = {
    'CCA': 'Air China', 'CA': 'Air China',
    'SAS': 'SAS Scandinavian Airlines', 'SK': 'SAS Scandinavian Airlines',
    'THY': 'Turkish Airlines', 'TK': 'Turkish Airlines',
    'DLH': 'Lufthansa', 'LH': 'Lufthansa',
    'BAW': 'British Airways', 'BA': 'British Airways',
    'UAL': 'United Airlines', 'UA': 'United Airlines',
    'DAL': 'Delta Air Lines', 'DL': 'Delta Air Lines',
    'AAL': 'American Airlines', 'AA': 'American Airlines',
    'AFR': 'Air France', 'AF': 'Air France',
    'KLM': 'KLM', 'KL': 'KLM',
    'QTR': 'Qatar Airways', 'QR': 'Qatar Airways',
    'UAE': 'Emirates', 'EK': 'Emirates',
    'SIA': 'Singapore Airlines', 'SQ': 'Singapore Airlines',
    'FIN': 'Finnair', 'AY': 'Finnair',
    'VIR': 'Virgin Atlantic', 'VS': 'Virgin Atlantic',
    'CPA': 'Cathay Pacific', 'CX': 'Cathay Pacific',
    'ANA': 'All Nippon Airways', 'NH': 'All Nippon Airways',
    'JAL': 'Japan Airlines', 'JL': 'Japan Airlines',
    'QFA': 'Qantas', 'QF': 'Qantas',
    'ANZ': 'Air New Zealand', 'NZ': 'Air New Zealand',
    'ACA': 'Air Canada', 'AC': 'Air Canada',
    'ETD': 'Etihad Airways', 'EY': 'Etihad Airways',
    'ETH': 'Ethiopian Airlines', 'ET': 'Ethiopian Airlines',
    'CES': 'China Eastern', 'MU': 'China Eastern',
    'CSN': 'China Southern', 'CZ': 'China Southern',
    'CHH': 'Hainan Airlines', 'HU': 'Hainan Airlines',
    'KAL': 'Korean Air', 'KE': 'Korean Air',
    'AAR': 'Asiana Airlines', 'OZ': 'Asiana Airlines',
    'SWR': 'Swiss International', 'LX': 'Swiss International',
    'AUA': 'Austrian Airlines', 'OS': 'Austrian Airlines',
    'IBE': 'Iberia', 'IB': 'Iberia',
    'TAP': 'TAP Air Portugal', 'TP': 'TAP Air Portugal',
    'EIN': 'Aer Lingus', 'EI': 'Aer Lingus',
    'WZZ': 'Wizz Air', 'W6': 'Wizz Air',
    'RYR': 'Ryanair', 'FR': 'Ryanair',
    'EZY': 'easyJet', 'U2': 'easyJet', 'EJU': 'easyJet Europe',
    'ICE': 'Icelandair', 'FI': 'Icelandair',
    'NOZ': 'Norwegian', 'DY': 'Norwegian', 'D8': 'Norwegian', 'NSZ': 'Norwegian',
    'BTI': 'airBaltic', 'BT': 'airBaltic',
    'LOT': 'LOT Polish Airlines', 'LO': 'LOT Polish Airlines',
    'AIC': 'Air India', 'AI': 'Air India'
}

def lookup_airline(flight_code):
    """Slår upp flygbolag ur flightnummer (t.ex. CCA876 -> Air China, SK0949 -> SAS)."""
    if not flight_code:
        return ""
    f = str(flight_code).strip().upper()
    # Försök först med 3 tecken (ICAO)
    if len(f) >= 3 and f[:3] in HFDL_AIRLINES:
        return HFDL_AIRLINES[f[:3]]
    # Sedan med 2 tecken (IATA)
    if len(f) >= 2 and f[:2] in HFDL_AIRLINES:
        return HFDL_AIRLINES[f[:2]]
    return ""

# Smart minnes-cache för flygplansdata (HFDL_AC_CACHE) med TTL 1800s
HFDL_CACHE_TTL = 1800
HFDL_AC_CACHE = {}
HFDL_AC_LOCK = threading.Lock()

def clean_reg_str(reg):
    """Tar bort inledande punkter och mellanslag från flygplansregistreringar."""
    if not reg:
        return ""
    return str(reg).strip().lstrip('.').upper()

def cache_ac_info(reg=None, flight=None, icao=None, gs_id=None, ac_id=None, ac_info=None, pos=None):
    """Sparar eller uppdaterar flygplansinformation i cachen nycklad på reg, flight, icao och (gs_id, ac_id)."""
    clean_reg = clean_reg_str(reg)
    flight_str = str(flight).strip().upper() if flight else ""
    icao_str = str(icao).strip().upper() if icao else ""
    
    if not (clean_reg or flight_str or icao_str or (gs_id is not None and ac_id is not None)):
        return

    now = time.time()
    info_dict = {
        'timestamp': now
    }

    if isinstance(ac_info, dict):
        if ac_info.get('icao'): info_dict['icao'] = str(ac_info['icao']).strip().upper()
        if ac_info.get('regnr'): info_dict['reg'] = clean_reg_str(ac_info['regnr'])
        if ac_info.get('model'): info_dict['model'] = str(ac_info['model']).strip()
        if ac_info.get('typecode'): info_dict['typecode'] = str(ac_info['typecode']).strip()
        if ac_info.get('manuf'): info_dict['manuf'] = str(ac_info['manuf']).strip()
        if ac_info.get('owner'): info_dict['owner'] = str(ac_info['owner']).strip()

    if clean_reg and 'reg' not in info_dict: info_dict['reg'] = clean_reg
    if flight_str: info_dict['flight'] = flight_str
    if icao_str and 'icao' not in info_dict: info_dict['icao'] = icao_str

    if isinstance(pos, dict):
        try:
            info_dict['lat'] = float(pos.get('lat'))
            info_dict['lon'] = float(pos.get('lon'))
        except (ValueError, TypeError):
            pass

    with HFDL_AC_LOCK:
        # Hämta befintlig post om någon finns för att sammanfoga
        existing = {}
        for key in (clean_reg, flight_str, icao_str, (gs_id, ac_id) if gs_id is not None and ac_id is not None else None):
            if key and key in HFDL_AC_CACHE:
                cand = HFDL_AC_CACHE[key]
                if now - cand.get('timestamp', 0) <= HFDL_CACHE_TTL:
                    existing.update(cand)

        merged = dict(existing)
        merged.update({k: v for k, v in info_dict.items() if v is not None and v != ""})
        merged['timestamp'] = now

        # Spara på alla relevanta nycklar
        if clean_reg: HFDL_AC_CACHE[clean_reg] = merged
        if merged.get('reg'): HFDL_AC_CACHE[merged['reg']] = merged
        if flight_str: HFDL_AC_CACHE[flight_str] = merged
        if merged.get('flight'): HFDL_AC_CACHE[merged['flight']] = merged
        if icao_str: HFDL_AC_CACHE[icao_str] = merged
        if merged.get('icao'): HFDL_AC_CACHE[merged['icao']] = merged
        if gs_id is not None and ac_id is not None:
            HFDL_AC_CACHE[(gs_id, ac_id)] = merged

        # Rensa gamla poster om cachen överstiger 2000 poster
        if len(HFDL_AC_CACHE) > 2000:
            expired = [k for k, v in HFDL_AC_CACHE.items() if now - v.get('timestamp', 0) > HFDL_CACHE_TTL]
            for k in expired:
                HFDL_AC_CACHE.pop(k, None)

def lookup_ac_info(reg=None, flight=None, icao=None, gs_id=None, ac_id=None):
    """Slår upp flygplansinformation ur cachen."""
    clean_reg = clean_reg_str(reg)
    flight_str = str(flight).strip().upper() if flight else ""
    icao_str = str(icao).strip().upper() if icao else ""
    pair = (gs_id, ac_id) if gs_id is not None and ac_id is not None else None

    now = time.time()
    with HFDL_AC_LOCK:
        for key in (clean_reg, flight_str, icao_str, pair):
            if key and key in HFDL_AC_CACHE:
                entry = HFDL_AC_CACHE[key]
                if now - entry.get('timestamp', 0) <= HFDL_CACHE_TTL:
                    return dict(entry)
    return None

def cache_hfdl_ac(reg=None, flight_id=None, icao=None, model=None, typecode=None, owner=None, pos=None, gs_id=None, ac_id=None):
    """Hjälpfunktion för att direkt cacha flygplansinfo."""
    ac_info = {}
    if reg: ac_info['regnr'] = reg
    if icao: ac_info['icao'] = icao
    if model: ac_info['model'] = model
    if typecode: ac_info['typecode'] = typecode
    if owner: ac_info['owner'] = owner

    pos_dict = None
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        pos_dict = {'lat': pos[0], 'lon': pos[1]}
    elif isinstance(pos, dict):
        pos_dict = pos

    cache_ac_info(reg=reg, flight=flight_id, icao=icao, gs_id=gs_id, ac_id=ac_id, ac_info=ac_info, pos=pos_dict)

def get_cached_hfdl_ac(reg=None, flight_id=None, icao=None, gs_id=None, ac_id=None):
    """Hjälpfunktion för att hämta cachad flygplansinfo."""
    return lookup_ac_info(reg=reg, flight=flight_id, icao=icao, gs_id=gs_id, ac_id=ac_id)


def format_freq_val(raw_freq):
    """Extraherar numeriskt frekvensvärde och formaterar till rent tal eller en decimal."""
    if raw_freq is None:
        return ""
    if isinstance(raw_freq, dict):
        raw_freq = raw_freq.get("freq", raw_freq.get("frequency", ""))
    try:
        f_num = float(raw_freq)
        if f_num > 100000:
            f_num = f_num / 1000.0
        if f_num.is_integer():
            return f"{int(f_num)}"
        return f"{f_num:.1f}"
    except (ValueError, TypeError):
        return str(raw_freq)

def format_hfdl_freq(raw_freq):
    """Konverterar frekvens i Hz eller dict till kHz-sträng (t.ex. 8942000 -> '8942 kHz', 8843.0 -> '8843 kHz')."""
    v = format_freq_val(raw_freq)
    return f"{v} kHz" if v else ""

def format_freq_list_str(freq_list):
    """Formaterar en lista med frekvenser, t.ex. [{'freq': 8942.0}, {'freq': 5547.0}] -> '8942, 5547 kHz'."""
    if not isinstance(freq_list, list) or not freq_list:
        return ""
    parts = []
    for item in freq_list:
        fv = format_freq_val(item)
        if fv:
            parts.append(fv)
    if not parts:
        return ""
    return f"{', '.join(parts)} kHz"

def format_hfdl_time(t_val):
    """Formaterar tid (antingen dict {'hour': 10, 'min': 26, 'sec': 15} eller sträng)."""
    if isinstance(t_val, dict):
        h = t_val.get("hour", 0)
        m = t_val.get("min", t_val.get("minute", 0))
        s = t_val.get("sec", t_val.get("second", 0))
        return f"{h:02d}:{m:02d}:{s:02d}"
    return str(t_val) if t_val else datetime.utcnow().strftime("%H:%M:%S")

def parse_hfdl_frame(payload, only_messages=True):
    """
    Parsar ett dumphfdl JSON-paket och returnerar en formaterad dict
    eller None om paketet filtreras bort.
    """
    if not isinstance(payload, dict):
        return None

    hfdl = payload.get("hfdl", payload) if isinstance(payload.get("hfdl"), dict) else payload

    # 1. Frekvens, Bitrate och SNR
    raw_freq = hfdl.get("freq")
    freq_str = format_hfdl_freq(raw_freq)

    bit_rate = hfdl.get("bit_rate")
    bitrate_str = f"HFDL-{bit_rate}bps" if bit_rate is not None else "HFDL"

    sig_level = hfdl.get("sig_level")
    noise_level = hfdl.get("noise_level")
    snr_str = ""
    if sig_level is not None and noise_level is not None:
        try:
            snr_val = float(sig_level) - float(noise_level)
            snr_str = f"+{snr_val:.1f} dB" if snr_val >= 0 else f"{snr_val:.1f} dB"
        except (ValueError, TypeError):
            pass

    # 2. Protokollstrukturer: SPDU, LPDU, HFNPDU, ACARS, AC_INFO
    spdu = hfdl.get("spdu") if isinstance(hfdl.get("spdu"), dict) else {}
    lpdu = hfdl.get("lpdu") if isinstance(hfdl.get("lpdu"), dict) else {}
    hfnpdu = lpdu.get("hfnpdu") if isinstance(lpdu.get("hfnpdu"), dict) else (hfdl.get("hfnpdu") if isinstance(hfdl.get("hfnpdu"), dict) else {})
    ac_info = lpdu.get("ac_info") if isinstance(lpdu.get("ac_info"), dict) else (hfdl.get("ac_info") if isinstance(hfdl.get("ac_info"), dict) else {})
    acars = hfnpdu.get("acars") if isinstance(hfnpdu.get("acars"), dict) else (lpdu.get("acars") if isinstance(lpdu.get("acars"), dict) else (hfdl.get("acars") if isinstance(hfdl.get("acars"), dict) else {}))

    # Filtrering för endast meningsfulla meddelanden
    is_squitter_only = (spdu and not lpdu and not hfnpdu and not acars and not ac_info)
    is_empty_lpdu = (lpdu and not hfnpdu and not acars and not ac_info)
    if only_messages and (is_squitter_only or is_empty_lpdu):
        return None

    # Hämta grundläggande adresseringsfält
    lpdu_src = lpdu.get("src", {}) if isinstance(lpdu.get("src"), dict) else {}
    lpdu_dst = lpdu.get("dst", {}) if isinstance(lpdu.get("dst"), dict) else {}
    gs_id = lpdu_dst.get("id") if lpdu_dst.get("type") == "Ground station" else (lpdu_src.get("id") if lpdu_src.get("type") == "Ground station" else None)
    ac_id = lpdu_src.get("id") if lpdu_src.get("type") == "Aircraft" else (lpdu_dst.get("id") if lpdu_dst.get("type") == "Aircraft" else None)

    gs_name = ""
    if lpdu_dst.get("name"): gs_name = str(lpdu_dst["name"]).strip()
    elif lpdu_src.get("name"): gs_name = str(lpdu_src["name"]).strip()
    elif isinstance(hfnpdu.get("gs"), dict) and hfnpdu.get("gs", {}).get("name"):
        gs_name = str(hfnpdu["gs"]["name"]).strip()

    # Extrahera råa identifierare
    flight_id = str(hfnpdu.get("flight_id") or acars.get("flight") or "").strip().upper()
    reg = clean_reg_str(ac_info.get("regnr") or acars.get("reg"))
    icao = str(ac_info.get("icao") or "").strip().upper()
    ac_model = str(ac_info.get("model") or "").strip()
    ac_typecode = str(ac_info.get("typecode") or "").strip()
    owner = str(ac_info.get("owner") or "").strip()

    # Position
    pos_obj = hfnpdu.get("pos") if isinstance(hfnpdu.get("pos"), dict) else (lpdu.get("pos") if isinstance(lpdu.get("pos"), dict) else (hfdl.get("pos") if isinstance(hfdl.get("pos"), dict) else {}))
    lat, lon = None, None
    if isinstance(pos_obj, dict):
        try:
            if "lat" in pos_obj and "lon" in pos_obj:
                lat = round(float(pos_obj["lat"]), 5)
                lon = round(float(pos_obj["lon"]), 5)
        except (ValueError, TypeError):
            pass

    # Spara/uppdatera cachen om vi har ac_info eller position
    if ac_info or pos_obj or flight_id or reg:
        cache_ac_info(
            reg=reg, flight=flight_id, icao=icao,
            gs_id=gs_id, ac_id=ac_id,
            ac_info=ac_info, pos=pos_obj
        )

    # Om paketet saknar detaljerad flygplansinfo: berika från cachen
    if not (ac_model and owner and icao):
        cached = lookup_ac_info(reg=reg, flight=flight_id, icao=icao, gs_id=gs_id, ac_id=ac_id)
        if cached:
            if not reg and cached.get('reg'): reg = cached['reg']
            if not flight_id and cached.get('flight'): flight_id = cached['flight']
            if not icao and cached.get('icao'): icao = cached['icao']
            if not ac_model and cached.get('model'): ac_model = cached['model']
            if not ac_typecode and cached.get('typecode'): ac_typecode = cached['typecode']
            if not owner and cached.get('owner'): owner = cached['owner']
            if (lat is None or lon is None) and cached.get('lat') is not None and cached.get('lon') is not None:
                lat = cached['lat']
                lon = cached['lon']

    # Rå JSON för toggle-box
    try:
        raw_json_str = json.dumps(payload, ensure_ascii=False)
    except Exception:
        raw_json_str = str(payload)

    # Identifiera pakettyp
    hfnpdu_type = hfnpdu.get("type", {}) if isinstance(hfnpdu.get("type"), dict) else {}
    hfnpdu_type_id = hfnpdu_type.get("id")
    hfnpdu_type_name = str(hfnpdu_type.get("name") or "").strip()
    lpdu_type = lpdu.get("type", {}) if isinstance(lpdu.get("type"), dict) else {}
    lpdu_type_name = str(lpdu_type.get("name") or "").strip()

    body_lines = []
    hfdl_badge_type = hfnpdu_type_name or lpdu_type_name or "HFDL"

    # Pakettyp A: Frequency data (hfnpdu.type.id == 213)
    if hfnpdu_type_id == 213 or "frequency" in hfnpdu_type_name.lower():
        hfdl_badge_type = "Frequency data"
        lp_desc = f" ({lpdu_type_name})" if lpdu_type_name else ""
        flight_disp = flight_id or "-"
        model_disp = ac_model or ac_typecode or "Okänt flygplan"
        reg_disp = f" ({reg})" if reg else ""
        gs_disp = gs_name or "-"

        time_val = format_hfdl_time(hfnpdu.get("utc_time") or hfnpdu.get("time"))
        body_lines.append(f"[HFDL Frekvens- & Hörbarhetsrapport{lp_desc}] Flight: {flight_disp} | Flygplan: {model_disp}{reg_disp} | Markstation: {gs_disp}")

        pos_part = f"Position: {lat:.4f}, {lon:.4f} | " if lat is not None and lon is not None else ""
        body_lines.append(f"{pos_part}Tid: {time_val} UTC")

        # Lista markstationer ur freq_data
        freq_data = hfnpdu.get("freq_data")
        if isinstance(freq_data, list) and freq_data:
            for item in freq_data:
                if not isinstance(item, dict):
                    continue
                item_gs = item.get("gs", {}) if isinstance(item.get("gs"), dict) else {}
                item_gs_name = item_gs.get("name") or f"GS #{item_gs.get('id', '?')}"
                heard = item.get("heard_on_freqs", [])
                listening = item.get("listening_on_freqs", [])

                if heard:
                    h_str = format_freq_list_str(heard)
                    l_str = format_freq_list_str(listening)
                    line_str = f"Hörd GS: {item_gs_name} ({h_str})"
                    if l_str:
                        line_str += f" [Lyssnar: {l_str}]"
                    body_lines.append(line_str)
                else:
                    cnt = len(listening)
                    body_lines.append(f"Lyssnar GS: {item_gs_name} ({cnt} frekv)")

    # Pakettyp B: Performance data (hfnpdu.type.id == 209)
    elif hfnpdu_type_id == 209 or "performance" in hfnpdu_type_name.lower():
        hfdl_badge_type = "Performance data"
        flight_disp = flight_id or "-"
        gs_disp = gs_name or "-"
        time_val = format_hfdl_time(hfnpdu.get("time") or hfnpdu.get("utc_time"))
        body_lines.append(f"[HFDL Prestanda- & Positionsrapport] Flight: {flight_disp} | Markstation: {gs_disp} | Tid: {time_val} UTC")

        leg_num = hfnpdu.get("flight_leg_num", 0)
        freq_info = hfnpdu.get("frequency", {}) if isinstance(hfnpdu.get("frequency"), dict) else {}
        active_freq_str = format_hfdl_freq(freq_info.get("freq") or raw_freq)

        pos_part = f"Position: {lat:.4f}, {lon:.4f} | " if lat is not None and lon is not None else ""
        body_lines.append(f"{pos_part}Leg: #{leg_num} | Aktiv HF-kanal: {active_freq_str}")

        pdu_stats = hfnpdu.get("pdu_stats", {}) if isinstance(hfnpdu.get("pdu_stats"), dict) else {}
        rx_pkts = pdu_stats.get("rx_packets", {}) if isinstance(pdu_stats.get("rx_packets"), dict) else pdu_stats
        rx_300 = rx_pkts.get("300bps", pdu_stats.get("rx_300", 0))
        rx_600 = rx_pkts.get("600bps", pdu_stats.get("rx_600", 0))
        rx_1200 = rx_pkts.get("1200bps", pdu_stats.get("rx_1200", 0))
        rx_1800 = rx_pkts.get("1800bps", pdu_stats.get("rx_1800", 0))
        spdus_ok = pdu_stats.get("spdus_rx_ok_cnt", pdu_stats.get("spdu_rx_ok", 0))
        spdus_missed = pdu_stats.get("spdus_missed_cnt", pdu_stats.get("spdu_missed", 0))

        cause_obj = hfnpdu.get("last_freq_change_cause", {})
        cause_desc = cause_obj.get("descr", "Normal") if isinstance(cause_obj, dict) else str(cause_obj or "Normal")

        body_lines.append(
            f"Paketstatistik (RX OK): 300bps: {rx_300}, 600bps: {rx_600}, 1200bps: {rx_1200}, 1800bps: {rx_1800} | "
            f"Squitter OK: {spdus_ok} (Missade: {spdus_missed}) | Frekvensbyte: {cause_desc}"
        )

    # Pakettyp C: Kapslad ACARS (hfnpdu.acars eller acars rot)
    elif acars:
        label = str(acars.get("label") or "").strip().upper()
        raw_desc = lookup_label(label) or ACARS_LABELS.get(label, "")
        if label == 'Q0':
            label_desc = "ACARS Länkbekräftelse"
        else:
            label_desc = raw_desc
        label_disp = f"Label: {label}" + (f" ({label_desc})" if label_desc else "")
        hfdl_badge_type = f"ACARS {label}" if label else "ACARS"

        flight_disp = flight_id or "-"
        reg_disp = reg or "-"
        gs_disp = gs_name or "-"
        blk_id = acars.get("blk_id", "")
        msg_num = acars.get("msg_num", "")
        msg_seq = acars.get("msg_num_seq", "")
        msg_tag = f" (Msg: {msg_num}{msg_seq})" if msg_num else ""
        block_part = f" | Block: {blk_id}{msg_tag}" if blk_id else ""

        raw_msg_text = str(acars.get("msg_text") or "").strip()
        header_line = f"[HFDL ACARS / {label_disp}] Flight: {flight_disp} | Reg: {reg_disp} | Markstation: {gs_disp}{block_part}"
        body_lines.append(header_line)

        if raw_msg_text:
            human_text = parse_human_acars(raw_msg_text, label=label)
            body_lines.append(human_text)

    # Pakettyp D: Allmän HFNPDU / LPDU (t.ex. Logon request, Logon resume utan freq_data etc.)
    else:
        type_title = hfnpdu_type_name or lpdu_type_name or "Datalänk"
        flight_disp = flight_id or "-"
        reg_disp = f" ({reg})" if reg else ""
        gs_disp = gs_name or "-"
        body_lines.append(f"[HFDL {type_title}] Flight: {flight_disp}{reg_disp} | Markstation: {gs_disp}")
        if lat is not None and lon is not None:
            body_lines.append(f"Position: {lat:.4f}, {lon:.4f}")

    message_body = "\n".join(body_lines)
    full_message = f"{message_body}\nRådata: {raw_json_str}"

    # Bestäm Address och Alias
    if flight_id and reg and icao:
        address = f"{flight_id} ({reg}) [{icao}]"
    elif flight_id and reg:
        address = f"{flight_id} ({reg})"
    elif flight_id:
        address = flight_id
    elif reg and icao:
        address = f"{reg} [{icao}]"
    elif reg:
        address = reg
    elif icao:
        address = icao
    elif gs_name:
        address = f"GS: {gs_name}"
    else:
        address = "HFDL"

    alias = ""
    if owner:
        alias = owner
    elif flight_id:
        alias = lookup_airline(flight_id)
    elif reg:
        alias = lookup_airline(reg)

    # Metadata
    metadata = {
        'protocol': 'HFDL',
        'frequency': freq_str,
        'bitrate': bitrate_str,
        'snr': snr_str
    }
    if reg: metadata['reg'] = reg
    if flight_id: metadata['flight'] = flight_id
    if icao: metadata['icao'] = icao
    if ac_model: metadata['ac_model'] = ac_model
    if ac_typecode: metadata['typecode'] = ac_typecode
    if gs_name: metadata['gs_name'] = gs_name
    if hfdl_badge_type: metadata['hfdl_type'] = hfdl_badge_type

    if acars:
        lbl = str(acars.get("label") or "").strip().upper()
        if lbl:
            metadata['label'] = lbl
            lbl_desc = "ACARS Länkbekräftelse" if lbl == 'Q0' else (lookup_label(lbl) or ACARS_LABELS.get(lbl, ""))
            if lbl_desc: metadata['label_desc'] = lbl_desc

    if lat is not None and lon is not None:
        metadata['lat'] = lat
        metadata['lon'] = lon

    is_alert = check_alert_words(message_body)

    return {
        'address': address,
        'alias': alias,
        'message': full_message,
        'frequency': freq_str,
        'bitrate': bitrate_str,
        'snr': snr_str,
        'metadata': metadata,
        'is_alert': is_alert,
        'flight': flight_id,
        'reg': reg,
        'icao': icao,
        'ac_model': ac_model,
        'gs_name': gs_name,
        'lat': lat,
        'lon': lon,
        'body_text': message_body
    }

class HfdlReceiver:
    """
    Lyssnar på TCP-ström (som klient eller server) och UDP på hfdl_host:hfdl_port
    för dumphfdl JSON-paket.
    """
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = 15556
        self.only_messages = True
        self.enabled = False
        self.running = False
        self.callback = None

        self.udp_sock = None
        self.tcp_server_sock = None
        self.tcp_client_sock = None

        self.udp_thread = None
        self.tcp_server_thread = None
        self.tcp_client_thread = None

        self.stats = {
            'status': 'stopped',
            'host': '127.0.0.1',
            'port': 15556,
            'packets_received': 0,
            'messages_decoded': 0,
            'last_flight': '-',
            'last_gs': '-',
            'last_freq': '-',
            'last_message_time': 'Ingen aktivitet ännu',
            'error_message': None
        }
        self.lock = threading.Lock()

    def set_callback(self, cb):
        self.callback = cb

    def start(self, host='127.0.0.1', port=15556, only_messages=True, enabled=False):
        self.host = str(host).strip() if host else '127.0.0.1'
        self.port = int(port)
        self.only_messages = (str(only_messages).lower() in ('true', '1', 'yes'))
        self.enabled = (str(enabled).lower() in ('true', '1', 'yes'))

        if not self.enabled:
            logger.info("[HFDL] HFDL-mottagaren är avaktiverad i inställningarna.")
            self.stats['status'] = 'disabled'
            return

        self.running = True
        self.stats['status'] = 'running'
        self.stats['host'] = self.host
        self.stats['port'] = self.port
        self.stats['error_message'] = None

        # Starta UDP-lyssnare
        self.udp_thread = threading.Thread(target=self._udp_listen_loop, daemon=True, name="HFDL-UDP-Receiver")
        self.udp_thread.start()

        # Om host är 0.0.0.0, starta TCP-server
        if self.host in ('0.0.0.0', ''):
            self.tcp_server_thread = threading.Thread(target=self._tcp_server_loop, daemon=True, name="HFDL-TCP-Server")
            self.tcp_server_thread.start()
        else:
            # Annars anslut som TCP-klient med automatisk återanslutning mot dumphfdl servern
            self.tcp_client_thread = threading.Thread(target=self._tcp_client_loop, daemon=True, name="HFDL-TCP-Client")
            self.tcp_client_thread.start()

        logger.info(f"[HFDL] HFDL-mottagare startad för {self.host}:{self.port} (only_messages={self.only_messages})")

    def stop(self):
        self.running = False
        self.stats['status'] = 'stopped'

        if self.udp_sock:
            try: self.udp_sock.close()
            except Exception: pass
            self.udp_sock = None

        if self.tcp_server_sock:
            try: self.tcp_server_sock.close()
            except Exception: pass
            self.tcp_server_sock = None

        if self.tcp_client_sock:
            try: self.tcp_client_sock.close()
            except Exception: pass
            self.tcp_client_sock = None

        logger.info("[HFDL] HFDL-mottagare stoppad.")

    def restart(self, host=None, port=None, only_messages=None, enabled=None):
        self.stop()
        time.sleep(0.3)
        h = host if host is not None else self.host
        p = port if port is not None else self.port
        o = only_messages if only_messages is not None else self.only_messages
        e = enabled if enabled is not None else self.enabled
        self.start(host=h, port=p, only_messages=o, enabled=e)

    def get_status(self):
        with self.lock:
            s = dict(self.stats)
            s['enabled'] = self.enabled
            s['running'] = self.running
            return s

    def _udp_listen_loop(self):
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_host = '0.0.0.0' if self.host in ('0.0.0.0', '') else self.host
            self.udp_sock.bind((bind_host, self.port))
            self.udp_sock.settimeout(2.0)
            logger.info(f"[HFDL] Lyssnar på UDP på {bind_host}:{self.port}")
        except Exception as e:
            logger.warning(f"[HFDL] Kunde inte binda UDP-port {self.port}: {e}")
            return

        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(65535)
                if not data:
                    continue
                self._handle_raw_data(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"[HFDL] UDP fel: {e}")
                time.sleep(0.5)

    def _tcp_client_loop(self):
        """Kopplar upp TCP-anslutning mot dumphfdl och återansluter automatiskt vid avbrott."""
        while self.running:
            try:
                logger.info(f"[HFDL] Ansluter som TCP-klient till {self.host}:{self.port}...")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                sock.connect((self.host, self.port))
                sock.settimeout(None)
                self.tcp_client_sock = sock
                logger.info(f"[HFDL] TCP-anslutning etablerad till {self.host}:{self.port}")
                with self.lock:
                    self.stats['status'] = 'connected'

                buffer = ""
                while self.running:
                    chunk = sock.recv(8192)
                    if not chunk:
                        logger.warning(f"[HFDL] Fjärrvärd stängde anslutningen ({self.host}:{self.port})")
                        break
                    buffer += chunk.decode('utf-8', errors='replace')
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            self._handle_raw_data(line.encode('utf-8'))
            except Exception as e:
                if self.running:
                    logger.warning(f"[HFDL] Kunde inte ansluta till {self.host}:{self.port}: {e}")
                    with self.lock:
                        self.stats['status'] = 'reconnecting'
                        self.stats['error_message'] = str(e)
            finally:
                if self.tcp_client_sock:
                    try: self.tcp_client_sock.close()
                    except Exception: pass
                    self.tcp_client_sock = None
            if self.running:
                time.sleep(5.0)

    def _tcp_server_loop(self):
        """Lyssnar som TCP-server när host är 0.0.0.0."""
        try:
            self.tcp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_server_sock.bind(('0.0.0.0', self.port))
            self.tcp_server_sock.listen(5)
            self.tcp_server_sock.settimeout(2.0)
            logger.info(f"[HFDL] TCP-server lyssnar på 0.0.0.0:{self.port}")
        except Exception as e:
            logger.error(f"[HFDL] Kunde inte starta TCP-server på port {self.port}: {e}")
            return

        while self.running:
            try:
                client_sock, addr = self.tcp_server_sock.accept()
                logger.info(f"[HFDL] Ny inkommande TCP-anslutning från {addr[0]}:{addr[1]}")
                t = threading.Thread(target=self._handle_tcp_client_stream, args=(client_sock, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"[HFDL] TCP server accept-fel: {e}")
                time.sleep(0.5)

    def _handle_tcp_client_stream(self, sock, addr):
        buffer = ""
        try:
            sock.settimeout(None)
            while self.running:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                buffer += chunk.decode('utf-8', errors='replace')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._handle_raw_data(line.encode('utf-8'))
        except Exception as e:
            logger.debug(f"[HFDL] Klient {addr} frånkopplad: {e}")
        finally:
            try: sock.close()
            except Exception: pass

    def _handle_raw_data(self, raw_bytes):
        with self.lock:
            self.stats['packets_received'] += 1

        text = raw_bytes.decode('utf-8', errors='replace').strip()
        if not text:
            return

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return

        parsed = parse_hfdl_frame(payload, only_messages=self.only_messages)
        if not parsed:
            return

        now_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        func_code = 1 if (parsed.get('lat') is not None and parsed.get('lon') is not None) else 0

        # Spara till databasen
        saved_id, saved_ts = save_message(
            address=parsed['address'],
            message=parsed['message'],
            alias=parsed['alias'],
            function_code=func_code,
            bitrate=parsed['bitrate'],
            frequency=parsed['frequency'],
            is_duplicate=0,
            repeat_count=1,
            last_timestamp=now_ts,
            metadata=parsed['metadata']
        )

        with self.lock:
            self.stats['messages_decoded'] += 1
            self.stats['last_message_time'] = now_ts
            if parsed.get('flight'): self.stats['last_flight'] = parsed['flight']
            elif parsed.get('reg'): self.stats['last_flight'] = parsed['reg']
            if parsed.get('gs_name'): self.stats['last_gs'] = parsed['gs_name']
            if parsed.get('frequency'): self.stats['last_freq'] = parsed['frequency']

        logger.info(f"[HFDL DECODED] -> [{parsed['address']}] {parsed['alias']} | {parsed['frequency']} | {parsed.get('flight', '')}")

        # Skicka till MQTT
        publish_message(parsed['address'], parsed['message'], saved_ts, parsed['alias'], metadata=parsed['metadata'])

        # Skicka via SSE till webbklienter
        msg_data = {
            'type': 'message',
            'id': saved_id,
            'timestamp': saved_ts,
            'address': parsed['address'],
            'message': parsed['message'],
            'alias': parsed['alias'],
            'frequency': parsed['frequency'],
            'bitrate': parsed['bitrate'],
            'function_code': func_code,
            'is_duplicate': False,
            'repeat_count': 1,
            'last_timestamp': saved_ts
        }
        msg_data.update(parsed['metadata'])

        if self.callback:
            try:
                self.callback(msg_data)
            except Exception as e:
                logger.error(f"[HFDL] Fel vid SSE-callback: {e}")

# Global singleton instans
hfdl_receiver = HfdlReceiver()

def init_hfdl(notify_callback=None):
    """Initierar HFDL-mottagaren från databasinställningar."""
    settings = get_settings()
    host = settings.get('hfdl_host', '127.0.0.1')
    port = settings.get('hfdl_port', '15556')
    only_messages = settings.get('hfdl_only_messages', 'true')
    enabled = settings.get('hfdl_enabled', 'false')

    if notify_callback:
        hfdl_receiver.set_callback(notify_callback)

    hfdl_receiver.start(host=host, port=port, only_messages=only_messages, enabled=enabled)

def restart_hfdl():
    """Startar om HFDL-mottagaren med uppdaterade inställningar."""
    settings = get_settings()
    hfdl_receiver.restart(
        host=settings.get('hfdl_host', '127.0.0.1'),
        port=settings.get('hfdl_port', '15556'),
        only_messages=settings.get('hfdl_only_messages', 'true'),
        enabled=settings.get('hfdl_enabled', 'false')
    )

def get_hfdl_status():
    """Returnerar aktuell status för HFDL."""
    return hfdl_receiver.get_status()

def send_test_hfdl_message(pkt_type='frequency_data'):
    """Skapar och injicerar ett realistiskt HFDL-testmeddelande."""
    if pkt_type == 'performance_data':
        test_frame = {
            "hfdl": {
                "freq": 8843000,
                "bit_rate": 300,
                "sig_level": -24.5,
                "noise_level": -31.0,
                "lpdu": {
                    "type": {"id": 79, "name": "Logon resume"},
                    "src": {"type": "Aircraft", "id": 401},
                    "dst": {"type": "Ground station", "name": "Shannon, Ireland", "id": 1},
                    "hfnpdu": {
                        "type": {"id": 209, "name": "Performance data"},
                        "flight_id": "CCA876",
                        "pos": {"lat": 52.666154, "lon": 6.621679},
                        "time": "12:15:30",
                        "gs": {"name": "Shannon, Ireland"},
                        "flight_leg_num": 1,
                        "frequency": {"freq": 8843.0},
                        "pdu_stats": {
                            "rx_300": 12, "rx_600": 4, "rx_1200": 0, "rx_1800": 0,
                            "spdus_rx_ok_cnt": 34, "spdus_missed_cnt": 1
                        },
                        "last_freq_change_cause": {"descr": "Normal propagation change"}
                    }
                }
            }
        }
    elif pkt_type == 'acars':
        test_frame = {
            "hfdl": {
                "freq": 8942000,
                "bit_rate": 300,
                "sig_level": -22.1,
                "noise_level": -30.4,
                "lpdu": {
                    "type": {"id": 19, "name": "Unnumbered ack'ed data"},
                    "src": {"type": "Aircraft", "id": 312},
                    "dst": {"type": "Ground station", "name": "Shannon, Ireland", "id": 1},
                    "hfnpdu": {
                        "type": {"id": 255, "name": "Enveloped data"},
                        "acars": {
                            "err": False,
                            "crc_ok": True,
                            "more": False,
                            "reg": ".SE-DMR",
                            "mode": "2",
                            "label": "Q0",
                            "blk_id": "3",
                            "ack": "!",
                            "flight": "SK0949",
                            "msg_num": "S35",
                            "msg_num_seq": "A",
                            "msg_text": ""
                        }
                    }
                }
            }
        }
    else:
        # Standard: Frequency data med rik ac_info
        test_frame = {
            "hfdl": {
                "freq": 8942000,
                "bit_rate": 300,
                "sig_level": -26.4376,
                "noise_level": -30.5612,
                "lpdu": {
                    "type": {"id": 79, "name": "Logon resume"},
                    "src": {"type": "Aircraft", "id": 312},
                    "dst": {"type": "Ground station", "name": "Shannon, Ireland", "id": 1},
                    "ac_info": {
                        "icao": "4A91B2",
                        "regnr": "SE-DMR",
                        "typecode": "A21N",
                        "opercode": "SAS-A21N",
                        "manuf": "Airbus",
                        "model": "Airbus A321-253NX",
                        "owner": "SAS Scandinavian Airlines"
                    },
                    "hfnpdu": {
                        "type": {"id": 213, "name": "Frequency data"},
                        "flight_id": "SAS949",
                        "pos": {"lat": 56.272767, "lon": 11.130888},
                        "utc_time": "11:22:33",
                        "freq_data": [
                            {
                                "gs": {"name": "Shannon, Ireland", "id": 1},
                                "heard_on_freqs": [8942, 8843],
                                "listening_on_freqs": [5547, 8843, 11384]
                            },
                            {
                                "gs": {"name": "Reykjavik, Iceland", "id": 2},
                                "heard_on_freqs": [8942],
                                "listening_on_freqs": [8942, 11384]
                            },
                            {
                                "gs": {"name": "Al Muharraq, Bahrain", "id": 8},
                                "heard_on_freqs": [],
                                "listening_on_freqs": [5547, 8843, 10081]
                            }
                        ]
                    }
                }
            }
        }

    hfdl_receiver._handle_raw_data(json.dumps(test_frame).encode('utf-8'))
    return {
        "status": "success",
        "message": f"Syntetiskt HFDL-testmeddelande ({pkt_type}) skickat.",
        "pkt_type": pkt_type
    }
