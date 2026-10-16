import socket
import json
import threading
import time
import logging
import re
from datetime import datetime
from database import (
    save_message, get_settings, get_connection
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
    """Formaterar frekvens till t.ex. 1537.700M så att den passar RF ACTIVITY och filter."""
    if not raw_freq:
        return "1537.700M"
    s = str(raw_freq).strip().replace("MHz", "").replace("mhz", "").replace("Hz", "").replace("hz", "").replace("M", "").replace(" ", "")
    try:
        val = float(s)
        if val > 1_000_000_000:
            return f"{val / 1e6:.3f}M"
        elif val > 1_000_000:
            return f"{val / 1e3:.3f}M"
        elif val > 100:
            return f"{val:.3f}M"
        else:
            return f"{val:.3f}M"
    except (ValueError, TypeError):
        return str(raw_freq).strip()

def normalize_satc_priority(raw_priority, text=""):
    """
    Normaliserar prioritet:
    DISTRESS, URGENCY, Safety, Routine.
    """
    p_str = str(raw_priority or "").strip().upper()
    t_str = str(text or "").upper()

    if p_str in ("3", "DISTRESS") or "DISTRESS" in p_str or "MAYDAY" in p_str or "MAYDAY" in t_str or "DISTRESS" in t_str:
        return "DISTRESS", True
    if p_str in ("2", "URGENCY") or "URGENCY" in p_str or "PAN PAN" in p_str or "PAN PAN" in t_str or "PAN-PAN" in t_str:
        return "URGENCY", True
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

def parse_satc_frame(payload, only_messages=True):
    """
    Parsar ett avkodat SatDump Inmarsat STD-C / EGC-ramverk i JSON-format.
    Returnerar dict med parsed info eller None om ramen filtrerades bort.
    """
    if not isinstance(payload, dict):
        return None

    # Extrahera rå meddelandetext ur alla tänkbara fält
    raw_text = None
    for k in ("message", "text", "msg", "payload", "data", "content", "body", "egc_text", "egc_message"):
        val = payload.get(k)
        if isinstance(val, str) and val.strip():
            raw_text = val.strip()
            break
        elif isinstance(val, dict):
            # Möjlig nästlad struktur
            for sub_k in ("text", "message", "msg", "payload", "data"):
                sub_val = val.get(sub_k)
                if isinstance(sub_val, str) and sub_val.strip():
                    raw_text = sub_val.strip()
                    break
        if raw_text:
            break

    type_str = str(payload.get("type") or payload.get("packet_type") or payload.get("service") or "").strip()

    # Kontrollera om det är en tom TDM-synk-/signaleringsram
    is_empty_signalling = False
    if not raw_text:
        is_empty_signalling = True
    elif any(sig in type_str.lower() for sig in ("bulletin board", "signalling channel", "interstation", "tdm frame", "sync", "idle")):
        if len(raw_text.strip()) < 5:
            is_empty_signalling = True

    if only_messages and is_empty_signalling:
        logger.debug(f"[SATC] Ignorerar tom TDM- eller synkram: {type_str}")
        return None

    body_text = raw_text or f"TDM Händelse: {type_str}"

    # Extrahera Frekvens
    raw_freq = payload.get("freq") or payload.get("frequency") or payload.get("rx_freq")
    freq_str = format_satc_frequency(raw_freq)

    # Extrahera Jordstation (LES)
    les_id = payload.get("les_id") or payload.get("les")
    les_name = payload.get("les_name") or payload.get("les_station")

    if not les_name and les_id is not None:
        try:
            les_id_int = int(les_id)
            les_name = LES_MAP.get(les_id_int)
        except (ValueError, TypeError):
            pass

    les_display = les_name if les_name else (f"LES-{les_id}" if les_id is not None else None)

    # Extrahera Område (NAVAREA / METAREA / Area)
    navarea = payload.get("navarea") or payload.get("area") or payload.get("metarea") or payload.get("ocean_region")
    if not navarea:
        m_area = re.search(r'\b(NAVAREA\s+[A-Z0-9]+|METAREA\s+[A-Z0-9]+)\b', body_text, re.IGNORECASE)
        if m_area:
            navarea = m_area.group(1).upper()

    navarea_str = str(navarea).strip() if navarea else ""

    # Extrahera Prioritet
    raw_priority = payload.get("priority") or payload.get("priority_name") or payload.get("prio")
    priority_norm, is_alert = normalize_satc_priority(raw_priority, body_text)

    # Extrahera Tjänst / Kategori
    service_title, service_badge, default_alias = classify_satc_service(payload, body_text)

    # Extrahera Koordinater
    lat, lon = extract_coordinates(body_text)

    # Skapa Adress (Capcode) och Alias
    # Adress: T.ex. "LES: Burum" eller "INMARSAT-C"
    # Alias: T.ex. "SafetyNET (EGC)", "FleetNET", "SAR / Distress"
    if les_display:
        address = f"LES: {les_display}"
    elif navarea_str:
        address = f"EGC: {navarea_str}"
    else:
        address = "INMARSAT-C"

    alias = default_alias

    # Bygg svensk sammanfattningsrad överst
    # T.ex. "[Inmarsat SafetyNET / Sjöfartsvarning] Område: NAVAREA I | Prioritet: Safety"
    summary_parts = []
    if navarea_str:
        summary_parts.append(f"Område: {navarea_str}")
    if les_display:
        summary_parts.append(f"Jordstation: {les_display}")
    summary_parts.append(f"Prioritet: {priority_norm}")

    summary_header = f"[{service_title}] " + " | ".join(summary_parts)

    # Skapa rådatasträng i kompakt JSON
    try:
        raw_json_str = json.dumps(payload, ensure_ascii=False)
    except Exception:
        raw_json_str = str(payload)

    # Bygg komplett meddelandetext med svensk sammanfattning och Rådata:
    full_message = f"{summary_header}\n{body_text}\nRådata: {raw_json_str}"

    metadata = {
        'protocol': 'SATC',
        'frequency': freq_str,
        'priority': priority_norm,
        'satc_priority': priority_norm,
        'satc_service': service_badge,
        'is_alert': is_alert
    }
    if navarea_str:
        metadata['navarea'] = navarea_str
    if les_display:
        metadata['les_name'] = les_display
    if les_id is not None:
        metadata['les_id'] = les_id
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
        self.port = 5558
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
            'port': 5558,
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

    def start(self, host='0.0.0.0', port=5558, only_messages=True, enabled=True):
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

        # Stäng UDP-socket
        if self.udp_sock:
            try:
                self.udp_sock.close()
            except Exception:
                pass
            self.udp_sock = None

        # Stäng TCP-serversocket
        if self.tcp_server_sock:
            try:
                self.tcp_server_sock.close()
            except Exception:
                pass
            self.tcp_server_sock = None

        # Stäng TCP-klientsocket
        if self.tcp_client_sock:
            try:
                self.tcp_client_sock.close()
            except Exception:
                pass
            self.tcp_client_sock = None

        logger.info("[SATC] Inmarsat STD-C mottagare stoppad.")

    def restart(self, host='0.0.0.0', port=5558, only_messages=True, enabled=True):
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
        backoff = 2
        while self.running:
            try:
                logger.info(f"[SATC] Försöker ansluta till SatDump TCP-ström på {self.host}:{self.port}...")
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5.0)
                s.connect((self.host, self.port))
                s.settimeout(None)
                self.tcp_client_sock = s
                backoff = 2
                logger.info(f"[SATC] Ansluten till SatDump TCP på {self.host}:{self.port}")

                file_obj = s.makefile('r', encoding='utf-8', errors='replace')
                for line in file_obj:
                    if not self.running:
                        break
                    line_str = line.strip()
                    if line_str:
                        self._handle_raw_json(line_str)
            except Exception as e:
                if self.running:
                    logger.debug(f"[SATC] TCP-klientanslutning mot {self.host}:{self.port} avbröts eller misslyckades: {e}. Nytt försök om {backoff}s.")
            finally:
                if self.tcp_client_sock:
                    try:
                        self.tcp_client_sock.close()
                    except Exception:
                        pass
                    self.tcp_client_sock = None

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
        metadata = parsed['metadata']

        # Spara till databas
        try:
            msg_id, timestamp = save_message(
                address=address,
                message=message,
                alias=alias,
                function_code=1 if parsed['is_alert'] else 0,
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
    port = settings.get('satc_port', '5558')
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
        port=settings.get('satc_port', '5558'),
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
