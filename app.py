import logging
import os
import hmac
import threading
from flask import Flask, jsonify, render_template, request, Response, stream_with_context
import json
import time
from queue import Queue, Empty

import sqlite3
import database
from database import (
    init_db, get_recent_messages, get_settings, 
    update_setting, get_aliases, save_alias, 
    delete_alias, get_alert_words, save_alert_word, 
    delete_alert_word, get_default_settings,
    get_sdr_instances, save_sdr_instance, delete_sdr_instance, toggle_sdr_instance,
    clone_sdr_instance,
    delete_message, toggle_message_lock, clear_messages, prune_messages,
    get_database_stats, auto_prune_if_enabled, clear_basestation_messages,
    save_message, delete_duplicates
)

try:
    from mqtt_client import init_mqtt
except ImportError:
    def init_mqtt():
        pass
from sdr_processor import start_sdr_thread, restart_sdr, on_new_message, get_sdr_runtime_status
from vdl2_receiver import init_vdl2, restart_vdl2, get_vdl2_status, send_test_vdl2_message
from sonde_receiver import init_sonde, restart_sonde, get_sonde_status, get_active_sondes_api, send_test_sonde_message
from satc_receiver import init_satc, restart_satc, get_satc_status, send_test_satc_message
from aero_receiver import init_aero, restart_aero, get_aero_status, send_test_aero_message
from hfdl_receiver import init_hfdl, restart_hfdl, get_hfdl_status, send_test_hfdl_message
from acars_receiver import init_acars, restart_acars, get_acars_status, send_test_acars_message
from log_streamer import setup_log_capture, log_manager

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize in-memory log capture and stdout/stderr stream tee for UI console
setup_log_capture()

# Disable werkzeug HTTP request logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
# Limit maximum payload size for incoming HTTP requests to prevent DoS memory exhaustion
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB

APP_VERSION = "2026.10.19.5"

@app.context_processor
def inject_version():
    return {'app_version': APP_VERSION}

# Authentication via environment variables (configured in docker-compose.yml or .env)
AUTH_USER = os.environ.get('AUTH_USER', '').strip()
AUTH_PASS = os.environ.get('AUTH_PASS', '').strip()

if AUTH_PASS:
    logger.info("HTTP Basic Auth is enabled for user: %s", AUTH_USER or 'admin')
else:
    logger.info("HTTP Basic Auth is disabled (no AUTH_PASS provided).")

@app.before_request
def require_authentication():
    # If no password is set, allow all traffic (open mode)
    if not AUTH_PASS:
        return None
        
    auth = request.authorization
    expected_user = AUTH_USER if AUTH_USER else 'admin'
    
    if not auth:
        return Response(
            'Authentication Required', 401,
            {'WWW-Authenticate': 'Basic realm="PagerMonitor"'}
        )
        
    user_ok = hmac.compare_digest((auth.username or '').encode('utf-8'), expected_user.encode('utf-8'))
    pass_ok = hmac.compare_digest((auth.password or '').encode('utf-8'), AUTH_PASS.encode('utf-8'))
    if not (user_ok and pass_ok):
        logger.warning(f"Failed login attempt from {request.remote_addr} with username: {auth.username}")
        return Response(
            'Invalid username or password', 401,
            {'WWW-Authenticate': 'Basic realm="PagerMonitor"'}
        )

@app.after_request
def set_security_headers(response):
    # Harden HTTP responses against common web vulnerabilities
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://code.jquery.com https://cdn.datatables.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.datatables.net https://cdn.jsdelivr.net https://unpkg.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
        "img-src 'self' data: https://*.tile.openstreetmap.org https://tiles.openseamap.org https://unpkg.com; "
        "connect-src 'self' ws: wss: https://*.tile.openstreetmap.org https://tiles.openseamap.org https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com;"
    )
    return response

def start_prune_scheduler():
    """Background thread to automatically prune old messages on schedule."""
    def prune_loop():
        # Initial sleep before first check
        time.sleep(15)
        while True:
            try:
                pruned = auto_prune_if_enabled()
                if pruned > 0:
                    logger.info(f"Automatic database maintenance: pruned {pruned} old messages.")
            except Exception as e:
                logger.error(f"Error in automatic prune scheduler: {e}")
            # Check every 6 hours
            time.sleep(6 * 3600)
            
    t = threading.Thread(target=prune_loop, daemon=True)
    t.start()

# Start the background maintenance scheduler
start_prune_scheduler()

APP_VERSION = "2026.10.19.5"
logger.info(f"PagerMonitor v{APP_VERSION} (CalVer) initialized.")

app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.context_processor
def inject_globals():
    return dict(app_version=APP_VERSION)

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/alarms')
@app.route('/larm')
def larm_page():
    return render_template('larm.html')

@app.route('/statistics')
def statistics_page():
    return render_template('statistics.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

@app.route('/rules')
@app.route('/aliases')
@app.route('/alerts')
def rules_page():
    return render_template('rules.html')

@app.route('/api/database/stats')
def database_stats():
    """Retrieve detailed database statistics including size, message counts, and oldest/newest timestamps."""
    force = request.args.get('force', '0').lower() in ('1', 'true')
    try:
        stats = get_database_stats(force=force)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Failed to fetch database stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
@app.route('/api/stats/dates')
def stats_dates():
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute('SELECT DISTINCT DATE(timestamp) AS day FROM messages ORDER BY day DESC')
    rows = c.fetchall()
    conn.close()
    return jsonify([row[0] for row in rows])

@app.route('/api/stats/day/<date>')
def stats_day(date):
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM messages WHERE DATE(timestamp)=? ORDER BY timestamp DESC', (date,))
    rows = c.fetchall()
    col_names = [desc[0] for desc in c.description]
    conn.close()
    msgs = [dict(zip(col_names, row)) for row in rows]
    return jsonify(msgs)

@app.route('/api/stats/range')
def stats_range():
    start_date = request.args.get('start')
    end_date = request.args.get('end', start_date)
    if not start_date:
        return jsonify([])
    
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT * FROM messages 
        WHERE DATE(timestamp) >= DATE(?) AND DATE(timestamp) <= DATE(?)
        ORDER BY timestamp DESC
    ''', (start_date, end_date))
    rows = c.fetchall()
    col_names = [desc[0] for desc in c.description]
    conn.close()
    msgs = [dict(zip(col_names, row)) for row in rows]
    return jsonify(msgs)

PROTO_CASE_SQL = '''
    CASE 
        WHEN bitrate LIKE '%VDL%' THEN 'VDL2'
        WHEN (bitrate LIKE '%AERO%' OR bitrate LIKE '%AERO-ACARS%') THEN 'AERO'
        WHEN (bitrate LIKE '%ACARS%' AND bitrate NOT LIKE '%VDL%' AND bitrate NOT LIKE '%AERO%') THEN 'ACARS'
        WHEN (bitrate LIKE '%SATC%' OR bitrate LIKE '%INMARSAT%' OR address LIKE 'LES:%') THEN 'SATC'
        WHEN bitrate LIKE '%HFDL%' THEN 'HFDL'
        WHEN bitrate LIKE '%SONDE%' THEN 'SONDE'
        WHEN bitrate LIKE '%TETRA%' THEN 'TETRA'
        WHEN (bitrate LIKE '%RDS%' OR bitrate LIKE '%TMC%') THEN 'RDS'
        ELSE 'POCSAG'
    END
'''

@app.route('/api/stats/range-activity')
def stats_range_activity():
    start_date = request.args.get('start')
    end_date = request.args.get('end', start_date)
    if not start_date:
        return jsonify({"mode": "hours", "data": [], "by_protocol": {}, "by_frequency": {}})
    
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    if start_date == end_date:
        # 24-timmars distribution för enskild dag
        c.execute('''
            SELECT STRFTIME('%H', timestamp) AS label, COUNT(*) AS cnt 
            FROM messages 
            WHERE DATE(timestamp) = DATE(?)
            GROUP BY label ORDER BY label
        ''', (start_date,))
        rows = c.fetchall()
        total_data = [{"label": int(r[0]), "count": r[1]} for r in rows]

        # Per protokoll
        c.execute(f'''
            SELECT STRFTIME('%H', timestamp) AS hr, {PROTO_CASE_SQL} AS proto, COUNT(*) AS cnt
            FROM messages
            WHERE DATE(timestamp) = DATE(?)
            GROUP BY hr, proto ORDER BY hr
        ''', (start_date,))
        by_proto = {}
        for hr_str, proto, cnt in c.fetchall():
            hr = int(hr_str)
            if proto not in by_proto:
                by_proto[proto] = [0] * 24
            by_proto[proto][hr] = cnt

        # Per frekvens
        c.execute('''
            SELECT STRFTIME('%H', timestamp) AS hr, frequency, COUNT(*) AS cnt
            FROM messages
            WHERE DATE(timestamp) = DATE(?) AND frequency IS NOT NULL AND frequency != ''
            GROUP BY hr, frequency ORDER BY hr
        ''', (start_date,))
        by_freq = {}
        for hr_str, freq, cnt in c.fetchall():
            hr = int(hr_str)
            if freq not in by_freq:
                by_freq[freq] = [0] * 24
            by_freq[freq][hr] = cnt

        conn.close()
        return jsonify({
            "mode": "hours",
            "data": total_data,
            "by_protocol": by_proto,
            "by_frequency": by_freq
        })
    else:
        # Dag-för-dag distribution för datumintervall
        c.execute('''
            SELECT DATE(timestamp) AS label, COUNT(*) AS cnt 
            FROM messages 
            WHERE DATE(timestamp) >= DATE(?) AND DATE(timestamp) <= DATE(?)
            GROUP BY label ORDER BY label
        ''', (start_date, end_date))
        rows = c.fetchall()
        total_data = [{"label": r[0], "count": r[1]} for r in rows]
        day_labels = [r[0] for r in rows]

        # Per protokoll
        c.execute(f'''
            SELECT DATE(timestamp) AS dt, {PROTO_CASE_SQL} AS proto, COUNT(*) AS cnt
            FROM messages
            WHERE DATE(timestamp) >= DATE(?) AND DATE(timestamp) <= DATE(?)
            GROUP BY dt, proto ORDER BY dt
        ''', (start_date, end_date))
        by_proto = {}
        for dt, proto, cnt in c.fetchall():
            if proto not in by_proto:
                by_proto[proto] = {d: 0 for d in day_labels}
            by_proto[proto][dt] = cnt
        by_proto_lists = {p: [by_proto[p].get(d, 0) for d in day_labels] for p in by_proto}

        # Per frekvens
        c.execute('''
            SELECT DATE(timestamp) AS dt, frequency, COUNT(*) AS cnt
            FROM messages
            WHERE DATE(timestamp) >= DATE(?) AND DATE(timestamp) <= DATE(?) AND frequency IS NOT NULL AND frequency != ''
            GROUP BY dt, frequency ORDER BY dt
        ''', (start_date, end_date))
        by_freq = {}
        for dt, freq, cnt in c.fetchall():
            if freq not in by_freq:
                by_freq[freq] = {d: 0 for d in day_labels}
            by_freq[freq][dt] = cnt
        by_freq_lists = {f: [by_freq[f].get(d, 0) for d in day_labels] for f in by_freq}

        conn.close()
        return jsonify({
            "mode": "days",
            "data": total_data,
            "by_protocol": by_proto_lists,
            "by_frequency": by_freq_lists
        })


@app.route('/api/stats/count-per-day')
def stats_count_per_day():
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute('SELECT DATE(timestamp) AS day, COUNT(*) AS cnt FROM messages GROUP BY day ORDER BY day')
    rows = c.fetchall()
    conn.close()
    return jsonify([{"day": r[0], "count": r[1]} for r in rows])

@app.route('/api/stats/count-per-hour/<date>')
def stats_count_per_hour(date):
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT STRFTIME('%H', timestamp) AS hour, COUNT(*) AS cnt FROM messages WHERE DATE(timestamp)=? GROUP BY hour ORDER BY hour", (date,))
    rows = c.fetchall()
    conn.close()
    return jsonify([{"hour": int(r[0]), "count": r[1]} for r in rows])

@app.route('/api/stats/alert-hits')
def stats_alert_hits():
    start_date = request.args.get('start')
    end_date = request.args.get('end', start_date)
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    if start_date and end_date:
        c.execute('''
            SELECT aw.word, COUNT(m.id) AS hits
            FROM alert_words aw
            LEFT JOIN messages m ON (m.message LIKE '%'||aw.word||'%' AND DATE(m.timestamp) >= DATE(?) AND DATE(m.timestamp) <= DATE(?))
            WHERE aw.is_active=1
            GROUP BY aw.word
            ORDER BY hits DESC
        ''', (start_date, end_date))
    else:
        c.execute('''
            SELECT aw.word, COUNT(m.id) AS hits
            FROM alert_words aw
            LEFT JOIN messages m ON m.message LIKE '%'||aw.word||'%'
            WHERE aw.is_active=1
            GROUP BY aw.word
            ORDER BY hits DESC
        ''')
    rows = c.fetchall()
    conn.close()
    return jsonify([{"word": r[0], "hits": r[1]} for r in rows])

@app.route('/api/stats/freq-hits')
def stats_freq_hits():
    start_date = request.args.get('start')
    end_date = request.args.get('end', start_date)
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    if start_date and end_date:
        c.execute('''
            SELECT frequency, COUNT(*) AS hits 
            FROM messages 
            WHERE DATE(timestamp) >= DATE(?) AND DATE(timestamp) <= DATE(?) AND frequency IS NOT NULL AND frequency != ''
            GROUP BY frequency 
            ORDER BY hits DESC
        ''', (start_date, end_date))
    else:
        c.execute('''
            SELECT frequency, COUNT(*) AS hits 
            FROM messages 
            WHERE frequency IS NOT NULL AND frequency != ''
            GROUP BY frequency 
            ORDER BY hits DESC
        ''')
    rows = c.fetchall()
    conn.close()
    return jsonify([{"frequency": r[0], "hits": r[1]} for r in rows])


@app.route('/api/messages')
def get_messages():
    before_id = request.args.get('before_id', type=int)
    since_id = request.args.get('since_id', type=int)
    limit_raw = request.args.get('limit', default='500')
    if str(limit_raw).lower() in ('all', 'none', '0'):
        limit = None
    else:
        try:
            limit = int(limit_raw)
        except (ValueError, TypeError):
            limit = 500
    search_query = request.args.get('search', default=None, type=str)
    alerts_only = request.args.get('alerts_only', default='0').lower() in ('1', 'true')
    protocol = request.args.get('protocol', default=None, type=str)
    ensure_protocols = request.args.get('ensure_protocols', default='1').lower() in ('1', 'true')
    
    settings = database.get_settings()
    dup_handling = settings.get('duplicate_handling', 'merge')
    include_dups = request.args.get('include_duplicates', '0').lower() in ('1', 'true')
    exclude_duplicates = (dup_handling == 'hide') and not include_dups

    should_balance = (ensure_protocols and not protocol and not before_id and not since_id and not search_query and not alerts_only)
    messages = get_recent_messages(limit, before_id, since_id=since_id, search=search_query, alerts_only=alerts_only, exclude_duplicates=exclude_duplicates, protocol=protocol, ensure_active_protocols=should_balance)
    return jsonify(messages)

@app.route('/api/messages/clear', methods=['POST'])
def clear_all_messages():
    clear_messages()
    return jsonify({"status": "success", "message": "All messages cleared"})

@app.route('/api/messages/prune', methods=['POST'])
def prune_old_messages():
    data = request.json or {}
    days = data.get('days', 30)
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 30
    deleted = prune_messages(days)
    return jsonify({
        "status": "success", 
        "message": f"Successfully pruned {deleted} messages older than {days} days.",
        "deleted_count": deleted
    })

@app.route('/api/messages/delete-duplicates', methods=['POST'])
def api_delete_duplicates():
    """Delete all duplicate messages immediately."""
    try:
        deleted = delete_duplicates()
        return jsonify({
            "status": "success",
            "message": f"Tog bort {deleted} dubblettmeddelanden ur databasen.",
            "deleted_count": deleted
        })
    except Exception as e:
        logger.error(f"Failed to delete duplicates: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/messages/basestations', methods=['DELETE', 'POST'])
def handle_clear_basestations():
    try:
        deleted_count = clear_basestation_messages()
        return jsonify({
            "status": "success", 
            "message": f"Tog bort {deleted_count} basstationsloggar ur databasen.",
            "deleted_count": deleted_count
        })
    except Exception as e:
        logger.error(f"Error clearing basestation messages: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/test/tmc', methods=['POST'])
def handle_test_tmc():
    """Genererar ett syntetiskt ALERT-C trafikmeddelande och skickar till SSE och databas."""
    try:
        from sdr_processor import new_message_callbacks
        address = "E4:14502"
        alias = "Trafikplats Nyköping Norra (Avfart 134)"
        msg = "Trafikolycka (Stationary traffic for 2 km) (Trafikplats Nyköping Norra (Avfart 134)) | Lat: 58.7612, Lon: 17.0211"
        freq = "88.7M"
        bitrate = "RDS-TMC"
        function_code = 3

        saved_id, saved_ts = save_message(address, msg, alias, function_code, bitrate, freq)
        payload = {
            'id': saved_id,
            'timestamp': saved_ts,
            'address': address,
            'message': msg,
            'alias': alias,
            'function_code': function_code,
            'protocol': 'RDS-TMC',
            'bitrate': bitrate,
            'frequency': freq,
            'repeat_count': 1,
            'is_duplicate': False
        }
        for cb in list(new_message_callbacks):
            try: cb(payload)
            except Exception: pass

        logger.info(f"[RDS-TMC TEST] Syntetiskt testlarm skickat till realtidsflödet: {msg}")
        return jsonify({"status": "success", "message": "Syntetiskt testlarm skickat", "data": payload})
    except Exception as e:
        logger.error(f"Error generating test TMC message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/vdl2/status')
def vdl2_status():
    """Returnerar aktuell anslutningsstatus och telemetri för VDL2."""
    return jsonify(get_vdl2_status())

@app.route('/api/vdl2/test', methods=['POST'])
def vdl2_test():
    """Skickar ett syntetiskt VDL2/ACARS-meddelande till databas och realtidsflöde."""
    try:
        res = send_test_vdl2_message()
        return jsonify(res)
    except Exception as e:
        logger.error(f"Error sending test VDL2 message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sonde/status')
def sonde_status():
    """Returnerar aktuell lyssnarstatus och telemetri för radiosondmottagaren."""
    return jsonify(get_sonde_status())

@app.route('/api/sonde/active')
def sonde_active():
    """Returnerar alla aktiva väderballonger med telemetri och flygspår."""
    return jsonify(get_active_sondes_api())

@app.route('/api/sonde/test', methods=['POST'])
def sonde_test():
    """Skickar en syntetisk väderballong (RS41-SG) till databas och realtidsflöde."""
    try:
        res = send_test_sonde_message()
        return jsonify(res)
    except Exception as e:
        logger.error(f"Error sending test Sonde message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/satc/status')
def satc_status():
    """Returnerar aktuell lyssnarstatus för Inmarsat STD-C / EGC-mottagaren."""
    return jsonify(get_satc_status())

@app.route('/api/satc/test', methods=['POST'])
def satc_test():
    """Skickar ett syntetiskt Inmarsat EGC-testmeddelande till databas och realtidsflöde."""
    try:
        data = request.get_json(silent=True) or {}
        is_distress = bool(data.get('distress', False))
        res = send_test_satc_message(is_distress=is_distress)
        return jsonify(res)
    except Exception as e:
        logger.error(f"Error sending test SATC message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/aero/status')
def aero_status():
    """Returnerar aktuell lyssnarstatus för Inmarsat AERO-mottagaren."""
    return jsonify(get_aero_status())

@app.route('/api/aero/test', methods=['POST'])
def aero_test():
    """Skickar ett syntetiskt Inmarsat AERO ACARS-testmeddelande till databas och realtidsflöde."""
    try:
        data = request.get_json(silent=True) or {}
        is_pos = bool(data.get('pos', False))
        res = send_test_aero_message(is_pos_report=is_pos)
        return jsonify(res)
    except Exception as e:
        logger.error(f"Error sending test AERO message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/hfdl/status')
def hfdl_status():
    """Returnerar aktuell lyssnarstatus och telemetri för HFDL-mottagaren."""
    return jsonify(get_hfdl_status())

@app.route('/api/hfdl/test', methods=['POST'])
def hfdl_test():
    """Skickar ett syntetiskt HFDL-testmeddelande till databas och realtidsflöde."""
    try:
        data = request.get_json(silent=True) or {}
        pkt_type = data.get('type', 'frequency_data')
        res = send_test_hfdl_message(pkt_type=pkt_type)
        return jsonify(res)
    except Exception as e:
        logger.error(f"Error sending test HFDL message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/acars/status')
def acars_status():
    """Returnerar aktuell anslutningsstatus och telemetri för VHF ACARS."""
    return jsonify(get_acars_status())

@app.route('/api/acars/test', methods=['POST'])
def acars_test():
    """Skickar ett syntetiskt VHF ACARS-meddelande till databas och realtidsflöde."""
    try:
        res = send_test_acars_message()
        return jsonify(res)
    except Exception as e:
        logger.error(f"Error sending test ACARS message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/settings/defaults')
def settings_defaults():
    return jsonify(get_default_settings())

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.json
        # Handle each setting explicitly to prevent injected keys
        allowed_keys = [
            'frequency', 'gain', 'device_serial', 'multimon_verbosity', 
            'multimon_charset', 'multimon_format', 'message_font', 
            'message_font_size', 'sample_rate', 'resample_rate', 
            'enable_dc_removal', 'ppm_error', 'enable_deemp', 
            'enable_high_quality_fir', 'atan_math', 'oversampling',
            'multimon_input_type', 'garbage_filter', 'garbage_filter_sensitivity',
            'duplicate_handling', 'duplicate_window', 'save_duplicates',
            'auto_prune_enabled', 'auto_prune_days', 'log_tetra_basestations',
            'tetra_scan_mode', 'tetra_dwell_time', 'tetra_skip_encrypted',
            'vdl2_enabled', 'vdl2_host', 'vdl2_port', 'vdl2_filter_empty', 'vdl2_filter_links',
            'sonde_enabled', 'sonde_udp_port', 'sonde_db_interval',
            'satc_enabled', 'satc_host', 'satc_port', 'satc_only_messages',
            'aero_enabled', 'aero_host', 'aero_port', 'aero_only_messages',
            'hfdl_enabled', 'hfdl_host', 'hfdl_port', 'hfdl_only_messages',
            'acars_enabled', 'acars_host', 'acars_port'
        ]
        sdr_restart_keys = {
            'frequency', 'gain', 'device_serial', 'multimon_verbosity', 
            'multimon_charset', 'multimon_format', 'sample_rate', 'resample_rate', 
            'enable_dc_removal', 'ppm_error', 'enable_deemp', 'enable_high_quality_fir',
            'atan_math', 'oversampling', 'multimon_input_type',
            'tetra_scan_mode', 'tetra_dwell_time', 'tetra_skip_encrypted'
        }
        vdl2_keys = {'vdl2_enabled', 'vdl2_host', 'vdl2_port', 'vdl2_filter_empty', 'vdl2_filter_links'}
        sonde_keys = {'sonde_enabled', 'sonde_udp_port', 'sonde_db_interval'}
        satc_keys = {'satc_enabled', 'satc_host', 'satc_port', 'satc_only_messages'}
        aero_keys = {'aero_enabled', 'aero_host', 'aero_port', 'aero_only_messages'}
        hfdl_keys = {'hfdl_enabled', 'hfdl_host', 'hfdl_port', 'hfdl_only_messages'}
        acars_keys = {'acars_enabled', 'acars_host', 'acars_port'}
        sdr_restart_needed = False
        vdl2_restart_needed = False
        sonde_restart_needed = False
        satc_restart_needed = False
        aero_restart_needed = False
        hfdl_restart_needed = False
        acars_restart_needed = False
        for key in allowed_keys:
            if key in data:
                update_setting(key, data[key])
                if key in sdr_restart_keys:
                    sdr_restart_needed = True
                if key in vdl2_keys:
                    vdl2_restart_needed = True
                if key in sonde_keys:
                    sonde_restart_needed = True
                if key in satc_keys:
                    satc_restart_needed = True
                if key in aero_keys:
                    aero_restart_needed = True
                if key in hfdl_keys:
                    hfdl_restart_needed = True
                if key in acars_keys:
                    acars_restart_needed = True
        
        if sdr_restart_needed:
            restart_sdr()
        if vdl2_restart_needed:
            restart_vdl2()
        if sonde_restart_needed:
            restart_sonde()
        if satc_restart_needed:
            restart_satc()
        if aero_restart_needed:
            restart_aero()
        if hfdl_restart_needed:
            restart_hfdl()
        if acars_restart_needed:
            restart_acars()
            
        return jsonify({"status": "success"})
    
    # GET request
    settings = get_settings()
    # Filter out rtl_tcp if it still exists in older db
    settings.pop('rtl_tcp_address', None)
    return jsonify(settings)

@app.route('/settings/sdr/<int:sdr_id>')
def sdr_settings_page(sdr_id):
    return render_template('sdr_settings.html', sdr_id=sdr_id)

@app.route('/api/sdr', methods=['GET', 'POST'])
def handle_sdr_instances():
    if request.method == 'POST':
        data = request.json
        save_sdr_instance(data)
        restart_sdr()
        return jsonify({"status": "success"})
    
    # GET request
    instances = get_sdr_instances()
    runtime_status = get_sdr_runtime_status()
    for inst in instances:
        rt = runtime_status.get(inst['id'], {})
        inst['is_running'] = rt.get('is_running', False)
        inst['rtl_fm_pid'] = rt.get('rtl_fm_pid')
        inst['multimon_pid'] = rt.get('multimon_pid')
        inst['last_error'] = rt.get('last_error')
    return jsonify(instances)

@app.route('/api/sdr/<int:instance_id>', methods=['GET'])
def get_single_sdr(instance_id):
    instances = get_sdr_instances()
    instance = next((i for i in instances if i['id'] == instance_id), None)
    if not instance:
        return jsonify({"status": "error", "message": "Instance not found"}), 404
    rt = get_sdr_runtime_status().get(instance_id, {})
    instance['is_running'] = rt.get('is_running', False)
    instance['rtl_fm_pid'] = rt.get('rtl_fm_pid')
    instance['multimon_pid'] = rt.get('multimon_pid')
    instance['last_error'] = rt.get('last_error')
    return jsonify(instance)

@app.route('/api/sdr/<int:instance_id>', methods=['DELETE'])
def delete_sdr(instance_id):
    delete_sdr_instance(instance_id)
    restart_sdr()
    return jsonify({"status": "success"})

@app.route('/api/sdr/<int:instance_id>/toggle', methods=['POST'])
def toggle_sdr(instance_id):
    data = request.json
    enabled = data.get('enabled', True)
    toggle_sdr_instance(instance_id, enabled)
    restart_sdr()
    return jsonify({"status": "success"})

@app.route('/api/sdr/<int:instance_id>/clone', methods=['POST'])
def clone_sdr(instance_id):
    data = request.get_json(silent=True) or {}
    new_name = data.get('name')
    new_frequency = data.get('frequency')
    new_id = clone_sdr_instance(instance_id, new_name, new_frequency, enabled=0)
    if new_id is None:
        return jsonify({"status": "error", "message": "Receiver not found"}), 404
    restart_sdr()
    return jsonify({"status": "success", "id": new_id})

@app.route('/api/aliases', methods=['GET', 'POST', 'DELETE'])
def handle_aliases():
    if request.method == 'POST':
        data = request.json
        address = data.get('address')
        alias = data.get('alias')
        is_hidden = data.get('is_hidden', False)
        
        if not address or not alias:
            return jsonify({"status": "error", "message": "Missing address or alias"}), 400
            
        save_alias(address, alias, is_hidden)
        return jsonify({"status": "success"})
        
    elif request.method == 'DELETE':
        data = request.json
        address = data.get('address')
        if not address:
             return jsonify({"status": "error", "message": "Missing address"}), 400
        delete_alias(address)
        logger.info(f"Alias for address {address} deleted.")
        return jsonify({"status": "success"})
        
    # GET request
    aliases = get_aliases()
    return jsonify(aliases)

@app.route('/api/alerts', methods=['GET', 'POST', 'DELETE'])
def handle_alerts():
    if request.method == 'POST':
        data = request.json
        word = data.get('word')
        color = data.get('color', '#f85149')
        is_active = data.get('is_active', True)
        
        if not word:
            return jsonify({"status": "error", "message": "Missing word"}), 400
            
        try:
            save_alert_word(word, color, is_active)
        except Exception as e:
            if "no such table" in str(e).lower():
                init_db()
                save_alert_word(word, color, is_active)
            else:
                return jsonify({"status": "error", "message": str(e)}), 500

        return jsonify({"status": "success"})
        
    elif request.method == 'DELETE':
        data = request.json
        word_id = data.get('id')
        if not word_id:
             return jsonify({"status": "error", "message": "Missing alert ID"}), 400
        delete_alert_word(word_id)
        logger.info(f"Alert word (id={word_id}) deleted.")
        return jsonify({"status": "success"})
        
    # GET request
    include_stats = request.args.get('stats') == '1' or request.args.get('include_stats') == '1'
    try:
        alerts = get_alert_words(include_stats=include_stats)
    except Exception as e:
        if "no such table" in str(e).lower():
            from database import init_db
            init_db()
            alerts = get_alert_words(include_stats=include_stats)
        else:
            return jsonify({"status": "error", "message": str(e)}), 500
            
    return jsonify(alerts)
    
@app.route('/api/messages/<int:msg_id>', methods=['DELETE'])
def delete_single_message(msg_id):
    try:
        delete_message(msg_id)
        logger.info(f"Message {msg_id} deleted.")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to delete message {msg_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/messages/<int:msg_id>/lock', methods=['POST'])
def lock_single_message(msg_id):
    try:
        data = request.json
        protected = data.get('protected', True)
        toggle_message_lock(msg_id, protected)
        logger.info(f"Message {msg_id} protection set to {protected}.")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to toggle lock for message {msg_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# SSE Setup
client_queues = []

def notify_clients(message_data):
    for q in list(client_queues):
        try:
            q.put(message_data)
        except Exception:
            client_queues.remove(q)

on_new_message(notify_clients)
init_vdl2(notify_clients)
init_sonde(notify_clients)
init_satc(notify_clients)
init_aero(notify_clients)
init_hfdl(notify_clients)
init_acars(notify_clients)

@app.route('/stream')
def stream():
    @stream_with_context
    def event_stream():
        q = Queue()
        client_queues.append(q)
        try:
            # Send an initial comment to flush buffers
            yield ": connected\n\n"
            while True:
                try:
                    # Use a timeout to send periodic pings to keep the connection alive
                    # and force proxies to flush their buffers.
                    msg = q.get(timeout=20)
                    yield f"data: {json.dumps(msg)}\n\n"
                except Empty:
                    # Heartbeat ping
                    yield ": ping\n\n"
        except GeneratorExit:
            client_queues.remove(q)
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            if q in client_queues:
                client_queues.remove(q)
            
    response = Response(event_stream(), content_type='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response

# Log Console Endpoints
@app.route('/api/logs/history')
def get_log_history():
    limit = request.args.get('limit', default=500, type=int)
    level = request.args.get('level', default=None, type=str)
    search = request.args.get('search', default=None, type=str)
    logs = log_manager.get_history(limit=limit, min_level=level, search=search)
    return jsonify({'status': 'success', 'logs': logs, 'total': len(logs)})

@app.route('/api/logs/clear', methods=['POST'])
def clear_log_history():
    log_manager.clear()
    return jsonify({'status': 'success', 'message': 'Logghistorik rensad'})

@app.route('/api/logs/stream')
def stream_logs():
    @stream_with_context
    def event_stream():
        q = log_manager.subscribe()
        try:
            yield ": connected\n\n"
            while True:
                try:
                    entry = q.get(timeout=20)
                    yield f"data: {json.dumps(entry)}\n\n"
                except Empty:
                    yield ": ping\n\n"
        except GeneratorExit:
            log_manager.unsubscribe(q)
        except Exception as e:
            logger.error(f"SSE log stream error: {e}")
            log_manager.unsubscribe(q)

    response = Response(event_stream(), content_type='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response

if __name__ == '__main__':
    print(r"""
+---------------------------------------------------------------------------+
| ___                                                      _                |
|(  _`\                           /'\_/`\               _ ( )_              |
|| |_) )  _ _    __     __   _ __ |     |   _     ___  (_)| ,_)   _    _ __ |
|| ,__/'/'_` ) /'_ `\ /'__`\( '__)| (_) | /'_`\ /' _ `\| || |   /'_`\ ( '__)|
|| |   ( (_| |( (_) |(  ___/| |   | | | |( (_) )| ( ) || || |_ ( (_) )| |   |
|(_)   `\__,_)`\__  |`\____)(_)   (_) (_)`\___/'(_) (_)(_)`\__)`\___/'(_)   |
|             ( )_) |                                                       |
|              \___/'                                                       |
+---------------------------------------------------------------------------+
""")
    logger.info("=================================================================")
    logger.info(f" PagerMonitor v{APP_VERSION} (CalVer) - Starting container service...")
    logger.info("=================================================================")
    
    # Initialize components
    init_db()
    init_mqtt()
    
    # Start the SDR processing background thread
    start_sdr_thread()
    
    # Run the Flask web application
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
