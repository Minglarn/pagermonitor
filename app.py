import logging
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
    get_sdr_instances, save_sdr_instance, delete_sdr_instance, toggle_sdr_instance
)

try:
    from mqtt_client import init_mqtt
except ImportError:
    def init_mqtt():
        pass
from sdr_processor import start_sdr_thread, restart_sdr, on_new_message

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable werkzeug HTTP request logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/statistics')
def statistics_page():
    return render_template('statistics.html')
@app.route('/settings')
def settings_page():
    return render_template('settings.html')
@app.route('/aliases')
def aliases_page():
    return render_template('aliases.html')
@app.route('/alerts')
def alerts_page():
    return render_template('alerts.html')
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
    c.execute('SELECT * FROM messages WHERE DATE(timestamp)=? ORDER BY timestamp', (date,))
    rows = c.fetchall()
    col_names = [desc[0] for desc in c.description]
    conn.close()
    msgs = [dict(zip(col_names, row)) for row in rows]
    return jsonify(msgs)

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
    messages = get_recent_messages(100)
    return jsonify(messages)

@app.route('/api/settings/defaults')
def settings_defaults():
    return jsonify(get_default_settings())

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.json
        # Handle each setting explicitly to prevent injected keys
        allowed_keys = ['frequency', 'gain', 'device_serial', 'multimon_verbosity', 'multimon_charset', 'multimon_format', 'message_font', 'message_font_size', 'sample_rate', 'resample_rate', 'enable_dc_removal', 'ppm_error', 'enable_deemp', 'multimon_input_type']
        changed = False
        for key in allowed_keys:
            if key in data:
                update_setting(key, data[key])
                changed = True
        
        if changed:
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
    return jsonify(instances)

@app.route('/api/sdr/<int:instance_id>', methods=['GET'])
def get_single_sdr(instance_id):
    instances = get_sdr_instances()
    instance = next((i for i in instances if i['id'] == instance_id), None)
    if not instance:
        return jsonify({"status": "error", "message": "Instance not found"}), 404
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
        return jsonify({"status": "success"})
    except Exception as e:
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

if __name__ == '__main__':
    logger.info("Starting PagerMonitor...")
    
    # Initialize components
    init_db()
    init_mqtt()
    
    # Start the SDR processing background thread
    start_sdr_thread()
    
    # Run the Flask web application
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
