import unittest
import time
import json
from acars_human_parser import parse_acars_payload, parse_human_acars
from acars_receiver import (
    parse_acars_message, ACARSReceiver, acars_receiver, 
    send_test_acars_message, get_acars_status
)

class TestAcarsPayloadAndReceiver(unittest.TestCase):
    def setUp(self):
        acars_receiver.recent_cache.clear()

    def test_parse_acars_payload_fm3(self):
        text = "FM3 194836,2147,N 57.686,E 18.017,33186,  399,80"
        meta = {}
        fields = parse_acars_payload(text, label="2P", metadata=meta)
        
        self.assertIsNotNone(fields)
        self.assertEqual(fields.get('report_type'), "Flight Report (FM3)")
        self.assertEqual(fields.get('time_utc'), "19:48:36")
        self.assertEqual(fields.get('eta_utc'), "21:47:00")
        self.assertEqual(fields.get('lat'), 57.686)
        self.assertEqual(fields.get('lon'), 18.017)
        self.assertEqual(fields.get('altitude_ft'), 33186)
        self.assertEqual(fields.get('extra'), "399, 80")
        
        # Metadata ska också vara berikad
        self.assertEqual(meta.get('lat'), 57.686)
        self.assertEqual(meta.get('lon'), 18.017)
        self.assertEqual(meta.get('alt_ft'), 33186)
        self.assertEqual(meta.get('eta'), "21:47:00")
        self.assertIn('decoded_fields', meta)

    def test_parse_acars_payload_fm1_fm2(self):
        text_fm1 = "FM1 123045,1345,S 12.345,W 045.678,28000, 420, 180"
        meta = {}
        fields = parse_acars_payload(text_fm1, label="2P", metadata=meta)
        self.assertIsNotNone(fields)
        self.assertEqual(fields.get('report_type'), "Flight Report (FM1)")
        self.assertEqual(fields.get('lat'), -12.345)
        self.assertEqual(fields.get('lon'), -45.678)
        self.assertEqual(fields.get('altitude_ft'), 28000)
        self.assertEqual(fields.get('time_utc'), "12:30:45")
        self.assertEqual(fields.get('eta_utc'), "13:45:00")

    def test_parse_acars_payload_oooi(self):
        text_out = "OUT / ESSA 1420 / FOB 12500"
        meta = {}
        fields = parse_acars_payload(text_out, label="QA", metadata=meta)
        self.assertIsNotNone(fields)
        self.assertEqual(fields.get('oooi_event'), "OUT")
        self.assertEqual(fields.get('airport'), "ESSA")
        self.assertEqual(fields.get('time_utc'), "14:20:00")
        self.assertEqual(fields.get('fuel_on_board'), "12500")

    def test_parse_acars_payload_weather_metar(self):
        text_metar = "METAR ESSA 161850Z 24008KT 9999 FEW040 09/04 Q1018 NOSIG"
        meta = {}
        fields = parse_acars_payload(text_metar, label="RA", metadata=meta)
        self.assertIsNotNone(fields)
        self.assertEqual(fields.get('wx_type'), "METAR")
        self.assertEqual(fields.get('wx_airport'), "ESSA")

    def test_parse_acars_payload_weather_atis(self):
        text_atis = "ATIS ESSA INFO D 1850Z RUNWAY IN USE 01L"
        meta = {}
        fields = parse_acars_payload(text_atis, label="B9", metadata=meta)
        self.assertIsNotNone(fields)
        self.assertEqual(fields.get('wx_type'), "ATIS")
        self.assertEqual(fields.get('wx_airport'), "ESSA")

    def test_parse_human_acars_with_fm3_payload(self):
        raw = "FM3 194836,2147,N 57.686,E 18.017,33186,  399,80"
        meta = {}
        formatted = parse_human_acars(raw, label="2P", metadata=meta)
        self.assertIn("Lat 57.686, Lon 18.017", formatted)
        self.assertIn("33 186 ft", formatted)
        self.assertIn("decoded_fields", meta)
        self.assertEqual(meta['decoded_fields'].get('eta_utc'), "21:47:00")

    def test_parse_acars_message_full_json(self):
        acars_json = {
            "timestamp": 1713297600.0,
            "station_id": "TEST_VHF",
            "channel": 1,
            "freq": 131.525,
            "level": -12.5,
            "error": 0,
            "mode": "2",
            "label": "2P",
            "block_id": "0",
            "ack": "!",
            "tail": "SE-ROA",
            "flight": "SK1401",
            "msgno": "M12A",
            "text": "FM3 194836,2147,N 57.686,E 18.017,33186,  399,80"
        }
        res = parse_acars_message(acars_json)
        self.assertIsNotNone(res)
        self.assertEqual(res['protocol'], 'ACARS')
        self.assertEqual(res['bitrate'], 'VHF-ACARS')
        self.assertEqual(res['source_type'], 'ACARS')
        self.assertEqual(res['alias'], 'SAS')
        self.assertEqual(res['address'], 'SK1401 (SE-ROA)')
        self.assertEqual(res['flight'], 'SK1401')
        self.assertEqual(res['reg'], 'SE-ROA')
        self.assertIn('SAS', res['airline'])
        
        meta = res.get('metadata', {})
        self.assertEqual(meta.get('freq'), 131.525)
        self.assertEqual(meta.get('station_id'), 'TEST_VHF')
        self.assertEqual(meta.get('label'), '2P')
        self.assertEqual(meta.get('lat'), 57.686)
        self.assertEqual(meta.get('lon'), 18.017)
        self.assertEqual(meta.get('alt_ft'), 33186)
        self.assertEqual(meta.get('eta'), "21:47:00")
        self.assertIn('decoded_fields', meta)
        self.assertEqual(meta['decoded_fields']['report_type'], 'Flight Report (FM3)')

    def test_acars_receiver_status_and_test_message(self):
        received_msgs = []
        def notify(msg):
            received_msgs.append(msg)

        acars_receiver.set_callback(notify)
        status = get_acars_status()
        self.assertIn('connected', status)
        self.assertIn('packets_received', status)

        # Skicka testmeddelande via send_test_acars_message
        res = send_test_acars_message()
        self.assertEqual(res.get('status'), 'success')
        self.assertGreaterEqual(len(received_msgs), 1)
        test_msg = received_msgs[-1]
        self.assertEqual(test_msg['protocol'], 'ACARS')
        self.assertEqual(test_msg['bitrate'], 'VHF-ACARS')
        self.assertIn('SAS', test_msg.get('airline', ''))

if __name__ == '__main__':
    unittest.main()
