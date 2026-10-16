import socket
import json
import threading
import time
import logging
import re
import email.header
import base64
from datetime import datetime
from database import (
    save_message, get_settings, get_connection, check_alert_words
)

try:
    from mqtt_client import publish_message
except ImportError:
    def publish_message(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

# Kända Land Earth Stations (LES) för Inmarsat C
LES_MAP = {
    1: "Eik",
    2: "Burum",
    3: "Aussaguel",
    4: "Thermopylae",
    10: "Goonhilly",
    11: "Southbury",
    12: "Santa Paula",
    101: "Perth",
    102: "Sentosa",
    104: "Yamagushi",
    201: "Raisting",
    302: "Eik",
    304: "Burum",
    311: "Thermopylae",
    321: "Aussaguel",
    328: "Fucino"
}

# Minnes-cache för Inmarsat STD-C: logical_channel_number -> mes_id
CHANNEL_CACHE_TTL = 600
CHANNEL_MES_CACHE = {}
CHANNEL_MES_LOCK = threading.Lock()

def cache_channel_mes(payload):
    """
    Sparar logical_channel_number -> mes_id från signalerings-/uppropspaket
    (t.ex. Announcement descriptor.type == 1 m.fl.).
    Nycklas på (les_id, logical_channel_number) och som fallback logical_channel_number.
    """
    if not isinstance(payload, dict):
        return

    desc = payload.get("descriptor") if isinstance(payload.get("descriptor"), dict) else {}
    lcn = payload.get("logical_channel_number")
    if lcn is None:
        lcn = payload.get("lcn") or payload.get("logical_channel")
    if lcn is None and isinstance(desc, dict):
        lcn = desc.get("logical_channel_number") or desc.get("lcn")

    mes_id = payload.get("mes_id")
    if mes_id is None:
        mes_id = payload.get("mes") or payload.get("terminal_id")
    if mes_id is None and isinstance(desc, dict):
        mes_id = desc.get("mes_id") or desc.get("mes")

    if lcn is not None and mes_id is not None:
        try:
            lcn_int = int(lcn)
            mes_str = str(mes_id).strip()
            if mes_str:
                les_id = payload.get("les_id") or payload.get("les")
                if les_id is None and isinstance(desc, dict):
                    les_id = desc.get("les_id") or desc.get("les")
                les_id_int = None
                if les_id is not None:
                    try:
                        les_id_int = int(les_id)
                    except (ValueError, TypeError):
                        pass

                raw_service = payload.get("service") or payload.get("service_name") or ""
                now = time.time()
                data = {
                    'mes_id': mes_str,
                    'service': str(raw_service),
                    'timestamp': now
                }
                with CHANNEL_MES_LOCK:
                    # Rensa gamla poster om cachen vuxit över gränsen
                    if len(CHANNEL_MES_CACHE) > 1000:
                        expired = [k for k, v in CHANNEL_MES_CACHE.items() if now - v.get('timestamp', 0) > CHANNEL_CACHE_TTL]
                        for k in expired:
                            CHANNEL_MES_CACHE.pop(k, None)
                    if les_id_int is not None:
                        CHANNEL_MES_CACHE[(les_id_int, lcn_int)] = data
                    CHANNEL_MES_CACHE[lcn_int] = data
        except (ValueError, TypeError):
            pass

def lookup_channel_mes(les_id, lcn):
    """
    Slår upp mes_id baserat på (les_id, lcn) eller lcn som fallback om posten är yngre än CHANNEL_CACHE_TTL.
    """
    if lcn is None:
        return None
    try:
        lcn_int = int(lcn)
    except (ValueError, TypeError):
        return None

    les_id_int = None
    if les_id is not None:
        try:
            les_id_int = int(les_id)
        except (ValueError, TypeError):
            pass

    now = time.time()
    with CHANNEL_MES_LOCK:
        if les_id_int is not None and (les_id_int, lcn_int) in CHANNEL_MES_CACHE:
            entry = CHANNEL_MES_CACHE[(les_id_int, lcn_int)]
            if now - entry.get('timestamp', 0) <= CHANNEL_CACHE_TTL:
                return entry
        if lcn_int in CHANNEL_MES_CACHE:
            entry = CHANNEL_MES_CACHE[lcn_int]
            if now - entry.get('timestamp', 0) <= CHANNEL_CACHE_TTL:
                return entry
    return None

def extract_coordinates(text):
    """
    Extraherar sjöfarts- och SAR-koordinater ur text.
    Stödjer:
    - 58-34.2N 016-12.5E eller 58-34N 016-12E
    - 58 34.2N 016 12.5E eller 58 34N 016 12E
    - 58°34'N 016°12'E
    - 5834N 01612E eller 5834.2N 01612.5E
    - LAT 58-34N LONG 016-12E
    - 58.570N 016.208E
    Returnerar (lat, lon) i decimalgrader avrundat till 5 decimaler, eller (None, None).
    """
    if not text:
        return None, None

    # 1. Hyphenated, spaced eller gradtecken: 58-34.2N 016-12.5E, 58 34N 016 12E, 58°34.2'N 016°12.5'E
    pat1 = re.compile(
        r'\b(\d{1,2})[-°\s]+(\d{1,2}(?:\.\d+)?)[′\'\s]*([NS])\b'
        r'[\s,;/and]*'
        r'\b(\d{1,3})[-°\s]+(\d{1,2}(?:\.\d+)?)[′\'\s]*([EW])\b',
        re.IGNORECASE
    )
    m = pat1.search(text)
    if m:
        lat_deg, lat_min, lat_dir, lon_deg, lon_min, lon_dir = m.groups()
        lat = float(lat_deg) + float(lat_min) / 60.0
        if lat_dir.upper() == 'S':
            lat = -lat
        lon = float(lon_deg) + float(lon_min) / 60.0
        if lon_dir.upper() == 'W':
            lon = -lon
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return round(lat, 5), round(lon, 5)

    # 2. Kompakt format: 5834N 01612E eller 5834.2N 01612.5E eller 5834N01612E
    pat2 = re.compile(
        r'\b(\d{2})(\d{2}(?:\.\d+)?)\s*([NS])\s*,?\s*(\d{3}|\d{2})(\d{2}(?:\.\d+)?)\s*([EW])\b',
        re.IGNORECASE
    )
    m = pat2.search(text)
    if m:
        lat_deg, lat_min, lat_dir, lon_deg, lon_min, lon_dir = m.groups()
        lat = float(lat_deg) + float(lat_min) / 60.0
        if lat_dir.upper() == 'S':
            lat = -lat
        lon = float(lon_deg) + float(lon_min) / 60.0
        if lon_dir.upper() == 'W':
            lon = -lon
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return round(lat, 5), round(lon, 5)

    # 3. Decimalgrader med N/S och E/W: 58.570N 016.208E
    pat3 = re.compile(
        r'\b(\d{1,2}\.\d+)\s*([NS])\b[\s,;]*\b(\d{1,3}\.\d+)\s*([EW])\b',
        re.IGNORECASE
    )
    m = pat3.search(text)
    if m:
        lat_val, lat_dir, lon_val, lon_dir = m.groups()
        lat = float(lat_val)
        if lat_dir.upper() == 'S':
            lat = -lat
        lon = float(lon_val)
        if lon_dir.upper() == 'W':
            lon = -lon
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return round(lat, 5), round(lon, 5)

    # 4. Explicit LAT / LONG labels: LAT 58-34N LONG 016-12E
    pat4 = re.compile(
        r'LAT(?:ITUDE)?[:\s]+([0-9.-]+)\s*([NS])?[\s,;]+LON(?:GITUDE)?[:\s]+([0-9.-]+)\s*([EW])?',
        re.IGNORECASE
    )
    m = pat4.search(text)
    if m:
        raw_lat, lat_dir, raw_lon, lon_dir = m.groups()
        try:
            if '-' in raw_lat:
                p = raw_lat.split('-')
                lat = float(p[0]) + float(p[1]) / 60.0
            else:
                lat = float(raw_lat)
            if lat_dir and lat_dir.upper() == 'S':
                lat = -abs(lat)
            if '-' in raw_lon:
                p = raw_lon.split('-')
                lon = float(p[0]) + float(p[1]) / 60.0
            else:
                lon = float(raw_lon)
            if lon_dir and lon_dir.upper() == 'W':
                lon = -abs(lon)
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return round(lat, 5), round(lon, 5)
        except Exception:
            pass

    return None, None

def format_satc_frequency(raw_freq):
    """
    Formaterar frekvens till standardiserat MHz-format för RF-aktivitet (t.ex. 1537.106M).
    Stödjer:
    - SatDump source.station_id: "1.537.106" eller "1.539.481." -> "1537.106M"
    - Hz som heltal eller sträng: 1539421000 eller "1539421000" -> "1539.421M"
    - MHz som float/sträng: 1539.975 -> "1539.975M"
    - Fallback: "1537.700M"
    """
    if not raw_freq:
        return "1537.700M"

    s = str(raw_freq).strip()

    # 1. SatDump station_id-mönster: ^1\.(\d{3})\.(\d{3})\.?$ (t.ex. "1.537.106" eller "1.539.481.")
    m_station = re.match(r'^1\.(\d{3})\.(\d{3})\.?$', s)
    if m_station:
        g1, g2 = m_station.groups()
        return f"1{g1}.{g2}M"

    # Rensa bort eventuella enheter och mellanslag
    s_clean = s.replace("MHz", "").replace("mhz", "").replace("Hz", "").replace("hz", "").replace("M", "").replace(" ", "")
    try:
        val = float(s_clean)
        if val > 1_000_000_000:
            return f"{val / 1e6:.3f}M"
        elif val > 1_000_000:
            return f"{val / 1e3:.3f}M"
        elif val > 100:
            return f"{val:.3f}M"
        else:
            return f"{val:.3f}M"
    except (ValueError, TypeError):
        return s

def clean_control_characters(text):
    """
    Rensar bort icke-utskrivbara binära kontrolltecken (ASCII < 32 utom \n, \r, \t)
    samt DEL (0x7F) ur text så att brödtexten hålls ren och läsbar.
    """
    if not text:
        return ""
    # Ta bort ASCII 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F
    clean_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(text))
    return clean_str.strip()

def decode_mime_headers(text: str) -> str:
    """
    Avkodar RFC 2047 MIME-kodade e-postheaders (t.ex. =?koi8-r?B?...?= eller =?utf-8?Q?...?=)
    till läsbar UTF-8-text.
    """
    if not text or '=?' not in text:
        return text

    def _replace_mime(m):
        charset = m.group(1).lower().strip()
        encoding = m.group(2).upper().strip()
        encoded_data = m.group(3).strip()
        try:
            if encoding == 'B':
                pad = len(encoded_data) % 4
                if pad:
                    encoded_data += '=' * (4 - pad)
                raw_bytes = base64.b64decode(encoded_data)
                return raw_bytes.decode(charset, errors='replace')
            elif encoding == 'Q':
                import quopri
                raw_bytes = quopri.decodestring(encoded_data.replace('_', ' '))
                return raw_bytes.decode(charset, errors='replace')
        except Exception:
            try:
                parts = email.header.decode_header(m.group(0))
                out = []
                for b, cs in parts:
                    if isinstance(b, bytes):
                        out.append(b.decode(cs or charset or 'utf-8', errors='replace'))
                    else:
                        out.append(str(b))
                return ''.join(out)
            except Exception:
                pass
        return m.group(0)

    pattern = re.compile(r'=\?([^?]+)\?([BbQq])\?([^?]+)\?=', re.IGNORECASE)
    return pattern.sub(_replace_mime, str(text))

def normalize_satc_priority(raw_priority, text=""):
    """
    Normaliserar prioritet:
    DISTRESS, URGENCY, Safety, Routine.
    Observera att radfärgning/alert styrs separat av användarens aktiva larmordslista.
    """
    p_str = str(raw_priority or "").strip().upper()
    t_str = str(text or "").upper()

    if p_str in ("3", "DISTRESS") or "DISTRESS" in p_str or "MAYDAY" in p_str or "MAYDAY" in t_str or "DISTRESS" in t_str:
        return "DISTRESS", False
    if p_str in ("2", "URGENCY") or "URGENCY" in p_str or "PAN PAN" in p_str or "PAN PAN" in t_str or "PAN-PAN" in t_str:
        return "URGENCY", False
    if p_str in ("1", "SAFETY") or "SAFETY" in p_str or "SECURITE" in p_str or "SECURITE" in t_str:
        return "Safety", False
    if p_str in ("0", "ROUTINE") or "ROUTINE" in p_str:
        return "Routine", False

    # Fallback baserat på text
    if "SAFETY" in t_str or "NAVWARN" in t_str or "METAREA" in t_str or "NAVAREA" in t_str:
        return "Safety", False

    return "Routine", False

def classify_satc_service(payload, text=""):
    """
    Klassificerar Inmarsat STD-C / EGC-tjänsten och returnerar:
    (svensk_kategori_titel, badge_label, alias_default)
    """
    raw_service = str(payload.get("service") or payload.get("service_name") or payload.get("type") or payload.get("msg_type") or "").strip().upper()
    text_upper = str(text or "").upper()

    # SAR / Distress
    if "SAR" in raw_service or "DISTRESS" in raw_service or "SAR" in text_upper or "SEARCH AND RESCUE" in text_upper or "SJÖRÄDDNING" in text_upper:
        return "Inmarsat SafetyNET / Sjöräddning (SAR)", "EGC: SAR (Sjöräddning)", "SAR / Distress"

    # Piratvarning / Skydd
    if "PIRACY" in raw_service or "SECURITY" in raw_service or "PIRACY" in text_upper or "ATTACK" in text_upper or "PIRAT" in text_upper:
        return "Inmarsat SafetyNET / Sjöfartsskydd", "EGC: Sjöfartsskydd / Piratvarning", "SafetyNET (EGC)"

    # Meteorologi / Vädervarning
    if "MET" in raw_service or "WEATHER" in raw_service or "METAREA" in text_upper or "GALE WARNING" in text_upper or "STORM WARNING" in text_upper or "WEATHER" in text_upper:
        return "Inmarsat SafetyNET / Vädervarning", "EGC: Metarea / Vädervarning", "SafetyNET (EGC)"

    # Navigationsvarning (NAVWARN)
    if "NAV" in raw_service or "NAVWARN" in text_upper or "NAVAREA" in text_upper or "NOTICE TO MARINERS" in text_upper or "LIGHT BUOY" in text_upper:
        return "Inmarsat SafetyNET / Sjöfartsvarning", "EGC: Navwarn / Sjöfartsvarning", "SafetyNET (EGC)"

    # FleetNET
    if "FLEET" in raw_service or "FLEETNET" in text_upper:
        return "Inmarsat FleetNET / Flottmeddelande", "FleetNET: Flottmeddelande", "FleetNET"

    # EGC Allmänt
    if "EGC" in raw_service or "SAFETYNET" in raw_service:
        return "Inmarsat SafetyNET / EGC", "EGC: SafetyNET", "SafetyNET (EGC)"

    # STD-C Textmeddelande
    return "Inmarsat STD-C / Textmeddelande", "STD-C: Textmeddelande", "Inmarsat-C"

def is_binary_or_gibberish(raw_text: str) -> bool:
    """
    Identifierar binära, telemetriska eller krypterade Inmarsat STD-C-paket
    som SatDump felaktigt tolkar som ASCII-text.
    Returnerar True om texten är skräp/binär och bör filtreras bort när satc_only_messages är aktivt.
    """
    if not raw_text or not isinstance(raw_text, str):
        return True

    # 1. Krypterade ryska paket (5PRCRYPTO eller 5PSCRYPTO)
    upper_raw = raw_text.upper()
    if "5PRCRYPTO" in upper_raw or "5PSCRYPTO" in upper_raw:
        return True

    # 2. Hög andel binära kontrolltecken i råtexten (innan städning)
    # Kontrolltecken: ASCII < 32 exklusive \r (13), \n (10), \t (9), samt 0x7F (127)
    control_chars = [ch for ch in raw_text if (ord(ch) < 32 and ch not in ('\r', '\n', '\t')) or ord(ch) == 127]
    control_count = len(control_chars)
    total_len = len(raw_text)

    if control_count > 2:
        return True
    if total_len > 0 and (control_count / total_len) > 0.05:
        return True

    # 3. Läsbarhets- och ordfilter (Gibberish-detektering)
    cleaned_text = clean_control_characters(raw_text).strip()
    if not cleaned_text:
        return True

    # Räkna andelen vanliga tecken jämfört med typiska telemetri-specialtecken: | < > ] [ $ & @ ^ ~ ` { }
    visible_chars = [ch for ch in cleaned_text if not ch.isspace()]
    if visible_chars:
        special_chars_set = set("|<>]}[{$&@^~`")
        special_count = sum(1 for ch in visible_chars if ch in special_chars_set)
        if (special_count / len(visible_chars)) > 0.12:
            return True

    # Kontrollera förekomst av riktiga ord med minst 4 bokstäver
    words = re.findall(r'[A-Za-z]{4,}', cleaned_text)
    if len(words) < 2:
        return True

    return False

def parse_satc_frame(payload, only_messages=True):
    """
    Parsar ett avkodat SatDump Inmarsat STD-C / EGC-ramverk i JSON-format.
    Stödjer SatDump 1.2.3 inmarsat_stdc_parser descriptors (type 1, 3, 6, 7 m.fl.).
    Returnerar dict med parsed info eller None om ramen filtrerades bort.
    """
    if not isinstance(payload, dict):
        return None

    # Spara korrelation mellan logical_channel_number och mes_id från signaleringspaket
    # Alltid INNAN fragment- eller only_messages-filtret kastar paketet!
    cache_channel_mes(payload)

    # Extrahera descriptor och pkt_name om tillgängligt
    desc = payload.get("descriptor") if isinstance(payload.get("descriptor"), dict) else {}
    desc_type = desc.get("type")
    pkt_name = str(payload.get("pkt_name") or payload.get("packet_name") or "").strip()
    pkt_name_lower = pkt_name.lower()

    # Kontrollera om det är ett ofullständigt delpaket/fragment
    is_fragment = False
    if pkt_name:
        # Om SatDump angett pkt_name: kompletta sammanslagna meddelanden innehåller alltid "full"
        # (t.ex. "Full Message" eller "Full EGC Message").
        # Paket som "EGC Double Header 1", "EGC Double Header 2", "EGC Single Header", "Message Packet" etc.
        # saknar "full" och är ofullständiga delpaket.
        if "full" not in pkt_name_lower:
            is_fragment = True
    else:
        # Om pkt_name saknas: kontrollera fragment- och fortsättningsflaggor
        if payload.get("continuation") is True or payload.get("is_continuation") is True:
            is_fragment = True
        elif payload.get("is_fragment") is True or payload.get("fragment") is True:
            is_fragment = True
        elif "packet_number" in payload and "number_of_packets" in payload:
            try:
                pkt_num = int(payload.get("packet_number", 0))
                num_pkts = int(payload.get("number_of_packets", 0))
                if num_pkts > 1 and pkt_num < num_pkts:
                    is_fragment = True
            except (ValueError, TypeError):
                pass

    # När only_messages är aktivt: ignorera ofullständiga delpaket/fragment
    if only_messages and is_fragment:
        logger.debug(f"[SATC] Ignorerar ofullständigt delpaket/fragment: pkt_name={pkt_name}")
        return None

    # Extrahera faktisk brödtext ur explicita meddelandefält innan städning
    # OBS: "message_reference_number" och "message_channel" är kontrollfält och INTE brödtext!
    raw_text_uncleaned = None
    for k in ("message", "text", "msg", "data", "content", "body", "egc_text", "egc_message", "ascii", "payload"):
        val = payload.get(k)
        if isinstance(val, str) and val.strip():
            raw_text_uncleaned = val
            break
        elif isinstance(val, dict):
            for sub_k in ("text", "message", "msg", "data", "ascii"):
                sub_val = val.get(sub_k)
                if isinstance(sub_val, str) and sub_val.strip():
                    raw_text_uncleaned = sub_val
                    break
        if raw_text_uncleaned:
            break

    # När only_messages är aktivt: kontrollera binärt skräp / telemetri / kryptering på den råa texten
    if only_messages and raw_text_uncleaned:
        if is_binary_or_gibberish(raw_text_uncleaned):
            logger.debug("[SATC] Ignorerar binärt/krypterat skräppaket")
            return None

    raw_text = clean_control_characters(raw_text_uncleaned) if raw_text_uncleaned else None
    if raw_text:
        raw_text = decode_mime_headers(raw_text)

    # Identifiera specifika kontrollpakettyper från SatDump descriptor & rotfält
    # 1. Bulletin Board: descriptor.type == 7 eller frame_number + status eller channel_type_name == "NCS"
    is_bulletin_board = (desc_type == 7) or ("frame_number" in payload and "status" in payload) or (payload.get("channel_type_name") == "NCS")
    # 2. Signalling Channel: descriptor.type == 6 eller tdm_slots finns
    is_signalling_channel = (desc_type == 6) or ("tdm_slots" in payload)
    # 3. Announcement: descriptor.type == 1 eller message_reference_number + mes_id finns
    is_announcement = (desc_type == 1) or ("message_reference_number" in payload and "mes_id" in payload)
    # 4. Logical Channel Assignment: descriptor.type == 3 eller message_channel + frame_offset finns
    is_channel_assignment = (desc_type == 3) or ("message_channel" in payload and "frame_offset" in payload)

    is_control_packet = (not raw_text) or is_bulletin_board or is_signalling_channel or is_announcement or is_channel_assignment

    # När only_messages är aktivt: släpp ENDAST igenom meddelanden med faktisk brödtext
    if only_messages and (is_control_packet or not raw_text):
        return None

    # Extrahera Frekvens från source.station_id ("1.537.106"), downlink_freq_mhz, freq, etc.
    raw_freq = None
    source_obj = payload.get("source")
    if isinstance(source_obj, dict):
        raw_freq = source_obj.get("station_id")
    if not raw_freq:
        raw_freq = (
            payload.get("station_id")
            or payload.get("downlink_freq_mhz")
            or payload.get("freq")
            or payload.get("frequency")
            or payload.get("uplink_freq_mhz")
            or payload.get("rx_freq")
        )
    freq_str = format_satc_frequency(raw_freq)

    # Extrahera Satellit (sat_name)
    sat_name = str(payload.get("sat_name") or "").strip()
    sat_short = None
    if sat_name:
        m_sat = re.search(r'\(([^)]+)\)', sat_name)
        sat_short = m_sat.group(1).strip() if m_sat else sat_name

    # Extrahera Jordstation (LES)
    les_id = payload.get("les_id") or payload.get("les")
    les_name = str(payload.get("les_name") or payload.get("les_station") or "").strip()

    if not les_name and les_id is not None:
        try:
            les_id_int = int(les_id)
            les_name = LES_MAP.get(les_id_int, "")
        except (ValueError, TypeError):
            pass

    les_display = les_name if les_name else (f"LES-{les_id}" if les_id is not None else None)

    # Extrahera logiskt kanalnummer
    lcn = payload.get("logical_channel_number")
    if lcn is None:
        lcn = payload.get("lcn") or payload.get("logical_channel")
    if lcn is None and isinstance(desc, dict):
        lcn = desc.get("logical_channel_number") or desc.get("lcn")
    try:
        lcn_val = int(lcn) if lcn is not None else None
    except (ValueError, TypeError):
        lcn_val = None

    # Extrahera Terminal-ID (mes_id)
    mes_id = payload.get("mes_id")
    if mes_id is None and isinstance(desc, dict):
        mes_id = desc.get("mes_id") or desc.get("mes")
    if mes_id is not None:
        mes_id = str(mes_id).strip()

    # Berika meddelandepaket från minnes-cachen om mes_id saknas men lcn finns
    if not mes_id and lcn_val is not None:
        cached_info = lookup_channel_mes(les_id, lcn_val)
        if cached_info:
            mes_id = cached_info.get('mes_id')

    # Extrahera Tjänst
    raw_service_str = str(payload.get("service") or payload.get("service_name") or "").strip()

    # Extrahera Prioritet
    raw_priority = payload.get("priority") or payload.get("priority_name") or payload.get("prio")
    priority_norm, is_alert = normalize_satc_priority(raw_priority, raw_text or "")

    # Skapa rådatasträng i kompakt JSON
    try:
        raw_json_str = json.dumps(payload, ensure_ascii=False)
    except Exception:
        raw_json_str = str(payload)

    # Hantera kontrollpaket när only_messages == False
    if not raw_text:
        if is_announcement:
            service_desc = raw_service_str or "Store And Forward"
            dl_freq = payload.get("downlink_freq_mhz", "-")
            ref_num = payload.get("message_reference_number", "-")
            lcn_disp = lcn_val if lcn_val is not None else payload.get("logical_channel_number", "-")
            body_text = (
                f"[ Upprop / Announcement ] Till terminal (MES): {mes_id} | "
                f"Tjänst: {service_desc} ({priority_norm}) | "
                f"Hänvisad downlink: {dl_freq} MHz (Kanal #{lcn_disp}) | "
                f"Referens: #{ref_num}"
            )
            service_title = "Inmarsat STD-C / Upprop"
            service_badge = "Announcement"
            default_alias = f"Announcement ({service_desc})"
            address = f"MES: {mes_id}" if mes_id else (f"LES: {les_display}" if les_display else "INMARSAT-C")
        elif is_channel_assignment:
            service_desc = raw_service_str or "Store And Forward"
            dl_freq = payload.get("downlink_freq_mhz", "-")
            slot = payload.get("slot_number", 0)
            lcn_disp = lcn_val if lcn_val is not None else payload.get("logical_channel_number", "-")
            body_text = (
                f"[ Kanalallokering ] Terminal (MES): {mes_id} | "
                f"Tjänst: {service_desc} | "
                f"Downlink: {dl_freq} MHz (Kanal #{lcn_disp}, Slot {slot})"
            )
            service_title = "Inmarsat STD-C / Kanalallokering"
            service_badge = "Channel Assign"
            default_alias = f"Channel Assign ({service_desc})"
            address = f"MES: {mes_id}" if mes_id else (f"LES: {les_display}" if les_display else "INMARSAT-C")
        elif is_bulletin_board:
            sat_disp = sat_name or "-"
            les_disp = les_name or "-"
            frame_num = payload.get("frame_number", "-")
            speed = 600
            if isinstance(payload.get("status"), dict):
                speed = payload.get("status", {}).get("return_link_speed", 600)
            body_text = (
                f"[ Bulletin Board (NCS) ] Satellit: {sat_disp} | "
                f"LES: {les_disp} | Ram: #{frame_num} | Uplink: {speed} bps"
            )
            service_title = "Inmarsat STD-C / Bulletin Board"
            service_badge = "Bulletin Board"
            default_alias = f"Bulletin Board ({sat_short or les_disp})"
            address = f"LES: {les_disp}" if les_disp != "-" else "INMARSAT-C"
        elif is_signalling_channel:
            up_freq = payload.get("uplink_freq_mhz", "-")
            body_text = f"[ Signalling Channel ] Uplink: {up_freq} MHz | TDM-tidluckor"
            service_title = "Inmarsat STD-C / Signalling Channel"
            service_badge = "Signalling"
            default_alias = "Signalling Channel"
            address = "Signalling Channel"
        else:
            type_str = str(payload.get("type") or desc_type or "Kontrollpaket").strip()
            body_text = f"[ Kontrollpaket ] Typ: {type_str}"
            service_title = "Inmarsat STD-C / Kontrollpaket"
            service_badge = "Control"
            default_alias = "Inmarsat-C"
            address = f"LES: {les_display}" if les_display else "INMARSAT-C"

        full_message = f"{body_text}\nRådata: {raw_json_str}"
        alias = default_alias
        navarea_str = ""
        lat, lon = None, None
    else:
        # Faktiskt meddelandepaket med text
        body_text = decode_mime_headers(raw_text)

        # Extrahera Område (NAVAREA / METAREA / Area)
        navarea = payload.get("navarea") or payload.get("area") or payload.get("metarea") or payload.get("ocean_region")
        if not navarea:
            m_area = re.search(r'\b(NAVAREA\s+[A-Z0-9]+|METAREA\s+[A-Z0-9]+)\b', body_text, re.IGNORECASE)
            if m_area:
                navarea = m_area.group(1).upper()

        navarea_str = str(navarea).strip() if navarea else ""

        # Extrahera Tjänst / Kategori
        service_title, service_badge, default_alias = classify_satc_service(payload, body_text)

        # Extrahera Koordinater ur meddelandetexten
        lat, lon = extract_coordinates(body_text)

        # Adress och Alias
        if mes_id:
            address = f"MES: {mes_id}"
            alias = default_alias
        elif les_display:
            address = f"LES: {les_display}"
            alias = default_alias
        elif navarea_str:
            address = f"EGC: {navarea_str}"
            alias = default_alias
        else:
            address = "INMARSAT-C"
            alias = default_alias

        # Bygg svensk sammanfattningsrad överst
        summary_parts = []
        if sat_short:
            summary_parts.append(f"Sat: {sat_short}")
        if navarea_str:
            summary_parts.append(f"Område: {navarea_str}")
        if les_display:
            summary_parts.append(f"Jordstation: {les_display}")
        if mes_id:
            summary_parts.append(f"MES ID: {mes_id}")
        elif lcn_val is not None:
            summary_parts.append(f"Kanal: #{lcn_val}")
        summary_parts.append(f"Prioritet: {priority_norm}")

        summary_header = f"[{service_title}] " + " | ".join(summary_parts)
        full_message = f"{summary_header}\n{body_text}\nRådata: {raw_json_str}"

    metadata = {
        'protocol': 'SATC',
        'frequency': freq_str,
        'priority': priority_norm,
        'satc_priority': priority_norm,
        'satc_service': service_badge,
        'is_alert': is_alert
    }
    if sat_name:
        metadata['sat_name'] = sat_name
        metadata['sat_badge'] = f"Sat: {sat_short or sat_name}"
    if les_display:
        metadata['les_name'] = les_display
        metadata['les_badge'] = f"LES: {les_display}"
    if les_id is not None:
        metadata['les_id'] = les_id
    if mes_id is not None:
        metadata['mes_id'] = mes_id
        metadata['mes_badge'] = f"MES: {mes_id}"
    if lcn_val is not None:
        metadata['logical_channel_number'] = lcn_val
        metadata['channel_badge'] = f"Ch: #{lcn_val}"
    if raw_service_str:
        metadata['service'] = raw_service_str
        metadata['service_badge'] = f"Service: {raw_service_str}"
    if navarea_str:
        metadata['navarea'] = navarea_str
    if lat is not None and lon is not None:
        metadata['lat'] = lat
        metadata['lon'] = lon

    return {
        'address': address,
        'alias': alias,
        'message': full_message,
        'frequency': freq_str,
        'bitrate': 'SATC',
        'metadata': metadata,
        'is_alert': is_alert,
        'priority': priority_norm,
        'service_title': service_title,
        'service_badge': service_badge,
        'navarea': navarea_str,
        'les': les_display,
        'mes_id': mes_id,
        'logical_channel_number': lcn_val,
        'lat': lat,
        'lon': lon,
        'body_text': body_text
    }

class SatCReceiver:
    """
    Lyssnar på både UDP och TCP på satc_host:satc_port för
    avkodade Inmarsat STD-C / EGC JSON-strömmar från SatDump.
    Stödjer både inkommande lyssning (server) och utgående anslutning (klient).
    """
    def __init__(self):
        self.host = '0.0.0.0'
        self.port = 6558
        self.only_messages = True
        self.enabled = True
        self.running = False
        self.callback = None

        self.udp_sock = None
        self.tcp_server_sock = None
        self.tcp_client_sock = None
        self.udp_thread = None
        self.tcp_server_thread = None
        self.tcp_client_thread = None
        self.client_threads = []

        self.stats = {
            'status': 'stopped',
            'host': '0.0.0.0',
            'port': 6558,
            'packets_received': 0,
            'messages_decoded': 0,
            'last_les': '-',
            'last_service': '-',
            'last_priority': '-',
            'last_message_time': 'Ingen aktivitet ännu',
            'error_message': None
        }
        self.lock = threading.Lock()

    def set_callback(self, cb):
        self.callback = cb

    def start(self, host='0.0.0.0', port=6558, only_messages=True, enabled=True):
        self.host = str(host).strip() if host else '0.0.0.0'
        self.port = int(port)
        self.only_messages = (str(only_messages).lower() in ('true', '1', 'yes'))
        self.enabled = (str(enabled).lower() in ('true', '1', 'yes'))

        if not self.enabled:
            logger.info("[SATC] Inmarsat STD-C mottagaren är avaktiverad i inställningarna.")
            self.stats['status'] = 'disabled'
            return

        self.running = True
        self.stats['status'] = 'running'
        self.stats['host'] = self.host
        self.stats['port'] = self.port
        self.stats['error_message'] = None

        # Starta UDP-lyssnartråd
        self.udp_thread = threading.Thread(target=self._udp_listen_loop, daemon=True, name="SatC-UDP-Receiver")
        self.udp_thread.start()

        # Starta TCP-servertråd
        self.tcp_server_thread = threading.Thread(target=self._tcp_server_loop, daemon=True, name="SatC-TCP-Server")
        self.tcp_server_thread.start()

        # Om host inte är 0.0.0.0, starta även utgående TCP-klienttråd ifall SatDump agerar server
        if self.host not in ('0.0.0.0', ''):
            self.tcp_client_thread = threading.Thread(target=self._tcp_client_loop, daemon=True, name="SatC-TCP-Client")
            self.tcp_client_thread.start()

        logger.info(f"[SATC] Inmarsat STD-C mottagare startad för {self.host}:{self.port} (only_messages={self.only_messages})")

    def stop(self):
        self.running = False
        self.stats['status'] = 'stopped'

        for s in (self.udp_sock, self.tcp_server_sock, self.tcp_client_sock):
            if s:
                try: s.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                try: s.close()
                except Exception: pass

        self.udp_sock = None
        self.tcp_server_sock = None
        self.tcp_client_sock = None

        threads_to_join = [th for th in (self.udp_thread, self.tcp_server_thread, self.tcp_client_thread) if th and th.is_alive() and threading.current_thread() != th]
        for th in threads_to_join:
            th.join(timeout=1.5)

        self.udp_thread = None
        self.tcp_server_thread = None
        self.tcp_client_thread = None

        logger.info("[SATC] Inmarsat STD-C mottagare stoppad.")

    def restart(self, host='0.0.0.0', port=6558, only_messages=True, enabled=True):
        self.stop()
        time.sleep(0.3)
        self.start(host=host, port=port, only_messages=only_messages, enabled=enabled)

    def get_status(self):
        with self.lock:
            s = dict(self.stats)
            s['host'] = self.host
            s['port'] = self.port
            s['enabled'] = self.enabled
            s['only_messages'] = self.only_messages
            return s

    def _udp_listen_loop(self):
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_sock.bind(('0.0.0.0', self.port))
            self.udp_sock.settimeout(1.0)
            logger.info(f"[SATC] UDP-lyssnare bunden till 0.0.0.0:{self.port}")
        except Exception as e:
            logger.error(f"[SATC] Kunde inte binda UDP-socket till port {self.port}: {e}")
            with self.lock:
                self.stats['error_message'] = f"UDP bind error: {e}"
            return

        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(65536)
                if not data:
                    continue
                text = data.decode('utf-8', errors='replace')
                for line in text.splitlines():
                    line = line.strip()
                    if line:
                        self._handle_raw_json(line)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"[SATC] UDP mottagningsfel: {e}")

    def _tcp_server_loop(self):
        try:
            self.tcp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_server_sock.bind(('0.0.0.0', self.port))
            self.tcp_server_sock.listen(5)
            self.tcp_server_sock.settimeout(1.0)
            logger.info(f"[SATC] TCP-server lyssnar på 0.0.0.0:{self.port}")
        except Exception as e:
            logger.debug(f"[SATC] Kunde inte starta TCP-server på port {self.port}: {e}")
            return

        while self.running:
            try:
                client_sock, client_addr = self.tcp_server_sock.accept()
                logger.info(f"[SATC] Ny TCP-anslutning från {client_addr}")
                t = threading.Thread(target=self._handle_tcp_client, args=(client_sock, client_addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"[SATC] TCP server accept-fel: {e}")

    def _tcp_client_loop(self):
        """
        När en specifik IP-adress eller värdnamn anges för SatDump, ansluter vi aktivt
        till dess TCP-server (likt VDL2) och läser strömmande JSON-rader med automatisk återanslutning.
        """
        backoff = 3
        immediate_eof_warned = False
        while self.running:
            sock = None
            try:
                logger.info(f"[SATC] Försöker ansluta till SatDump TCP-ström på {self.host}:{self.port}...")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((self.host, self.port))
                sock.settimeout(2.0)
                self.tcp_client_sock = sock

                connection_confirmed = False
                buffer = ""

                while self.running:
                    try:
                        chunk = sock.recv(4096)
                    except (socket.timeout, TimeoutError):
                        if not connection_confirmed:
                            connection_confirmed = True
                            with self.lock:
                                self.stats['status'] = 'connected'
                                self.stats['error_message'] = None
                            backoff = 3
                            immediate_eof_warned = False
                            logger.info(f"[SATC] Ansluten till SatDump TCP på {self.host}:{self.port}")
                        continue

                    if not chunk:
                        if not connection_confirmed:
                            if not immediate_eof_warned:
                                logger.warning(f"[SATC] Port {self.host}:{self.port} stängde anslutningen omedelbart (EOF). Kontrollera att SatDump körs. Nytt försök om {backoff}s.")
                                immediate_eof_warned = True
                            with self.lock:
                                self.stats['status'] = 'reconnecting'
                        else:
                            logger.warning(f"[SATC] Fjärrvärd stängde anslutningen ({self.host}:{self.port}). Nytt försök om {backoff}s.")
                            with self.lock:
                                self.stats['status'] = 'reconnecting'
                        break

                    if not connection_confirmed:
                        connection_confirmed = True
                        with self.lock:
                            self.stats['status'] = 'connected'
                            self.stats['error_message'] = None
                        backoff = 3
                        immediate_eof_warned = False
                        logger.info(f"[SATC] Ansluten till SatDump TCP på {self.host}:{self.port}")

                    buffer += chunk.decode('utf-8', errors='replace')
                    while '\n' in buffer:
                        line_str, buffer = buffer.split('\n', 1)
                        line_str = line_str.strip()
                        if line_str:
                            self._handle_raw_json(line_str)
            except Exception as e:
                if self.running:
                    logger.warning(f"[SATC] TCP-klientanslutning mot {self.host}:{self.port} avbröts eller misslyckades: {e}. Nytt försök om {backoff}s.")
                    with self.lock:
                        self.stats['status'] = 'reconnecting'
                        self.stats['error_message'] = str(e)
            finally:
                if self.tcp_client_sock:
                    try: self.tcp_client_sock.close()
                    except Exception: pass
                    self.tcp_client_sock = None
                if sock:
                    try: sock.close()
                    except Exception: pass

            for _ in range(backoff):
                if not self.running:
                    break
                time.sleep(1.0)
            backoff = min(backoff * 2, 30)

    def _handle_tcp_client(self, client_sock, client_addr):
        client_sock.settimeout(2.0)
        buffer = ""
        try:
            while self.running:
                try:
                    data = client_sock.recv(4096)
                    if not data:
                        break
                    buffer += data.decode('utf-8', errors='replace')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self._handle_raw_json(line)
                except socket.timeout:
                    continue
        except Exception as e:
            logger.debug(f"[SATC] TCP klient fel ({client_addr}): {e}")
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            logger.info(f"[SATC] TCP-anslutning från {client_addr} stängdes.")

    def _handle_raw_json(self, raw_str):
        with self.lock:
            self.stats['packets_received'] += 1

        try:
            payload = json.loads(raw_str)
        except Exception as e:
            logger.debug(f"[SATC] Ogiltig JSON: {e} -> {raw_str[:80]}")
            return

        self._handle_frame(payload)

    def _handle_frame(self, payload):
        parsed = parse_satc_frame(payload, only_messages=self.only_messages)
        if not parsed:
            return

        address = parsed['address']
        alias = parsed['alias']
        message = parsed['message']
        frequency = parsed['frequency']
        bitrate = parsed['bitrate']

        # Kontrollera larmord ENDAST mot den faktiska brödtexten
        body_to_check = parsed.get('body_text') or ""
        alert_match = check_alert_words(body_to_check)
        is_alert_hit = bool(alert_match)

        metadata = dict(parsed['metadata'])
        metadata['is_alert'] = is_alert_hit
        if alert_match:
            metadata['alert_word'] = alert_match.get('word')
            metadata['alert_color'] = alert_match.get('color')

        # Spara till databas (function_code=1 ENDAST vid träff i användarens larmordslista)
        try:
            msg_id, timestamp = save_message(
                address=address,
                message=message,
                alias=alias,
                function_code=1 if is_alert_hit else 0,
                bitrate=bitrate,
                frequency=frequency,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"[SATC] Databasfel vid lagring av meddelande: {e}")
            msg_id = None
            timestamp = datetime.now().isoformat()

        # Uppdatera intern statistik
        with self.lock:
            self.stats['messages_decoded'] += 1
            if parsed['les']:
                self.stats['last_les'] = parsed['les']
            self.stats['last_service'] = parsed['service_badge']
            self.stats['last_priority'] = parsed['priority']
            self.stats['last_message_time'] = datetime.now().strftime("%H:%M:%S")

        logger.info(f"[SATC DECODED] -> [{address}] {alias} | {parsed['service_title']} ({parsed['priority']})")

        # Publicera till MQTT
        publish_message(address, message, timestamp, alias, metadata=metadata)

        # Skicka via SSE till webbklienter
        msg_data = {
            'type': 'message',
            'id': msg_id,
            'timestamp': timestamp,
            'address': address,
            'message': message,
            'alias': alias,
            'frequency': frequency,
            'bitrate': bitrate,
            'is_alert': is_alert_hit,
            'alert_word': alert_match.get('word') if alert_match else None,
            'alert_color': alert_match.get('color') if alert_match else None,
            'is_duplicate': False,
            'repeat_count': 1,
            'last_timestamp': timestamp
        }
        msg_data.update(metadata)

        if self.callback:
            try:
                self.callback(msg_data)
            except Exception as e:
                logger.error(f"[SATC] Fel vid anrop till klient-callback: {e}")

# Global singleton
satc_receiver = SatCReceiver()

def init_satc(notify_callback=None):
    """Initierar Inmarsat STD-C-mottagaren från databasinställningar."""
    settings = get_settings()
    host = settings.get('satc_host', '0.0.0.0')
    port = settings.get('satc_port', '6558')
    only_messages = settings.get('satc_only_messages', 'true')
    enabled = settings.get('satc_enabled', 'true')

    if notify_callback:
        satc_receiver.set_callback(notify_callback)

    satc_receiver.start(host=host, port=port, only_messages=only_messages, enabled=enabled)

def restart_satc():
    """Startar om Inmarsat STD-C-mottagaren med uppdaterade inställningar."""
    settings = get_settings()
    satc_receiver.restart(
        host=settings.get('satc_host', '0.0.0.0'),
        port=settings.get('satc_port', '6558'),
        only_messages=settings.get('satc_only_messages', 'true'),
        enabled=settings.get('satc_enabled', 'true')
    )

def get_satc_status():
    """Returnerar aktuell status för Inmarsat STD-C-mottagaren."""
    return satc_receiver.get_status()

def send_test_satc_message(is_distress=False):
    """
    Skapar och injicerar ett realistiskt testmeddelande för Inmarsat EGC i databasen och liveflödet.
    """
    if is_distress:
        test_frame = {
            "station": "SatDump",
            "freq": 1537700000,
            "type": "EGC",
            "les_id": 2,
            "les_name": "Burum",
            "service": "SAR",
            "priority": "Distress",
            "navarea": "NAVAREA I",
            "text": "151800 UTC OCT\nDISTRESS ALERT RELAY\nMRCC OSTEND DE INMARSAT-C\nVESSEL 'NORDIC SEA' IN DISTRESS POSITION 58-34.2N 016-12.5E\nVESSEL TAKING IN WATER. 4 PERSONS ON BOARD IN LIFE RAFT.\nALL SHIPS IN VICINITY PROCEED AND ASSIST."
        }
    else:
        test_frame = {
            "station": "SatDump",
            "freq": 1537700000,
            "type": "EGC",
            "les_id": 2,
            "les_name": "Burum",
            "service": "SafetyNET",
            "priority": "Safety",
            "navarea": "NAVAREA I",
            "text": "151200 UTC OCT\nNAVAREA I 123\nENGLAND, SOUTH COAST. DOVER STRAIT.\nLIGHT BUOY OFF STATION AT 51-12.4N 001-24.8E.\nVESSELS IN VICINITY REQUESTED TO KEEP A SHARP LOOKOUT."
        }

    satc_receiver._handle_frame(test_frame)
    return {
        "status": "success",
        "message": f"Syntetiskt Inmarsat EGC-testmeddelande skickat ({'SAR / DISTRESS' if is_distress else 'SafetyNET / Sjöfartsvarning'})",
        "address": "LES: Burum",
        "alias": "SAR / Distress" if is_distress else "SafetyNET (EGC)",
        "frequency": "1537.700M"
    }
