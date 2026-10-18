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


def format_acars_freq(freq_val):
    """
    Formaterar frekvensvärde från acarsdec/acars_router till läsbar sträng (t.ex. 131.525M).
    Stöder Hz (131525000), MHz (131.525), och strängar ('131.525', '131.525M').
    """
    if freq_val is None or freq_val == '' or freq_val == 0:
        return '131.525M'
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


def parse_acars_message(raw_data):
    """
    Avkodar och berikar ett inkommande JSON-paket från acarsdec via acars_router (port 15550).
    Returnerar en standardiserad meddelandeordbok för PagerMonitor eller None om ogiltigt.
    """
    if not isinstance(raw_data, dict):
        return None

    # Stöd för både direkt format och inbäddat i {"acars": { ... }}
    data = raw_data.get('acars', raw_data)
    if not isinstance(data, dict):
        return None

    tail = str(data.get('tail') or data.get('reg') or '').strip().lstrip('.')
    flight = str(data.get('flight') or '').strip().upper()
    label = str(data.get('label') or '').strip().upper()
    msgno = str(data.get('msgno') or '').strip()
    block_id = str(data.get('block_id') or '').strip()
    raw_text = str(data.get('text') or '').strip()
    station_id = str(data.get('station_id') or '').strip()
    channel = data.get('channel')
    freq_raw = data.get('freq')
    freq_str = format_acars_freq(freq_raw)
    level = data.get('level')
    error_cnt = data.get('error')
    mode = str(data.get('mode') or '').strip()
    ack = str(data.get('ack') or '').strip()

    # Om varken flyg, registrering, etikett eller text finns, är det brus/ogiltigt
    if not tail and not flight and not label and not raw_text:
        return None

    label_desc = lookup_label(label)
    airline_name = lookup_airline(flight) if flight else ""

    # Konstruera adress
    if flight and tail:
        address = f"{flight} ({tail})"
    elif flight:
        address = flight
    elif tail:
        address = tail
    elif station_id:
        address = f"GS: {station_id}"
    else:
        address = "VHF-ACARS"

    # Bestäm alias
    if airline_name:
        alias = airline_name
    elif tail:
        alias = tail
    else:
        alias = "VHF ACARS"

    # Tolka meddelandetext via human parser
    parsed_human = ""
    if raw_text:
        parsed_human = parse_human_acars(raw_text, label=label, metadata=data, strip_prefix=True)

    if not parsed_human:
        if label == '_d':
            parsed_human = "Kvittens (ACK)"
        elif label == 'Q0':
            parsed_human = "Länktest (ACARS Link Test)"
        elif label_desc:
            parsed_human = f"{label_desc} [{label}]"
        elif label:
            parsed_human = f"ACARS Meddelande [{label}]"
        else:
            parsed_human = "ACARS Signal mottagen"

    # Kontrollera om position/koordinater kan extraheras ur texten
    lat = None
    lon = None
    m_pos = re.search(r'(?:\bPos(?:ition)?\b\s*:?\s*)(-?\d{1,2}\.\d{2,6})\s*,\s*(-?\d{1,3}\.\d{2,6})', parsed_human, re.IGNORECASE)
    if m_pos:
        try:
            c_lat = float(m_pos.group(1))
            c_lon = float(m_pos.group(2))
            if -90 <= c_lat <= 90 and -180 <= c_lon <= 180 and not (c_lat == 0 and c_lon == 0):
                lat = round(c_lat, 4)
                lon = round(c_lon, 4)
        except (ValueError, TypeError):
            pass

    if lat is None or lon is None:
        m_nsew = re.search(r'\b([NS])\s*(\d{1,2}\.\d{2,6})\s*,\s*([EW])\s*(\d{1,3}\.\d{2,6})\b', parsed_human, re.IGNORECASE)
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
                    lat = round(c_lat, 4)
                    lon = round(c_lon, 4)
            except (ValueError, TypeError):
                pass

    # Kontrollera strukturerad payload
    decoded_fields = data.get('decoded_fields') or parse_acars_payload(raw_text, label=label)
    if decoded_fields:
        if decoded_fields.get('lat') is not None and decoded_fields.get('lon') is not None and lat is None:
            lat = decoded_fields['lat']
            lon = decoded_fields['lon']

    metadata = {
        'protocol': 'ACARS',
        'bitrate': 'VHF-ACARS',
        'source_type': 'ACARS',
        'frequency': freq_str,
        'freq': freq_raw,
        'flight': flight or None,
        'reg': tail or None,
        'tail': tail or None,
        'label': label or None,
        'label_desc': label_desc or None,
        'msgno': msgno or None,
        'block_id': block_id or None,
        'station': station_id or None,
        'station_id': station_id or None,
        'channel': channel,
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
        'sdr_name': 'VHF-ACARS'
    }

    return {
        'address': address,
        'message': parsed_human,
        'raw_text': raw_text,
        'alias': alias,
        'flight': flight,
        'reg': tail,
        'airline': airline_name,
        'label': label,
        'label_desc': label_desc,
        'frequency': freq_str,
        'station_id': station_id,
        'protocol': 'ACARS',
        'source_type': 'ACARS',
        'bitrate': 'VHF-ACARS',
        'lat': lat,
        'lon': lon,
        'metadata': metadata
    }


class ACARSReceiver:
    """
    Dedikerad TCP-klient/receiver för VHF ACARS som ansluter till acars_router (15550).
    Robust läsloop med timeout och automatisk återanslutning.
    """
    def __init__(self):
        self.host = '192.168.1.242'
        self.port = 15550
        self.enabled = True
        self.running = False
        self.callback = None

        self.sock = None
        self.thread = None
        self._thread_id = None
        self._worker_session = 0

        self.cache_lock = threading.Lock()
        self.recent_cache = {}

        self.stats = {
            'status': 'stopped',
            'connected': False,
            'status_text': 'Stoppad',
            'host': '192.168.1.242',
            'port': 15550,
            'packets_received': 0,
            'messages_decoded': 0,
            'last_flight': '-',
            'last_tail': '-',
            'last_label': '-',
            'last_freq': '-',
            'last_message_time': 'Ingen aktivitet ännu',
            'error_message': None
        }
        self.lock = threading.Lock()

    def set_callback(self, cb):
        self.callback = cb

    def start(self, host=None, port=None, enabled=None):
        env_host = os.environ.get('ACARS_HOST')
        env_port = os.environ.get('ACARS_PORT')
        env_enabled = os.environ.get('ACARS_ENABLED')

        cur_host = host if host is not None else (env_host or self.host)
        cur_port = port if port is not None else (env_port or self.port)
        cur_enabled = enabled if enabled is not None else (env_enabled or self.enabled)

        self.host = str(cur_host).strip() if cur_host else '192.168.1.242'
        try:
            self.port = int(cur_port)
        except (ValueError, TypeError):
            self.port = 15550

        self.enabled = (str(cur_enabled).lower() in ('true', '1', 'yes'))

        if not self.enabled:
            logger.info("[ACARS] VHF ACARS-mottagaren är avaktiverad i inställningarna.")
            with self.lock:
                self.stats['status'] = 'disabled'
                self.stats['connected'] = False
                self.stats['status_text'] = 'Avaktiverad'
            return

        old_thread = None
        with self.lock:
            self._worker_session += 1
            cur_session = self._worker_session
            self.running = True
            self.stats['status'] = 'connecting'
            self.stats['connected'] = False
            self.stats['status_text'] = f'Ansluter till {self.host}:{self.port}...'
            self.stats['host'] = self.host
            self.stats['port'] = self.port
            self.stats['error_message'] = None

            if self.sock:
                try: self.sock.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                try: self.sock.close()
                except Exception: pass
                self.sock = None

            if self.thread and self.thread.is_alive():
                old_thread = self.thread
            self.thread = None

        if old_thread and threading.current_thread() != old_thread:
            old_thread.join(timeout=1.5)

        with self.lock:
            self.thread = threading.Thread(
                target=self._worker_loop,
                args=(cur_session,),
                daemon=True,
                name="ACARS-Receiver-Thread"
            )
            self.thread.start()

        logger.info(f"[ACARS] VHF ACARS-mottagare startad för {self.host}:{self.port}")

    def stop(self):
        old_thread = None
        with self.lock:
            self._worker_session += 1
            self._thread_id = None
            self.running = False
            self.stats['status'] = 'stopped'
            self.stats['connected'] = False
            self.stats['status_text'] = 'Stoppad'

            if self.sock:
                try: self.sock.shutdown(socket.SHUT_RDWR)
                except Exception: pass
                try: self.sock.close()
                except Exception: pass
                self.sock = None

            if self.thread and self.thread.is_alive():
                old_thread = self.thread
            self.thread = None

        if old_thread and threading.current_thread() != old_thread:
            old_thread.join(timeout=1.5)

        logger.info("[ACARS] VHF ACARS-mottagare stoppad.")

    def restart(self, host=None, port=None, enabled=None):
        self.stop()
        time.sleep(0.3)
        self.start(host=host, port=port, enabled=enabled)

    def get_status(self):
        with self.lock:
            s = dict(self.stats)
            s['enabled'] = self.enabled
            s['running'] = self.running
            return s

    def _worker_loop(self, session_id):
        current_thread_id = threading.current_thread().ident
        with self.lock:
            if not self.running or session_id != self._worker_session:
                return
            self._thread_id = current_thread_id

        backoff = 5
        while self.running and session_id == self._worker_session and self._thread_id == current_thread_id:
            sock = None
            t_connect = 0
            try:
                with self.lock:
                    self.stats['status'] = 'connecting'
                    self.stats['status_text'] = f'Ansluter till {self.host}:{self.port}...'

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                sock.connect((self.host, self.port))
                t_connect = time.time()
                sock.settimeout(5.0)

                with self.lock:
                    self.sock = sock
                    self.stats['status'] = 'running'
                    self.stats['connected'] = True
                    self.stats['status_text'] = f'Ansluten till {self.host}:{self.port}'
                    self.stats['error_message'] = None

                backoff = 5
                logger.info(f"[ACARS] Ansluten till acars_router på {self.host}:{self.port}!")

                buffer = ""
                while self.running and session_id == self._worker_session and self._thread_id == current_thread_id:
                    try:
                        data = sock.recv(4096)
                    except (socket.timeout, TimeoutError):
                        # Tystnad på frekvensen - ligg kvar på TCP-kopplingen
                        continue

                    if not data:
                        conn_duration = time.time() - t_connect
                        if conn_duration < 0.5:
                            logger.warning(f"[ACARS] Fjärrvärd stängde anslutningen omedelbart ({self.host}:{self.port}).")
                        else:
                            logger.warning(f"[ACARS] Fjärrvärd stängde anslutningen ({self.host}:{self.port}).")
                        break

                    buffer += data.decode('utf-8', errors='replace')
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line_str = line.strip()
                        if not line_str:
                            continue

                        with self.lock:
                            self.stats['packets_received'] += 1

                        try:
                            raw_json = json.loads(line_str)
                        except json.JSONDecodeError:
                            continue

                        self._handle_frame(raw_json)

            except (socket.timeout, TimeoutError):
                if not self.running or session_id != self._worker_session or self._thread_id != current_thread_id:
                    break
                logger.warning(f"[ACARS] Timeout vid anslutning mot {self.host}:{self.port}. Nytt försök om {backoff}s.")
            except Exception as e:
                err_msg = str(e)
                if self.running and session_id == self._worker_session and self._thread_id == current_thread_id:
                    with self.lock:
                        self.stats['status'] = 'reconnecting'
                        self.stats['connected'] = False
                        self.stats['error_message'] = err_msg
                        self.stats['status_text'] = f'Frånkopplad ({err_msg}). Nytt försök om {backoff}s...'
                    logger.warning(f"[ACARS] Nätverksfel mot {self.host}:{self.port}: {err_msg}. Nytt försök om {backoff}s.")
            finally:
                with self.lock:
                    if self.sock:
                        try: self.sock.close()
                        except Exception: pass
                        self.sock = None
                if sock:
                    try: sock.close()
                    except Exception: pass

            # Exponential backoff loop (max 60 sekunder)
            for _ in range(backoff):
                if not self.running or session_id != self._worker_session or self._thread_id != current_thread_id:
                    break
                time.sleep(1.0)
            backoff = min(backoff * 2, 60)

        with self.lock:
            if self._thread_id == current_thread_id:
                self._thread_id = None

    def _handle_frame(self, raw_json):
        parsed = parse_acars_message(raw_json)
        if not parsed:
            return

        address = parsed['address']
        message = parsed['message']
        alias = parsed['alias']
        freq = parsed['frequency']
        flight = parsed.get('flight')
        reg = parsed.get('reg')
        label = parsed.get('label')

        # Kontrollera om användaren konfigurerat ett specifikt alias i PagerMonitor
        alias_info = get_alias_info(address)
        if not alias_info and flight:
            alias_info = get_alias_info(flight)
        if not alias_info and reg:
            alias_info = get_alias_info(reg)

        if alias_info and alias_info.get('alias'):
            alias = alias_info['alias']
            if alias_info.get('is_hidden'):
                return

        # Dubbletthantering
        settings = get_settings()
        try:
            dup_window = int(settings.get('duplicate_window', '120'))
        except (ValueError, TypeError):
            dup_window = 120
        dup_handling = settings.get('duplicate_handling', 'merge')

        now = time.time()
        msg_key = (address, message, label)
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
                for k in to_del:
                    del self.recent_cache[k]

        if is_duplicate and dup_handling == 'merge' and cached_entry and cached_entry.get('id'):
            cached_id = cached_entry['id']
            now_iso = datetime.now().isoformat()
            new_count = increment_message_repeat(cached_id, now_iso)
            cached_entry['time'] = now
            cached_entry['repeat_count'] = new_count
            logger.info(f"[ACARS] MERGED: Repeat count {new_count}x på ID {cached_id} ({address})")

            repeat_data = {
                'type': 'repeat_update',
                'id': cached_id,
                'repeat_count': new_count,
                'last_timestamp': now_iso,
                'frequency': freq,
                'address': address,
                'protocol': 'ACARS',
                'source_type': 'ACARS'
            }
            if self.callback:
                try: self.callback(repeat_data)
                except Exception: pass
            return

        if is_duplicate and dup_handling == 'discard':
            return

        # Kontrollera larmord (både formaterad text, råtext och metadata)
        extra_fields = [flight, reg, address, alias, parsed.get('raw_text'), parsed.get('station_id')]
        alert_match = check_alert_words(message, extra_fields=extra_fields)
        is_alert_hit = bool(alert_match)
        now_iso = datetime.now().isoformat()

        metadata = dict(parsed['metadata'])
        metadata['is_alert'] = is_alert_hit
        metadata['alert_word'] = alert_match['word'] if alert_match else None
        metadata['alert_color'] = alert_match['color'] if alert_match else None
        metadata['is_duplicate'] = is_duplicate
        metadata['repeat_count'] = 1
        metadata['last_timestamp'] = now_iso

        lat_val = parsed.get('lat')
        lon_val = parsed.get('lon')
        has_pos = (lat_val is not None and lon_val is not None)

        # Spara till databas
        msg_id, timestamp = save_message(
            address=address,
            message=message,
            alias=alias,
            function_code=1 if (is_alert_hit or has_pos) else 0,
            bitrate='VHF-ACARS',
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

        # Uppdatera statistik
        with self.lock:
            self.stats['messages_decoded'] += 1
            self.stats['last_message_time'] = timestamp
            if flight:
                self.stats['last_flight'] = flight
            if reg:
                self.stats['last_tail'] = reg
            if label:
                self.stats['last_label'] = label
            if freq:
                self.stats['last_freq'] = freq

        logger.info(f"[ACARS DECODED] -> [{address}] {alias} | {freq} | Label: {label}")

        # Skicka till MQTT
        publish_message(address, message, timestamp, alias, metadata=metadata)

        # Skicka via SSE till anslutna klienter
        msg_data = {
            'type': 'message',
            'id': msg_id,
            'timestamp': timestamp,
            'address': address,
            'message': message,
            'alias': alias,
            'frequency': freq,
            'bitrate': 'VHF-ACARS',
            'protocol': 'ACARS',
            'source_type': 'ACARS',
            'function_code': 1 if (is_alert_hit or has_pos) else 0,
            'is_alert': is_alert_hit,
            'alert_word': metadata['alert_word'],
            'alert_color': metadata['alert_color'],
            'is_duplicate': is_duplicate,
            'repeat_count': 1,
            'last_timestamp': timestamp,
            'flight': flight,
            'airline': parsed.get('airline') or metadata.get('airline'),
            'reg': reg,
            'tail': reg,
            'label': label,
            'label_desc': parsed.get('label_desc'),
            'station': parsed.get('station_id'),
            'lat': lat_val,
            'lon': lon_val,
            'decoded_fields': metadata.get('decoded_fields'),
            'metadata': metadata
        }
        if self.callback:
            try: self.callback(msg_data)
            except Exception: pass


# Global instans
acars_receiver = ACARSReceiver()

def init_acars(notify_callback=None):
    """Startar ACARS-mottagaren baserat på sparade inställningar."""
    if notify_callback:
        acars_receiver.set_callback(notify_callback)

    settings = get_settings()
    env_host = os.environ.get('ACARS_HOST')
    env_port = os.environ.get('ACARS_PORT')
    env_enabled = os.environ.get('ACARS_ENABLED')

    host = env_host or settings.get('acars_host', '192.168.1.242')
    port = env_port or settings.get('acars_port', '15550')
    enabled = env_enabled if env_enabled is not None else settings.get('acars_enabled', 'true')

    acars_receiver.start(host=host, port=port, enabled=enabled)

def restart_acars():
    """Startar om ACARS-mottagaren med de senaste inställningarna."""
    settings = get_settings()
    env_host = os.environ.get('ACARS_HOST')
    env_port = os.environ.get('ACARS_PORT')
    env_enabled = os.environ.get('ACARS_ENABLED')

    host = env_host or settings.get('acars_host', '192.168.1.242')
    port = env_port or settings.get('acars_port', '15550')
    enabled = env_enabled if env_enabled is not None else settings.get('acars_enabled', 'true')

    acars_receiver.restart(host=host, port=port, enabled=enabled)

def get_acars_status():
    """Returnerar aktuell status och statistik för VHF ACARS."""
    return acars_receiver.get_status()

def send_test_acars_message():
    """Skapar och skickar ett syntetiskt VHF ACARS-meddelande för testning."""
    sample_frame = {
        "timestamp": time.time(),
        "station_id": "ESMS",
        "channel": 0,
        "freq": 131.525,
        "level": -14.2,
        "error": 0,
        "mode": "2",
        "label": "5U",
        "block_id": "1",
        "ack": "!",
        "tail": "SE-ROA",
        "flight": "SK142",
        "msgno": "M12A",
        "text": "/ARN.TI2/026ESSA0700"
    }
    acars_receiver._handle_frame(sample_frame)
    return {"status": "success", "message": "Syntetiskt VHF ACARS-meddelande skickat (SK142 / SE-ROA)"}
