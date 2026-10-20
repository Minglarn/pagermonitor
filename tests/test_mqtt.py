import unittest
import json
from unittest.mock import MagicMock, patch
import mqtt_client
from mqtt_client import publish_message, split_message_and_raw, _sanitize_raw_dict

class TestMqttClient(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        mqtt_client.mqtt_client = self.mock_client

    def tearDown(self):
        mqtt_client.mqtt_client = None

    def test_split_message_and_raw_newline(self):
        msg = "Inmarsat Aero [DLH400] ADS-C Positionsrapport\nRådata: {\"station\": \"SatDump\", \"freq\": 1545150000}"
        clean, raw = split_message_and_raw(msg)
        self.assertEqual(clean, "Inmarsat Aero [DLH400] ADS-C Positionsrapport")
        self.assertEqual(raw, '{"station": "SatDump", "freq": 1545150000}')

    def test_split_message_and_raw_pipe(self):
        msg = "[AOC Flygbolagsdata] Intern driftrapport | Rådata: 07336019 8991 9536"
        clean, raw = split_message_and_raw(msg)
        self.assertEqual(clean, "[AOC Flygbolagsdata] Intern driftrapport")
        self.assertEqual(raw, "07336019 8991 9536")

    def test_split_message_and_raw_none(self):
        msg = "POCSAG larm: Brand i villa, Storgatan 1"
        clean, raw = split_message_and_raw(msg)
        self.assertEqual(clean, msg)
        self.assertIsNone(raw)

    def test_publish_message_separates_raw_json(self):
        raw_obj = {
            "station": "SatDump",
            "freq": 1545150000,
            "channel": "P-Channel",
            "acars": {
                "flight": "DLH400",
                "message": "/YQXE2YA.CR1..."
            }
        }
        msg_with_raw = f"[Inmarsat Aero / DLH400] ADS-C Positionsrapport\nRådata: {json.dumps(raw_obj)}"

        publish_message(
            address="DLH400 (D-AIGV)",
            message=msg_with_raw,
            timestamp="2026-10-20T10:50:00",
            alias="Lufthansa",
            metadata={"protocol": "AERO", "flight": "DLH400"}
        )

        self.mock_client.publish.assert_called_once()
        topic, payload_str = self.mock_client.publish.call_args[0][:2]
        payload = json.loads(payload_str)

        # 1. message ska vara ren och kort - INGEN rådata
        self.assertEqual(payload['message'], "[Inmarsat Aero / DLH400] ADS-C Positionsrapport")
        self.assertNotIn("Rådata:", payload['message'])
        self.assertNotIn("SatDump", payload['message'])

        # 2. raw_data ska finnas som ett separat fält
        self.assertIn('raw_data', payload)
        self.assertEqual(payload['raw_data']['station'], "SatDump")
        self.assertEqual(payload['raw_data']['freq'], 1545150000)

        # 3. Övriga metadatafält ska finnas kvar
        self.assertEqual(payload['protocol'], "AERO")
        self.assertEqual(payload['flight'], "DLH400")

    def test_publish_message_separates_raw_text(self):
        msg_with_raw = "Begär flygplatsväder (ATIS) för ESSA\nRådata: /ARN.TI2/026ESSA0700"

        publish_message(
            address="SK142",
            message=msg_with_raw,
            timestamp="2026-10-20T10:51:00",
            alias="SAS",
            metadata={"protocol": "ACARS"}
        )

        self.mock_client.publish.assert_called_once()
        payload = json.loads(self.mock_client.publish.call_args[0][1])

        self.assertEqual(payload['message'], "Begär flygplatsväder (ATIS) för ESSA")
        self.assertEqual(payload['raw_data'], "/ARN.TI2/026ESSA0700")

    def test_publish_message_sanitizes_internal_fields_from_raw_data(self):
        raw_obj_with_internals = {
            "station": "SatDump",
            "libacars": {"arinc622": {"msg_type": "adsc"}},
            "decoded_fields": {"lat": 64.12},
            "acars": {
                "flight": "DLH400",
                "airline": "Lufthansa",
                "libacars": {"dummy": 1}
            }
        }
        msg = f"Kort rapport\nRådata: {json.dumps(raw_obj_with_internals)}"

        publish_message("123", msg, "2026-10-20T10:52:00")
        payload = json.loads(self.mock_client.publish.call_args[0][1])

        self.assertEqual(payload['message'], "Kort rapport")
        self.assertIn('raw_data', payload)
        self.assertNotIn('libacars', payload['raw_data'])
        self.assertNotIn('decoded_fields', payload['raw_data'])
        self.assertNotIn('airline', payload['raw_data']['acars'])
        self.assertNotIn('libacars', payload['raw_data']['acars'])

if __name__ == '__main__':
    unittest.main()
