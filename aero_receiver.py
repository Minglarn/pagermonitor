import socket
import json
import threading
import time
import logging
import re
import os
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
        parse_human_acars, lookup_airline, lookup_label,
        parse_acars_payload, ACARS_LABELS as PARSER_ACARS_LABELS
    )
except ImportError:
    PARSER_ACARS_LABELS = {}
    def parse_human_acars(msg, label=None, metadata=None, strip_prefix=False): return msg
    def lookup_airline(f): return ""
    def lookup_label(l): return ""
    def parse_acars_payload(text, label=None): return None

logger = logging.getLogger(__name__)

# Kända Ground Earth Stations (GES) för Inmarsat Classic Aero (decimal & oktal mappning)
GES_MAP = {
    1: "Santa Paula (USA)",
    2: "Southbury (USA)",
    3: "Goonhilly (UK)",
    4: "Sentosa (Singapore)",
    5: "Burum (Nederländerna)",
    6: "Perth (Australien)",
    10: "Aussaguel (Frankrike)",
    12: "Aussaguel (Frankrike)",
    14: "Fucino (Italien)",
    15: "Kumsan (Sydkorea)",
    16: "Eik (Norge)",
    20: "Eik (Norge)",
    23: "Raisting (Tyskland)",
    24: "Lake Cowichan (Kanada)",
    25: "Winnipeg (Kanada)",
    30: "Lake Cowichan (Kanada)",
    31: "Laurentides (Kanada)",
    37: "Laurentides (Kanada)",
    42: "Auckland (Nya Zeeland)",
    52: "Auckland (Nya Zeeland)"
}

def lookup_ges_name(ges_val):
    """
    Slår upp markstationsnamn baserat på GES ID (heltal, sträng eller oktal).
    """
    if not ges_val:
        return ""
    try:
        val_int = int(ges_val)
        if val_int in GES_MAP:
            return GES_MAP[val_int]
        # Prova oktal tolkning om sträng
        if isinstance(ges_val, str) and len(ges_val) <= 3:
            oct_int = int(ges_val, 8)
            if oct_int in GES_MAP:
                return GES_MAP[oct_int]
    except Exception:
        pass
    return str(ges_val).strip()

def format_aero_freq(freq_val):
    """
    Formaterar frekvensvärde från SatDump/JAERO till standardiserad MHz-sträng (t.ex. 1545.150M).
    Stöder Hz (1545150000), MHz (1545.150), och strängar ('1545.150', '1545.150M').
    """
    if freq_val is None or freq_val == '' or freq_val == 0:
        return '1545.150M'
    try:
        if isinstance(freq_val, str):
            f_str = freq_val.strip().rstrip('Hz').rstrip('hz')
            if f_str.upper().endswith('M'):
                return f_str.upper()
            f_num = float(f_str)
        else:
            f_num = float(freq_val)

        if f_num > 1000000:
            return f"{f_num / 1000000.0:.3f}M"
        elif f_num > 100:
            return f"{f_num:.3f}M"
        else:
            return f"{f_num}M"
    except Exception:
        return str(freq_val).strip()

def extract_aero_coordinates(text):
    """
    Extraherar lat/lon-koordinater ur avkodade flygmeddelanden (ADS-C, FMS och fritext).
    """
    if not text:
        return None, None

    # 1. Standard decimalformat: "Position: 58.1234, 18.5678" eller "Pos: 58.1234, 18.5678"
    m_pos = re.search(r'(?:\bPos(?:ition)?\b\s*:?\s*)(-?\d{1,2}\.\d{2,6})\s*,\s*(-?\d{1,3}\.\d{2,6})', text, re.IGNORECASE)
    if m_pos:
        try:
            c_lat = float(m_pos.group(1))
            c_lon = float(m_pos.group(2))
            if -90 <= c_lat <= 90 and -180 <= c_lon <= 180 and not (c_lat == 0 and c_lon == 0):
                return round(c_lat, 4), round(c_lon, 4)
        except (ValueError, TypeError):
            pass

    # 2. Riktat format med N/S och E/W: "N 58.123, E 18.567"
    m_nsew = re.search(r'\b([NS])\s*(\d{1,2}\.\d{2,6})\s*,\s*([EW])\s*(\d{1,3}\.\d{2,6})\b', text, re.IGNORECASE)
    if m_nsew:
        try:
            ns_dir, ns_val, ew_dir, ew_val = m_nsew.groups()
            c_lat = float(ns_val)
            if ns_dir.upper() == 'S':
                c_lat = -c_lat
            c_lon = float(ew_val)
            if ew_dir.upper() == 'W':
                c_lon = -c_lon
            if -90 <= c_lat <= 90 and -180 <= c_lon <= 180 and not (c_lat == 0 and c_lon == 0):
                return round(c_lat, 4), round(c_lon, 4)
        except (ValueError, TypeError):
            pass

    # 2b. Decimalformat med N/S och E/W efter siffror: "59.3500N 018.1000E"
    m_num_dir = re.search(r'\b(\d{1,2}\.\d{2,6})\s*([NS])\s*,?\s*(\d{1,3}\.\d{2,6})\s*([EW])\b', text, re.IGNORECASE)
    if m_num_dir:
        try:
            lat_val, ns_dir, lon_val, ew_dir = m_num_dir.groups()
            c_lat = float(lat_val)
            if ns_dir.upper() == 'S':
                c_lat = -c_lat
            c_lon = float(lon_val)
            if ew_dir.upper() == 'W':
                c_lon = -c_lon
            if -90 <= c_lat <= 90 and -180 <= c_lon <= 180 and not (c_lat == 0 and c_lon == 0):
                return round(c_lat, 4), round(c_lon, 4)
        except (ValueError, TypeError):
            pass

    # 3. Kompakt format (t.ex. 5834N 01612E)
    m_comp = re.search(r'\b(\d{2})(\d{2}(?:\.\d+)?)\s*([NS])\s*,?\s*(\d{3}|\d{2})(\d{2}(?:\.\d+)?)\s*([EW])\b', text, re.IGNORECASE)
    if m_comp:
        try:
            lat_deg, lat_min, lat_dir, lon_deg, lon_min, lon_dir = m_comp.groups()
            c_lat = float(lat_deg) + float(lat_min) / 60.0
            if lat_dir.upper() == 'S':
                c_lat = -c_lat
            c_lon = float(lon_deg) + float(lon_min) / 60.0
            if lon_dir.upper() == 'W':
                c_lon = -c_lon
            if -90 <= c_lat <= 90 and -180 <= c_lon <= 180 and not (c_lat == 0 and c_lon == 0):
                return round(c_lat, 4), round(c_lon, 4)
        except (ValueError, TypeError):
            pass

    return None, None

def parse_aero_frame(raw_data):
    """
    Avkodar ett inkommande JSON-paket från SatDump inmarsat_aero eller JAERO.
    Extraherar flygplan, markstation, frekvens, ACARS-data och berikar via acars_human_parser.
    """
    if not isinstance(raw_data, dict):
        return None

    # Stöd för inbäddat {"acars": { ... }} eller direkt objekt
    data = raw_data.get('acars', raw_data)
    if not isinstance(data, dict):
        return None

    # Extrahera satellit- och kanalmetadata
    freq_raw = raw_data.get('freq') or raw_data.get('frequency') or data.get('freq')
    freq_str = format_aero_freq(freq_raw)
    channel = raw_data.get('channel') or data.get('channel') or 'P-Channel'
    su_type = raw_data.get('su_type') or raw_data.get('type') or ''

    # Markstation (GES)
    ges_id = raw_data.get('ges_id') or raw_data.get('ges') or data.get('ges_id') or data.get('ges')
    ges_name = raw_data.get('ges_name') or lookup_ges_name(ges_id)
    if not ges_name and ges_id:
        ges_name = f"GES #{ges_id}"

    # Flygplan (AES / ICAO / Flight / Tail)
    aes_id = raw_data.get('aes_id') or raw_data.get('icao') or data.get('aes_id') or data.get('icao')
    if aes_id:
        # Formatera hexadecimal ICAO i versaler
        aes_str = str(aes_id).strip().upper().lstrip('0X')
    else:
        aes_str = ''

    tail = str(data.get('tail') or data.get('reg') or '').strip().lstrip('.')
    flight = str(data.get('flight') or '').strip().upper()
    label = str(data.get('label') or '').strip().upper()
    msgno = str(data.get('msgno') or '').strip()
    block_id = str(data.get('block_id') or '').strip()
    raw_text = str(data.get('text') or data.get('message') or '').strip()
    station_id = str(data.get('station_id') or data.get('station') or ges_name or '').strip()

    # Signalvärden
    level = raw_data.get('level') or data.get('level') or raw_data.get('snr')
    error_cnt = raw_data.get('error') or data.get('error')
    mode = str(data.get('mode') or '').strip()
    ack = str(data.get('ack') or '').strip()

    # Filtrera bort tomma Keep-Alive/signaleringspaket om det inte finns någon nyttolast eller adresser
    if not raw_text and not flight and not tail and not aes_str and not label:
        return None

    label_desc = lookup_label(label)
    airline_name = lookup_airline(flight) if flight else ""

    # Konstruera logisk adress och visningsalias
    if flight and tail:
        address = f"{flight} ({tail})"
    elif flight:
        address = flight
    elif tail:
        address = tail
    elif aes_str:
        address = f"ICAO: {aes_str}"
    elif ges_name:
        address = f"GES: {ges_name}"
    else:
        address = "INMARSAT-AERO"

    if airline_name and tail:
        alias = f"{airline_name} ({tail})"
    elif airline_name:
        alias = airline_name
    elif tail:
        alias = tail
    elif ges_name:
        alias = f"AERO / {ges_name}"
    else:
        alias = "Inmarsat Aero"

    # Tolka meddelandetext via vår befintliga acars_human_parser
    parsed_human = ""
    if raw_text:
        parsed_human = parse_human_acars(raw_text, label=label, metadata=data, strip_prefix=True)

    if not parsed_human:
        if label == '_d':
            parsed_human = "Systemkvittens: Länk aktiv (ACK)"
        elif label == 'Q0':
            parsed_human = "Länktest: Inmarsat Aero Link Test (Q0)"
        elif label_desc:
            parsed_human = f"{label_desc} [{label}]"
        elif label:
            parsed_human = f"Aero ACARS-meddelande [{label}]"
        elif su_type:
            parsed_human = f"Inmarsat Aero Signaleringspaket: {su_type}"
        else:
            parsed_human = "Inmarsat Aero signal mottagen"

    # Extrahera koordinater från parsed_human eller råtext
    lat, lon = extract_aero_coordinates(parsed_human)
    if lat is None or lon is None:
        lat, lon = extract_aero_coordinates(raw_text)

    # Kontrollera om strukturerad payload har lat/lon
    decoded_fields = data.get('decoded_fields') or parse_acars_payload(raw_text, label=label)
    if decoded_fields:
        if decoded_fields.get('lat') is not None and decoded_fields.get('lon') is not None and lat is None:
            lat = decoded_fields['lat']
            lon = decoded_fields['lon']

    b_rate = f"AERO-{channel}" if channel else 'AERO-ACARS'

    metadata = {
        'protocol': 'AERO',
        'bitrate': b_rate,
        'source_type': 'AERO',
        'frequency': freq_str,
        'freq': freq_raw,
        'channel': channel,
        'ges_id': ges_id,
        'ges_name': ges_name,
        'aes_id': aes_str or None,
        'icao': aes_str or None,
        'flight': flight or None,
        'reg': tail or None,
        'tail': tail or None,
        'label': label or None,
        'label_desc': label_desc or None,
        'msgno': msgno or None,
        'block_id': block_id or None,
        'station': ges_name or station_id or None,
        'station_id': ges_name or station_id or None,
        'level': level,
        'error': error_cnt,
        'mode': mode or None,
        'ack': ack or None,
        'lat': lat,
        'lon': lon,
        'alt_ft': decoded_fields.get('altitude_ft') if decoded_fields else None,
        'eta': decoded_fields.get('eta') if decoded_fields else None,
        'decoded_fields': decoded_fields,
        'airline': airline_name or None,
        'sdr_name': 'Inmarsat AERO'
    }

    return {
        'address': address,
        'message': parsed_human,
        'raw_text': raw_text,
        'alias': alias,
        'flight': flight,
        'reg': tail,
        'icao': aes_str or None,
        'airline': airline_name,
        'label': label,
        'label_desc': label_desc,
        'frequency': freq_str,
        'station_id': ges_name or station_id,
        'protocol': 'AERO',
        'source_type': 'AERO',
        'bitrate': b_rate,
        'lat': lat,
        'lon': lon,
        'metadata': metadata
    }

class AeroReceiver:
    """
    Dedikerad nätverksmottagare för Inmarsat AERO ACARS från SatDump eller JAERO.
    Stödjer UDP-lyssning, inkommande TCP-server samt anslutning som TCP-klient.
    """
    def __init__(self):
        self.running = False
        self.host = "0.0.0.0"
        self.port = 6559
        self.only_messages = True
        self.enabled = True
        self.lock = threading.Lock()
        self.threads = []
        self.udp_sock = None
        self.tcp_server_sock = None
        self.tcp_client_sock = None
        self.callback = None
        self.recent_messages = {}  # (address, hash) -> (msg_id, timestamp, repeat_count)
        self.stats = {
            'status': 'stopped',
            'packets_received': 0,
            'messages_decoded': 0,
            'last_heard': None,
            'last_ges': None,
            'last_flight': None,
            'last_message_time': None,
            'error_message': None
        }

    def set_callback(self, cb):
        self.callback = cb

    def start(self, host="0.0.0.0", port=6559, only_messages=True, enabled=True):
        with self.lock:
            if self.running:
                return
            self.host = str(host).strip() if host else "0.0.0.0"
            try:
                self.port = int(port)
            except (ValueError, TypeError):
                self.port = 6559
            self.only_messages = (str(only_messages).lower() in ('true', '1', 'yes'))
            self.enabled = (str(enabled).lower() in ('true', '1', 'yes'))

            if not self.enabled:
                self.stats['status'] = 'disabled'
                logger.info("[AERO] Inmarsat AERO-mottagaren är inaktiverad i inställningarna.")
                return

            self.running = True
            self.stats['status'] = 'running'
            self.stats['error_message'] = None

        logger.info(f"[AERO] Startar Inmarsat AERO-lyssnare (host={self.host}, port={self.port})...")

        # Starta nätverkstrådar baserat på konfiguration
        if self.host in ("0.0.0.0", "", "::"):
            # Lyssna lokalt på både UDP och inkommande TCP
            t_udp = threading.Thread(target=self._udp_listen_loop, daemon=True, name="Aero-UDP-Listen")
            t_tcp = threading.Thread(target=self._tcp_server_loop, daemon=True, name="Aero-TCP-Server")
            self.threads = [t_udp, t_tcp]
            t_udp.start()
            t_tcp.start()
        else:
            # Specifik värd angiven: anslut som TCP-klient och lyssna på UDP som fallback
            t_client = threading.Thread(target=self._tcp_client_loop, daemon=True, name="Aero-TCP-Client")
            t_udp = threading.Thread(target=self._udp_listen_loop, daemon=True, name="Aero-UDP-Listen")
            self.threads = [t_client, t_udp]
            t_client.start()
            t_udp.start()

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            self.stats['status'] = 'stopped'

        # Stäng sockets
        if self.udp_sock:
            try:
                self.udp_sock.close()
            except Exception:
                pass
            self.udp_sock = None

        if self.tcp_server_sock:
            try:
                self.tcp_server_sock.close()
            except Exception:
                pass
            self.tcp_server_sock = None

        if self.tcp_client_sock:
            try:
                self.tcp_client_sock.close()
            except Exception:
                pass
            self.tcp_client_sock = None

        for t in self.threads:
            if t.is_alive():
                t.join(timeout=1.0)
        self.threads = []
        logger.info("[AERO] Inmarsat AERO-lyssnaren stoppad.")

    def restart(self, host="0.0.0.0", port=6559, only_messages=True, enabled=True):
        self.stop()
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
            logger.info(f"[AERO] UDP-lyssnare bunden till 0.0.0.0:{self.port}")
        except Exception as e:
            logger.error(f"[AERO] Kunde inte binda UDP-socket till port {self.port}: {e}")
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
                    logger.debug(f"[AERO] UDP mottagningsfel: {e}")

    def _tcp_server_loop(self):
        try:
            self.tcp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_server_sock.bind(('0.0.0.0', self.port))
            self.tcp_server_sock.listen(5)
            self.tcp_server_sock.settimeout(1.0)
            logger.info(f"[AERO] TCP-server lyssnar på 0.0.0.0:{self.port}")
        except Exception as e:
            logger.debug(f"[AERO] Kunde inte starta TCP-server på port {self.port}: {e}")
            return

        while self.running:
            try:
                client_sock, client_addr = self.tcp_server_sock.accept()
                logger.info(f"[AERO] Ny TCP-anslutning från {client_addr}")
                t = threading.Thread(target=self._handle_tcp_client, args=(client_sock, client_addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"[AERO] TCP server accept-fel: {e}")

    def _tcp_client_loop(self):
        while self.running:
            sock = None
            try:
                logger.info(f"[AERO] Försöker ansluta till SatDump AERO TCP-ström på {self.host}:{self.port}...")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                sock.connect((self.host, self.port))
                sock.settimeout(5.0)
                self.tcp_client_sock = sock

                with self.lock:
                    self.stats['status'] = 'connected'
                    self.stats['error_message'] = None

                logger.info(f"[AERO] Ansluten till SatDump AERO TCP på {self.host}:{self.port}!")

                buffer = ""
                while self.running:
                    try:
                        data = sock.recv(4096)
                    except (socket.timeout, TimeoutError):
                        continue

                    if not data:
                        logger.warning(f"[AERO] Fjärrvärd stängde anslutningen ({self.host}:{self.port}).")
                        break

                    buffer += data.decode('utf-8', errors='replace')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line_str = line.strip()
                        if line_str:
                            self._handle_raw_json(line_str)
            except Exception as e:
                if self.running:
                    logger.debug(f"[AERO] TCP anslutningsfel mot {self.host}:{self.port}: {e}")
                    with self.lock:
                        self.stats['status'] = 'reconnecting'
                        self.stats['error_message'] = str(e)
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                self.tcp_client_sock = None

            if self.running:
                time.sleep(5.0)

    def _handle_tcp_client(self, sock, addr):
        buffer = ""
        sock.settimeout(10.0)
        try:
            while self.running:
                try:
                    data = sock.recv(4096)
                except (socket.timeout, TimeoutError):
                    continue

                if not data:
                    break

                buffer += data.decode('utf-8', errors='replace')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line_str = line.strip()
                    if line_str:
                        self._handle_raw_json(line_str)
        except Exception as e:
            logger.debug(f"[AERO] Klientanslutning från {addr} avslutad: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _handle_raw_json(self, line):
        with self.lock:
            self.stats['packets_received'] = self.stats.get('packets_received', 0) + 1
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return

        self._handle_frame(payload)

    def _handle_frame(self, frame):
        with self.lock:
            if not self.stats.get('packets_received'):
                self.stats['packets_received'] = 1
        parsed = parse_aero_frame(frame)
        if not parsed:
            return

        # Om användaren valt att bara spara meddelanden, filtrera bort rena signaler/länktest utan text
        if self.only_messages and not parsed.get('raw_text'):
            label = parsed.get('label')
            # Släpp igenom viktiga flygmeddelanden även om fritext saknas
            if label not in ('_d', 'Q0', 'H1', '15', '16', '21', 'RA', '5U'):
                return

        address = parsed['address']
        message = parsed['message']
        alias = parsed['alias']
        frequency = parsed['frequency']
        bitrate = parsed['bitrate']
        metadata = parsed['metadata']

        # Alias-ersättning från databasen om konfigurerad
        alias_info = get_alias_info(address)
        if alias_info:
            if alias_info.get('is_hidden'):
                return
            if alias_info.get('alias'):
                alias = alias_info['alias']

        # Larmordskontroll
        alert_match = check_alert_words(message, extra_fields=[address, alias, parsed.get('flight'), parsed.get('reg')])
        is_alert_hit = bool(alert_match)
        alert_word = alert_match.get('word') if alert_match else None
        alert_color = alert_match.get('color') if alert_match else None

        # Duplikathantering
        msg_hash = f"{address}_{parsed.get('raw_text') or message}"
        now = time.time()
        is_duplicate = False
        existing_msg_id = None

        settings = get_settings()
        dup_window = int(settings.get('duplicate_window', 120))
        dup_handling = settings.get('duplicate_handling', 'merge')

        if msg_hash in self.recent_messages:
            last_id, last_time, r_count = self.recent_messages[msg_hash]
            if now - last_time <= dup_window:
                is_duplicate = True
                existing_msg_id = last_id
                if dup_handling == 'ignore':
                    return
                elif dup_handling == 'merge':
                    new_count = increment_message_repeat(last_id)
                    self.recent_messages[msg_hash] = (last_id, now, new_count)

                    # Publicera uppdaterad repeat till SSE
                    if self.callback:
                        self.callback({
                            'type': 'repeat',
                            'id': last_id,
                            'repeat_count': new_count,
                            'last_timestamp': datetime.now().isoformat()
                        })
                    return

        # Spara till databasen
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
            logger.error(f"[AERO] Databasfel vid sparning av meddelande: {e}")
            msg_id = None
            timestamp = datetime.now().isoformat()

        if msg_id:
            self.recent_messages[msg_hash] = (msg_id, now, 1)

        # Uppdatera intern statistik
        with self.lock:
            self.stats['messages_decoded'] += 1
            self.stats['last_heard'] = address
            if parsed.get('station_id'):
                self.stats['last_ges'] = parsed['station_id']
            if parsed.get('flight'):
                self.stats['last_flight'] = parsed['flight']
            self.stats['last_message_time'] = datetime.now().strftime("%H:%M:%S")

        logger.info(f"[AERO DECODED] -> [{address}] {alias} | {parsed.get('label_desc') or parsed.get('label') or 'ACARS'}")

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
            'alert_word': alert_word,
            'alert_color': alert_color,
            'is_duplicate': False,
            'repeat_count': 1,
            'last_timestamp': timestamp
        }
        msg_data.update(metadata)

        if self.callback:
            try:
                self.callback(msg_data)
            except Exception as e:
                logger.error(f"[AERO] Fel vid anrop till klient-callback: {e}")

# Global singleton
aero_receiver = AeroReceiver()

def init_aero(notify_callback=None):
    """Initierar Inmarsat AERO-mottagaren från databasinställningar."""
    settings = get_settings()
    host = settings.get('aero_host', '0.0.0.0')
    port = settings.get('aero_port', '6559')
    only_messages = settings.get('aero_only_messages', 'true')
    enabled = settings.get('aero_enabled', 'true')

    if notify_callback:
        aero_receiver.set_callback(notify_callback)

    aero_receiver.start(host=host, port=port, only_messages=only_messages, enabled=enabled)

def restart_aero():
    """Startar om Inmarsat AERO-mottagaren med uppdaterade inställningar."""
    settings = get_settings()
    aero_receiver.restart(
        host=settings.get('aero_host', '0.0.0.0'),
        port=settings.get('aero_port', '6559'),
        only_messages=settings.get('aero_only_messages', 'true'),
        enabled=settings.get('aero_enabled', 'true')
    )

def get_aero_status():
    """Returnerar aktuell status för Inmarsat AERO-mottagaren."""
    return aero_receiver.get_status()

def send_test_aero_message(is_pos_report=False):
    """
    Skapar och injicerar ett realistiskt syntetiskt Inmarsat Aero ACARS-testmeddelande i databasen och liveflödet.
    """
    if is_pos_report:
        # Transatlantisk SAS positionsrapport (ADS-C / FMS)
        test_frame = {
            "station": "SatDump",
            "freq": 1545150000,
            "channel": "P-Channel",
            "ges_id": 5,
            "ges_name": "Burum",
            "aes_id": "4ACA8E",
            "acars": {
                "flight": "SK903",
                "tail": "SE-RTN",
                "label": "H1",
                "msgno": "M42A",
                "block_id": "1",
                "text": "FMS POS RPT\nFLIGHT SK903\nPOS 59.3500N 018.1000E\nALT FL380\nETA KELEB 18:45 UTC\nWIND 270/45\nTEMP -56C"
            }
        }
    else:
        # Flygledningsklarering / CPDLC över satellit
        test_frame = {
            "station": "SatDump",
            "freq": 1545150000,
            "channel": "P-Channel",
            "ges_id": 2,
            "ges_name": "Southbury",
            "aes_id": "461F6D",
            "acars": {
                "flight": "AY1422",
                "tail": "OH-LXL",
                "label": "21",
                "msgno": "M15B",
                "block_id": "2",
                "text": "/CPDLC OCEANIC CLEARANCE CLR TO BOSTON VIA 58N020W 57N030W 55N040W 52N050W MAINTAIN FL370 MACH 0.80 CROSS 58N020W AT 1820"
            }
        }

    aero_receiver._handle_frame(test_frame)
    return {
        "status": "success",
        "message": f"Syntetiskt Inmarsat AERO-testmeddelande skickat ({'FMS / Positionsrapport' if is_pos_report else 'CPDLC / Oceanic Clearance'})",
        "address": "SK903 (SE-RTN)" if is_pos_report else "AY1422 (OH-LXL)",
        "alias": "Scandinavian Airlines (SE-RTN)" if is_pos_report else "Finnair (OH-LXL)",
        "frequency": "1545.150M"
    }
