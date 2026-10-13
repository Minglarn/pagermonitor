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
    get_database_stats, auto_prune_if_enabled, clear_basestation_messages
)

try:
    from mqtt_client import init_mqtt
except ImportError:
    def init_mqtt():
        pass
from sdr_processor import start_sdr_thread, restart_sdr, on_new_message, get_sdr_runtime_status
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
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://code.jquery.com https://cdn.datatables.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.datatables.net https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
        "img-src 'self' data:; "
        "connect-src 'self';"
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

APP_VERSION = "2026.10.13.31"
logger.info(f"PagerMonitor v{APP_VERSION} (CalVer) initialized.")

@app.context_processor
def inject_globals():
    return dict(app_version=APP_VERSION)

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
    try:
        stats = get_database_stats()
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

@app.route('/api/stats/range-activity')
def stats_range_activity():
    start_date = request.args.get('start')
    end_date = request.args.get('end', start_date)
    if not start_date:
        return jsonify({"mode": "hours", "data": []})
    
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    if start_date == end_date:
        # 24-hour distribution for single day
        c.execute('''
            SELECT STRFTIME('%H', timestamp) AS label, COUNT(*) AS cnt 
            FROM messages 
            WHERE DATE(timestamp) = DATE(?)
            GROUP BY label ORDER BY label
        ''', (start_date,))
        rows = c.fetchall()
        conn.close()
        return jsonify({
            "mode": "hours",
            "data": [{"label": int(r[0]), "count": r[1]} for r in rows]
        })
    else:
        # Day-by-day distribution for date range
        c.execute('''
            SELECT DATE(timestamp) AS label, COUNT(*) AS cnt 
            FROM messages 
            WHERE DATE(timestamp) >= DATE(?) AND DATE(timestamp) <= DATE(?)
            GROUP BY label ORDER BY label
        ''', (start_date, end_date))
        rows = c.fetchall()
        conn.close()
        return jsonify({
            "mode": "days",
            "data": [{"label": r[0], "count": r[1]} for r in rows]
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
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT aw.word, COUNT(m.id) AS hits
        FROM alert_words aw
        LEFT JOIN messages m ON m.message LIKE '%'||aw.word||'%'
        WHERE aw.is_active=1
        GROUP BY aw.word
    ''')
    rows = c.fetchall()
    conn.close()
    return jsonify([{"word": r[0], "hits": r[1]} for r in rows])
@app.route('/api/stats/freq-hits')
def stats_freq_hits():
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute('SELECT frequency, COUNT(*) AS hits FROM messages GROUP BY frequency ORDER BY hits DESC')
    rows = c.fetchall()
    conn.close()
    return jsonify([{"frequency": r[0], "hits": r[1]} for r in rows])


@app.route('/api/messages')
def get_messages():
    before_id = request.args.get('before_id', type=int)
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
    
    settings = database.get_settings()
    dup_handling = settings.get('duplicate_handling', 'merge')
    include_dups = request.args.get('include_duplicates', '0').lower() in ('1', 'true')
    exclude_duplicates = (dup_handling == 'hide') and not include_dups

    messages = get_recent_messages(limit, before_id, search_query, alerts_only=alerts_only, exclude_duplicates=exclude_duplicates)
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
            'duplicate_handling', 'duplicate_window',
            'auto_prune_enabled', 'auto_prune_days', 'log_tetra_basestations',
            'tetra_scan_mode', 'tetra_dwell_time', 'tetra_skip_encrypted'
        ]
        sdr_restart_keys = {
            'frequency', 'gain', 'device_serial', 'multimon_verbosity', 
            'multimon_charset', 'multimon_format', 'sample_rate', 'resample_rate', 
            'enable_dc_removal', 'ppm_error', 'enable_deemp', 'enable_high_quality_fir',
            'atan_math', 'oversampling', 'multimon_input_type',
            'tetra_scan_mode', 'tetra_dwell_time', 'tetra_skip_encrypted'
        }
        sdr_restart_needed = False
        for key in allowed_keys:
            if key in data:
                update_setting(key, data[key])
                if key in sdr_restart_keys:
                    sdr_restart_needed = True
        
        if sdr_restart_needed:
            restart_sdr()
            
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
    try:
        alerts = get_alert_words()
    except Exception as e:
        if "no such table" in str(e).lower():
            from database import init_db
            init_db()
            alerts = get_alert_words()
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
╔═══════════════════════════════════════════════════════════════════════════╗
║ ___                                                      _                ║
║(  _`\                           /'\_/`\               _ ( )_              ║
║| |_) )  _ _    __     __   _ __ |     |   _     ___  (_)| ,_)   _    _ __ ║
║| ,__/'/'_` ) /'_ `\ /'__`\( '__)| (_) | /'_`\ /' _ `\| || |   /'_`\ ( '__)║
║| |   ( (_| |( (_) |(  ___/| |   | | | |( (_) )| ( ) || || |_ ( (_) )| |   ║
║(_)   `\__,_)`\__  |`\____)(_)   (_) (_)`\___/'(_) (_)(_)`\__)`\___/'(_)   ║
║             ( )_) |                                                       ║
║              \___/'                                                       ║
╚═══════════════════════════════════════════════════════════════════════════╝
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
