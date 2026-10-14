import socket
import json
import threading
import time
import logging
from datetime import datetime
from database import (
    save_message, get_alias_info, check_alert_words, 
    get_settings, get_connection
)

try:
    from mqtt_client import publish_message
except ImportError:
    def publish_message(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

# Kända tillverkare och modeller av radiosonder
SONDE_MODELS = {
    'RS41': 'Vaisala RS41',
    'RS41-SG': 'Vaisala RS41-SG',
    'RS41-SGP': 'Vaisala RS41-SGP',
    'RS92': 'Vaisala RS92',
    'DFM': 'GRAW DFM',
    'DFM09': 'GRAW DFM-09',
    'DFM17': 'GRAW DFM-17',
    'M10': 'Meteomodem M10',
    'M20': 'Meteomodem M20',
    'PILOT': 'Meteomodem Pilot',
    'LMS6': 'Lockheed Martin LMS-6',
    'MRZ': 'Meteo-Radiosonde MRZ'
}

def format_sonde_model(raw_model):
    if not raw_model:
        return "Radiosond"
    raw_upper = str(raw_model).strip().upper()
    for key, name in sorted(SONDE_MODELS.items(), key=lambda x: len(x[0]), reverse=True):
        if key in raw_upper:
            return name
    return str(raw_model).strip()

def format_frequency(raw_freq):
    if not raw_freq:
        return "403.500M"
    s = str(raw_freq).strip()
    # Om "403.500 MHz" -> "403.500M"
    s = s.replace("MHz", "M").replace("mhz", "M").replace(" ", "")
    if not s.endswith("M") and not s.endswith("k") and not s.endswith("K"):
        try:
            val = float(s)
            if val > 1000000:
                s = f"{val / 1e6:.3f}M"
            elif val > 1000:
                s = f"{val / 1e3:.3f}M"
            else:
                s = f"{val:.3f}M"
        except (ValueError, TypeError):
            pass
    return s

class SondeState:
    """Håller tillstånd och telemetrihistorik för en specifik väderballong under dess flygning."""
    def __init__(self, callsign, model, freq, station):
        self.callsign = callsign
        self.model = model
        self.freq = freq
        self.station = station
        self.start_time = datetime.now().isoformat()
        self.last_update_time = time.time()
        self.last_db_time = 0.0
        
        # Telemetri
        self.lat = None
        self.lon = None
        self.alt = 0.0
        self.max_alt = 0.0
        self.min_alt = 999999.0
        self.vel_v = 0.0
        self.vel_h = 0.0
        self.heading = 0.0
        self.temp = None
        self.humidity = None
        self.pressure = None
        self.batt = None
        self.snr = None
        self.frame = 0
        
        # Händelsestatus
        self.flight_state = "ASCENDING"  # ASCENDING, BURST, DESCENDING, LANDED
        self.burst_logged = False
        self.landing_logged = False
        self.db_active_row_id = None
        self.repeat_count = 1
        
        # Spår för kartritning (senaste 500 punkterna)
        self.track = []

    def update_telemetry(self, data):
        self.last_update_time = time.time()
        
        try: self.lat = float(data.get('latitude'))
        except (ValueError, TypeError): pass
        
        try: self.lon = float(data.get('longitude'))
        except (ValueError, TypeError): pass
        
        try:
            self.alt = float(data.get('altitude', 0))
            if self.alt > self.max_alt:
                self.max_alt = self.alt
            if self.alt < self.min_alt:
                self.min_alt = self.alt
        except (ValueError, TypeError):
            pass
            
        try: self.vel_v = float(data.get('vel_v', 0))
        except (ValueError, TypeError): pass
        
        try: self.vel_h = float(data.get('vel_h', 0))
        except (ValueError, TypeError): pass
        
        try: self.heading = float(data.get('heading', 0))
        except (ValueError, TypeError): pass
        
        try: self.temp = float(data.get('temp')) if data.get('temp') is not None else None
        except (ValueError, TypeError): pass
        
        try: self.humidity = float(data.get('humidity')) if data.get('humidity') is not None else None
        except (ValueError, TypeError): pass
        
        try: self.pressure = float(data.get('pressure')) if data.get('pressure') is not None else None
        except (ValueError, TypeError): pass
        
        try: self.batt = float(data.get('batt')) if data.get('batt') is not None else None
        except (ValueError, TypeError): pass
        
        try: self.snr = float(data.get('snr')) if data.get('snr') is not None else None
        except (ValueError, TypeError): pass
        
        try: self.frame = int(data.get('frame', 0))
        except (ValueError, TypeError): pass

        # Spara i spår
        if self.lat is not None and self.lon is not None:
            pt = {
                'lat': self.lat,
                'lon': self.lon,
                'alt': round(self.alt, 1),
                'vel_v': round(self.vel_v, 1),
                'temp': self.temp,
                't': data.get('time') or datetime.now().strftime("%H:%M:%S")
            }
            self.track.append(pt)
            if len(self.track) > 500:
                self.track.pop(0)

        # Kontrollera flygfas och burst/landning
        if not self.burst_logged:
            # Burst detekteras om sonden varit över 8 000 m och faller kraftigt (vel_v < -4 m/s och fallit minst 250 m från max_alt)
            if self.max_alt > 8000 and self.vel_v < -4.0 and (self.max_alt - self.alt) > 250:
                self.flight_state = "BURST"
                return "BURST"
        elif not self.landing_logged:
            # Landning detekteras om sonden faller mot marken (alt < 350 m eller hastighet < 1.0 m/s efter fall)
            if self.alt < 350 or (abs(self.vel_v) < 1.0 and self.alt < 1000):
                self.flight_state = "LANDED"
                return "LANDED"
            else:
                self.flight_state = "DESCENDING"
        return "NORMAL"

    def get_summary_text(self):
        """Genererar aktuell status för den aktiva raden."""
        status_lbl = "STIGER" if self.flight_state == "ASCENDING" else ("FALLER EFTER SPRÄNGNING" if self.flight_state in ("BURST", "DESCENDING") else "LANDAD")
        
        alt_str = f"{int(self.alt):,} m"
        max_str = f"Max: {int(self.max_alt):,} m"
        v_speed = f"{self.vel_v:+.1f} m/s"
        h_kmh = f"{self.vel_h * 3.6:.0f} km/h"
        
        parts = [
            f"[{status_lbl}] Höjd: {alt_str} ({max_str})",
            f"Stighastighet: {v_speed}",
            f"Fart: {h_kmh} ({self.heading:.0f}°)"
        ]
        
        if self.temp is not None:
            parts.append(f"Temp: {self.temp:.1f}°C")
        if self.humidity is not None:
            parts.append(f"Fukt: {self.humidity:.0f}%")
        if self.pressure is not None:
            parts.append(f"Tryck: {self.pressure:.1f} hPa")
        if self.batt is not None:
            parts.append(f"Batt: {self.batt:.1f}V")
        if self.snr is not None:
            parts.append(f"SNR: {self.snr:.1f} dB")
        if self.station:
            parts.append(f"Mottagare: {self.station}")
            
        return " | ".join(parts)


class SondeReceiver:
    """Hanterar UDP-lyssning på port 55673 och strömmar väderballonger till Pager-Monitor."""
    def __init__(self):
        self.port = 55673
        self.enabled = True
        self.db_interval = 5.0  # Sekunder mellan uppdatering av aktiv rad i SQLite
        self.thread = None
        self.running = False
        self.sock = None
        self.lock = threading.Lock()
        self.callback = None
        
        # Aktiva väderballonger mappade på anropssignal
        self.sondes = {}
        self.sondes_lock = threading.Lock()
        
        # Statistik
        self.stats = {
            'listening': False,
            'port': self.port,
            'packets_received': 0,
            'active_sondes': 0,
            'active_sondes_count': 0,
            'max_altitude_record': 0.0,
            'last_callsign': None,
            'last_model': None,
            'last_packet_time': None,
            'status_text': 'Initierar...'
        }

    def set_callback(self, cb):
        self.callback = cb

    def start(self, port=None, enabled=None, db_interval=None):
        with self.lock:
            if port is not None:
                try: self.port = int(port)
                except (ValueError, TypeError): self.port = 55673
            if enabled is not None:
                self.enabled = (str(enabled).lower() == 'true')
            if db_interval is not None:
                try: self.db_interval = max(2.0, float(db_interval))
                except (ValueError, TypeError): self.db_interval = 5.0

            self.stats['port'] = self.port

            if not self.enabled:
                self.stats['listening'] = False
                self.stats['status_text'] = 'Inaktiverad i inställningar'
                logger.info("[SONDE] Radiosondmottagare är inaktiverad.")
                return

            if self.running:
                logger.info("[SONDE] Mottagaren körs redan.")
                return

            self.running = True
            self.thread = threading.Thread(target=self._udp_listener_loop, daemon=True, name="Sonde-UDP-Listener")
            self.thread.start()
            logger.info(f"[SONDE] Startar UDP-lyssnare på port {self.port}...")

    def stop(self):
        with self.lock:
            self.running = False
            self.stats['listening'] = False
            self.stats['status_text'] = 'Stoppad'
            if self.sock:
                try: self.sock.close()
                except Exception: pass
                self.sock = None
        logger.info("[SONDE] UDP-lyssnare stoppad.")

    def restart(self, port=None, enabled=None, db_interval=None):
        logger.info("[SONDE] Startar om UDP-lyssnare...")
        self.stop()
        time.sleep(0.3)
        self.start(port=port, enabled=enabled, db_interval=db_interval)

    def get_status(self):
        with self.lock:
            with self.sondes_lock:
                self.stats['active_sondes'] = len(self.sondes)
                self.stats['active_sondes_count'] = len(self.sondes)
            return dict(self.stats)

    def get_active_sondes(self):
        """Returnerar lista med aktiva sonder och deras rutter för kartvisualisering."""
        with self.sondes_lock:
            out = []
            now = time.time()
            for cs, s in list(self.sondes.items()):
                # Rensa sonder som varit tysta i mer än 60 minuter
                if (now - s.last_update_time) > 3600:
                    del self.sondes[cs]
                    continue
                out.append({
                    'callsign': s.callsign,
                    'model': s.model,
                    'freq': s.freq,
                    'station': s.station,
                    'lat': s.lat,
                    'lon': s.lon,
                    'alt': round(s.alt, 1),
                    'max_alt': round(s.max_alt, 1),
                    'vel_v': round(s.vel_v, 1),
                    'vel_h': round(s.vel_h, 1),
                    'heading': round(s.heading, 1),
                    'temp': s.temp,
                    'humidity': s.humidity,
                    'pressure': s.pressure,
                    'batt': s.batt,
                    'snr': s.snr,
                    'flight_state': s.flight_state,
                    'last_seen': s.last_update_time,
                    'track': s.track
                })
            return out

    def _udp_listener_loop(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', self.port))
            s.settimeout(2.0)
            with self.lock:
                self.sock = s
                self.stats['listening'] = True
                self.stats['status_text'] = f"Lyssnar på UDP 0.0.0.0:{self.port}"
            logger.info(f"[SONDE] Lyssnar på inkommande telemetri på UDP 0.0.0.0:{self.port}!")
        except Exception as e:
            with self.lock:
                self.stats['listening'] = False
                self.stats['status_text'] = f"Kunde inte binda port {self.port}: {e}"
            logger.error(f"[SONDE] Fel vid bindning av UDP-port {self.port}: {e}")
            return

        while self.running:
            try:
                data, addr = s.recvfrom(8192)
                if not data:
                    continue
                line_str = data.decode('utf-8', errors='replace').strip()
                if not line_str:
                    continue
                
                try:
                    payload = json.loads(line_str)
                except json.JSONDecodeError:
                    continue
                
                self._handle_payload(payload)

            except socket.timeout:
                continue
            except Exception as e:
                if not self.running:
                    break
                logger.warning(f"[SONDE] UDP-fel: {e}")
                time.sleep(0.5)

    def _handle_payload(self, data):
        """Parsar inkommande JSON och hanterar milstolpar, databas och SSE."""
        if not isinstance(data, dict):
            return
        
        self.stats['packets_received'] += 1
        
        # radiosonde_auto_rx skickar PAYLOAD_SUMMARY
        p_type = data.get('type')
        if p_type and p_type != 'PAYLOAD_SUMMARY':
            return
            
        callsign = str(data.get('callsign') or data.get('id') or '').strip().upper()
        if not callsign:
            return
            
        model_str = format_sonde_model(data.get('model'))
        freq_str = format_frequency(data.get('freq'))
        station = str(data.get('station') or '').strip()

        now = time.time()
        is_new_sonde = False
        
        with self.sondes_lock:
            if callsign not in self.sondes:
                sonde = SondeState(callsign, model_str, freq_str, station)
                self.sondes[callsign] = sonde
                is_new_sonde = True
            else:
                sonde = self.sondes[callsign]
                
            event = sonde.update_telemetry(data)
            
            if sonde.max_alt > self.stats['max_altitude_record']:
                self.stats['max_altitude_record'] = sonde.max_alt

            self.stats['last_callsign'] = callsign
            self.stats['last_sonde_callsign'] = callsign
            self.stats['last_model'] = model_str
            self.stats['last_packet_time'] = datetime.now().isoformat()

        # Skicka sekundsnabb telemetri till SSE för silkesmjuk kartuppdatering
        if self.callback and sonde.lat is not None and sonde.lon is not None:
            telemetry_event = {
                'type': 'sonde_telemetry',
                'callsign': callsign,
                'model': model_str,
                'frequency': freq_str,
                'station': station,
                'lat': sonde.lat,
                'lon': sonde.lon,
                'alt': round(sonde.alt, 1),
                'max_alt': round(sonde.max_alt, 1),
                'vel_v': round(sonde.vel_v, 1),
                'vel_h': round(sonde.vel_h, 1),
                'heading': round(sonde.heading, 1),
                'temp': sonde.temp,
                'humidity': sonde.humidity,
                'pressure': sonde.pressure,
                'batt': sonde.batt,
                'snr': sonde.snr,
                'flight_state': sonde.flight_state
            }
            try:
                self.callback(telemetry_event)
            except Exception:
                pass

        # MILSTOLPE 1: START / FÖRSTA UPPTÄCKT
        if is_new_sonde:
            launch_msg = (
                f"[START] Ny väderballong upptäckt! Modell: {model_str} | Frekvens: {freq_str} | "
                f"Höjd: {int(sonde.alt):,} m | Stighastighet: {sonde.vel_v:+.1f} m/s | "
                f"Fart: {sonde.vel_h * 3.6:.0f} km/h ({sonde.heading:.0f}°)"
            )
            if sonde.station:
                launch_msg += f" | Mottagare: {sonde.station}"
            if sonde.lat is not None and sonde.lon is not None:
                launch_msg += f" | Lat: {sonde.lat:.4f}, Lon: {sonde.lon:.4f}"

            msg_id, ts = save_message(
                address=callsign,
                message=launch_msg,
                alias=f"{model_str} ({station})" if station else model_str,
                function_code=1,
                bitrate="SONDE-START",
                frequency=freq_str,
                is_duplicate=False,
                repeat_count=1,
                last_timestamp=None
            )
            logger.info(f"[SONDE NY] {callsign} ({model_str}) på {freq_str} från station {station}")
            
            # Initiera även den aktiva raden i databasen för kontinuerlig uppdatering
            active_summary = sonde.get_summary_text()
            if sonde.lat is not None and sonde.lon is not None:
                active_summary += f" | Lat: {sonde.lat:.4f}, Lon: {sonde.lon:.4f}"
                
            active_id, active_ts = save_message(
                address=callsign,
                message=active_summary,
                alias=f"{model_str} (Aktiv)",
                function_code=1,
                bitrate="SONDE",
                frequency=freq_str,
                is_duplicate=False,
                repeat_count=1,
                last_timestamp=None
            )
            sonde.db_active_row_id = active_id
            sonde.last_db_time = now

            # Skicka startmeddelande till larmflödet
            if self.callback:
                try:
                    self.callback({
                        'type': 'message',
                        'id': msg_id,
                        'timestamp': ts,
                        'address': callsign,
                        'message': launch_msg,
                        'alias': f"{model_str} ({station})" if station else model_str,
                        'protocol': 'SONDE',
                        'bitrate': 'SONDE-START',
                        'frequency': freq_str,
                        'repeat_count': 1,
                        'lat': sonde.lat,
                        'lon': sonde.lon
                    })
                    self.callback({
                        'type': 'message',
                        'id': active_id,
                        'timestamp': active_ts,
                        'address': callsign,
                        'message': active_summary,
                        'alias': f"{model_str} (Aktiv)",
                        'protocol': 'SONDE',
                        'bitrate': 'SONDE',
                        'frequency': freq_str,
                        'repeat_count': 1,
                        'lat': sonde.lat,
                        'lon': sonde.lon
                    })
                except Exception:
                    pass
            return

        # MILSTOLPE 2: BURST / MAXHÖJD
        if event == "BURST" and not sonde.burst_logged:
            sonde.burst_logged = True
            burst_msg = (
                f"[BURST] Ballong sprängd på maxhöjd: {int(sonde.max_alt):,} m! "
                f"Fallhastighet: {sonde.vel_v:.1f} m/s | Fart: {sonde.vel_h * 3.6:.0f} km/h"
            )
            if sonde.temp is not None:
                burst_msg += f" | Temp: {sonde.temp:.1f}°C"
            if sonde.lat is not None and sonde.lon is not None:
                burst_msg += f" | Lat: {sonde.lat:.4f}, Lon: {sonde.lon:.4f}"

            b_id, b_ts = save_message(
                address=callsign,
                message=burst_msg,
                alias=f"{model_str} (Burst)",
                function_code=3,
                bitrate="SONDE-BURST",
                frequency=freq_str,
                is_duplicate=False,
                repeat_count=1,
                last_timestamp=None
            )
            logger.info(f"[SONDE BURST] {callsign} nådde {int(sonde.max_alt):,} m!")
            if self.callback:
                try:
                    self.callback({
                        'type': 'message',
                        'id': b_id,
                        'timestamp': b_ts,
                        'address': callsign,
                        'message': burst_msg,
                        'alias': f"{model_str} (Burst)",
                        'protocol': 'SONDE',
                        'bitrate': 'SONDE-BURST',
                        'frequency': freq_str,
                        'repeat_count': 1,
                        'lat': sonde.lat,
                        'lon': sonde.lon
                    })
                except Exception:
                    pass

        # MILSTOLPE 3: LANDNING
        if event == "LANDED" and not sonde.landing_logged:
            sonde.landing_logged = True
            land_msg = (
                f"[LANDNING] Väderballong har landat på {int(sonde.alt)} m höjd! "
                f"Maxhöjd under flygning: {int(sonde.max_alt):,} m"
            )
            if sonde.batt is not None:
                land_msg += f" | Batteri: {sonde.batt:.1f}V"
            if sonde.lat is not None and sonde.lon is not None:
                land_msg += f" | Slutposition: Lat: {sonde.lat:.4f}, Lon: {sonde.lon:.4f}"

            l_id, l_ts = save_message(
                address=callsign,
                message=land_msg,
                alias=f"{model_str} (Landad)",
                function_code=2,
                bitrate="SONDE-LAND",
                frequency=freq_str,
                is_duplicate=False,
                repeat_count=1,
                last_timestamp=None
            )
            logger.info(f"[SONDE LANDNING] {callsign} landade vid Lat: {sonde.lat}, Lon: {sonde.lon}")
            if self.callback:
                try:
                    self.callback({
                        'type': 'message',
                        'id': l_id,
                        'timestamp': l_ts,
                        'address': callsign,
                        'message': land_msg,
                        'alias': f"{model_str} (Landad)",
                        'protocol': 'SONDE',
                        'bitrate': 'SONDE-LAND',
                        'frequency': freq_str,
                        'repeat_count': 1,
                        'lat': sonde.lat,
                        'lon': sonde.lon
                    })
                except Exception:
                    pass

        # UPPDATERING AV AKTIV RAD (Rate-limited till db_interval, t.ex. var 5:e sekund)
        if sonde.db_active_row_id and (now - sonde.last_db_time) >= self.db_interval:
            sonde.last_db_time = now
            sonde.repeat_count += 1
            now_iso = datetime.now().isoformat()
            
            summary = sonde.get_summary_text()
            if sonde.lat is not None and sonde.lon is not None:
                summary += f" | Lat: {sonde.lat:.4f}, Lon: {sonde.lon:.4f}"
                
            try:
                conn = get_connection()
                c = conn.cursor()
                c.execute('''
                    UPDATE messages 
                    SET message = ?, repeat_count = ?, last_timestamp = ?
                    WHERE id = ?
                ''', (summary, sonde.repeat_count, now_iso, sonde.db_active_row_id))
                conn.commit()
                conn.close()
                
                # Skicka repeat_update via SSE så raden i tabellen uppdateras direkt
                if self.callback:
                    self.callback({
                        'type': 'repeat_update',
                        'id': sonde.db_active_row_id,
                        'repeat_count': sonde.repeat_count,
                        'last_timestamp': now_iso,
                        'frequency': freq_str,
                        'address': callsign,
                        'message': summary,
                        'lat': sonde.lat,
                        'lon': sonde.lon
                    })
            except Exception as e:
                logger.error(f"[SONDE] Fel vid uppdatering av aktiv rad: {e}")

# Global singleton
sonde_receiver = SondeReceiver()

def init_sonde(notify_callback=None):
    """Startar radiosondmottagaren baserat på databasens inställningar."""
    settings = get_settings()
    enabled = settings.get('sonde_enabled', 'true')
    port = settings.get('sonde_udp_port', '55673')
    db_interval = settings.get('sonde_db_interval', '5')

    if notify_callback:
        sonde_receiver.set_callback(notify_callback)

    sonde_receiver.start(port=port, enabled=enabled, db_interval=db_interval)

def restart_sonde():
    """Startar om radiosondmottagaren vid ändrade inställningar."""
    settings = get_settings()
    sonde_receiver.restart(
        port=settings.get('sonde_udp_port', '55673'),
        enabled=settings.get('sonde_enabled', 'true'),
        db_interval=settings.get('sonde_db_interval', '5')
    )

def get_sonde_status():
    return sonde_receiver.get_status()

def get_active_sondes_api():
    return sonde_receiver.get_active_sondes()

def send_test_sonde_message():
    """Skapar ett syntetiskt PAYLOAD_SUMMARY-paket och injicerar det."""
    test_data = {
        "type": "PAYLOAD_SUMMARY",
        "station": "TROSA_SDR",
        "callsign": "V1420512",
        "model": "RS41-SG",
        "freq": "403.500 MHz",
        "latitude": 58.12451,
        "longitude": 18.21044,
        "altitude": 18450.2,
        "vel_v": 5.4,
        "vel_h": 14.2,
        "heading": 315.0,
        "temp": -54.8,
        "humidity": 12.4,
        "pressure": 71.2,
        "batt": 2.9,
        "snr": 16.5,
        "frame": 2841,
        "time": "01:42:15"
    }
    sonde_receiver._handle_payload(test_data)
    return {
        "status": "success",
        "message": "Syntetisk RS41-SG radiosond skickad (V1420512)",
        "callsign": "V1420512",
        "model": "Vaisala RS41-SG",
        "altitude": "18,450 m"
    }
