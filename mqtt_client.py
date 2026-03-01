import os
import json
import logging
import time

try:
    import paho.mqtt.client as mqtt
    # Support for paho-mqtt 2.0+
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        HAS_V2_API = True
    except ImportError:
        HAS_V2_API = False
except ImportError:
    class _DummyClient:
        def __init__(self, *args, **kwargs): pass
        def username_pw_set(self, *args, **kwargs): pass
        def connect(self, *args, **kwargs): pass
        def loop_start(self): pass
        def publish(self, *args, **kwargs): pass
    class mqtt:
        Client = _DummyClient
    HAS_V2_API = False

logger = logging.getLogger(__name__)

mqtt_client = None
MQTT_TOPIC = os.environ.get('MQTT_TOPIC', 'pagermonitor/alarms')

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Successfully connected to MQTT broker")
    else:
        logger.error(f"MQTT connection failed with result code {rc}")

def on_disconnect(client, userdata, rc, properties=None):
    if rc != 0:
        logger.warning(f"Unexpected MQTT disconnection (rc={rc}). Will attempt to reconnect.")

def init_mqtt():
    global mqtt_client
    broker = os.environ.get('MQTT_BROKER', '192.168.1.121')
    port = int(os.environ.get('MQTT_PORT', '1883'))
    user = os.environ.get('MQTT_USER')
    password = os.environ.get('MQTT_PASS')

    try:
        if HAS_V2_API:
            mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION1)
        else:
            mqtt_client = mqtt.Client()

        if user and password:
            mqtt_client.username_pw_set(user, password)
        
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        
        # Configure automatic reconnection
        mqtt_client.reconnect_delay_set(min_delay=1, max_delay=120)
        
        logger.info(f"Attempting to connect to MQTT broker at {broker}:{port}...")
        # Use non-blocking connect if possible, paho-mqtt handles loop
        mqtt_client.connect_async(broker, port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.error(f"Failed to initialize MQTT client: {e}")
        # Don't set to None, so publish_message can still try to log errors or wait for reconnection
        # but if it crashed hard, we should know
        if not mqtt_client:
            mqtt_client = None

def publish_message(address, message, timestamp, alias='', metadata=None):
    global mqtt_client
    if not mqtt_client:
        return

    payload = {
        'timestamp': timestamp,
        'address': address,
        'message': message,
        'alias': alias
    }
    
    if metadata:
        payload.update(metadata)
    
    try:
        # Check if connected before publishing (optional, publish usually queues if disconnected)
        info = mqtt_client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
        # We don't wait for publish here to keep it async/fast
        # if info.rc != mqtt.MQTT_ERR_SUCCESS:
        #     logger.warning(f"MQTT publish returned code {info.rc}")
    except Exception as e:
        logger.error(f"MQTT publish failed: {e}")
