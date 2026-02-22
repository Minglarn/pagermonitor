import logging
from flask import Flask, jsonify, render_template

from database import init_db, get_recent_messages
from mqtt_client import init_mqtt
from sdr_processor import start_sdr_thread

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/messages')
def get_messages():
    messages = get_recent_messages(100)
    return jsonify(messages)

if __name__ == '__main__':
    logger.info("Starting PagerMonitor...")
    
    # Initialize components
    init_db()
    init_mqtt()
    
    # Start the SDR processing background thread
    start_sdr_thread()
    
    # Run the Flask web application
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
