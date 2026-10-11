import sys
sys.path.append('d:/antigravity/pager-monitor')

def test_imports():
    try:
        import mqtt_client
        print("MQTT Client imported successfully.")
        import sdr_processor
        print("SDR Processor imported successfully.")
    except Exception as e:
        import traceback
        traceback.print_exc()

test_imports()
