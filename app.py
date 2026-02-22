import logging
from flask import Flask, jsonify, render_template, request, Response
import json
import time
from queue import Queue

from database import init_db, get_recent_messages, get_settings, update_setting, get_aliases, save_alias, delete_alias
from mqtt_client import init_mqtt
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
@app.route('/settings')
def settings_page():
    return render_template('settings.html')
@app.route('/aliases')
def aliases_page():
    return render_template('aliases.html')

@app.route('/api/messages')
def get_messages():
    messages = get_recent_messages(100)
    return jsonify(messages)

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.json
        # Handle each setting explicitly to prevent injected keys
        allowed_keys = ['frequency', 'gain', 'device_serial']
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
    def event_stream():
        q = Queue()
        client_queues.append(q)
        try:
            while True:
                msg = q.get()
                yield f"data: {json.dumps(msg)}\n\n"
        except GeneratorExit:
            client_queues.remove(q)
            
    return Response(event_stream(), content_type='text/event-stream')

if __name__ == '__main__':
    logger.info("Starting PagerMonitor...")
    
    # Initialize components
    init_db()
    init_mqtt()
    
    # Start the SDR processing background thread
    start_sdr_thread()
    
    # Run the Flask web application
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
