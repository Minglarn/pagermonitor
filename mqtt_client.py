import os
import paho.mqtt.client as mqtt
import json
import logging

logger = logging.getLogger(__name__)

mqtt_client = None

def init_mqtt():
    global mqtt_client
    broker = os.environ.get('MQTT_BROKER', '192.168.1.121')
    port = int(os.environ.get('MQTT_PORT', '1883'))
    user = os.environ.get('MQTT_USER')
    password = os.environ.get('MQTT_PASS')

    mqtt_client = mqtt.Client()

    if user and password:
        mqtt_client.username_pw_set(user, password)
    
    try:
        mqtt_client.connect(broker, port, 60)
        mqtt_client.loop_start()
        logger.info(f"Connected to MQTT broker at {broker}:{port}")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
        mqtt_client = None

def publish_message(address, message, timestamp, alias=''):
    global mqtt_client
    if not mqtt_client:
        return

    payload = {
        'timestamp': timestamp,
        'address': address,
        'message': message,
        'alias': alias
    }
    
    try:
        mqtt_client.publish('pagermonitor/alarms', json.dumps(payload))
    except Exception as e:
        logger.error(f"MQTT publish failed: {e}")
