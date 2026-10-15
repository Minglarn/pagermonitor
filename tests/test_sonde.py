import unittest
from sonde_receiver import (
    SondeState, SondeReceiver, format_sonde_model, format_frequency
)

class TestSondeReceiver(unittest.TestCase):
    def test_format_sonde_model(self):
        self.assertEqual(format_sonde_model('RS41-SG'), 'Vaisala RS41-SG')
        self.assertEqual(format_sonde_model('DFM09'), 'GRAW DFM-09')
        self.assertEqual(format_sonde_model('M10'), 'Meteomodem M10')
        self.assertEqual(format_sonde_model('UNKNOWN_MODEL'), 'UNKNOWN_MODEL')
        self.assertEqual(format_sonde_model(''), 'Radiosond')

    def test_format_frequency(self):
        self.assertEqual(format_frequency('403.500 MHz'), '403.500M')
        self.assertEqual(format_frequency('402.7M'), '402.7M')
        self.assertEqual(format_frequency(403500000), '403.500M')
        self.assertEqual(format_frequency(''), '403.500M')

    def test_sonde_state_telemetry_and_events(self):
        sonde = SondeState(callsign='V1420512', model='RS41-SG', freq='403.500M', station='TROSA_SDR')
        
        # Ascent packet
        pkt1 = {
            'type': 'PAYLOAD_SUMMARY',
            'station': 'TROSA_SDR',
            'callsign': 'V1420512',
            'model': 'RS41-SG',
            'freq': '403.500 MHz',
            'latitude': 58.12451,
            'longitude': 18.21044,
            'altitude': 18450.2,
            'vel_v': 5.4,
            'vel_h': 14.2,
            'heading': 315.0,
            'temp': -54.8,
            'humidity': 12.4,
            'pressure': 71.2,
            'batt': 2.9,
            'snr': 16.5,
            'frame': 2841,
            'time': '01:42:15'
        }
        event1 = sonde.update_telemetry(pkt1)
        self.assertEqual(event1, 'NORMAL')
        self.assertEqual(sonde.flight_state, 'ASCENDING')
        self.assertEqual(sonde.max_alt, 18450.2)
        self.assertEqual(len(sonde.track), 1)

        summary = sonde.get_summary_text()
        self.assertIn('18,450 m', summary)
        self.assertIn('-54.8', summary)

        # Higher ascent packet
        pkt2 = {
            'altitude': 32400.0,
            'vel_v': 6.1,
            'vel_h': 15.0,
            'latitude': 58.1500,
            'longitude': 18.2500
        }
        event2 = sonde.update_telemetry(pkt2)
        self.assertEqual(event2, 'NORMAL')
        self.assertEqual(sonde.max_alt, 32400.0)

        # Burst detection packet: altitude dropped significantly with strong negative vertical speed
        pkt_burst = {
            'altitude': 31900.0,
            'vel_v': -28.5,
            'vel_h': 10.0,
            'latitude': 58.1600,
            'longitude': 18.2600
        }
        event_burst = sonde.update_telemetry(pkt_burst)
        self.assertEqual(event_burst, 'BURST')
        self.assertEqual(sonde.flight_state, 'BURST')
        sonde.burst_logged = True

        # Landing detection packet
        pkt_land = {
            'altitude': 240.0,
            'vel_v': -0.4,
            'vel_h': 0.8,
            'latitude': 58.1800,
            'longitude': 18.3000
        }
        event_land = sonde.update_telemetry(pkt_land)
        self.assertEqual(event_land, 'LANDED')
        self.assertEqual(sonde.flight_state, 'LANDED')

    def test_receiver_payload_summary(self):
        receiver = SondeReceiver()
        received_events = []
        receiver.set_callback(lambda d: received_events.append(d))

        test_payload = {
            'type': 'PAYLOAD_SUMMARY',
            'station': 'TROSA_SDR',
            'callsign': 'T1234567',
            'model': 'RS41',
            'freq': '402.300 MHz',
            'latitude': 59.3293,
            'longitude': 18.0686,
            'altitude': 1250.0,
            'vel_v': 4.8,
            'vel_h': 8.2,
            'heading': 180.0,
            'temp': 12.0,
            'humidity': 65.0,
            'batt': 3.1,
            'snr': 22.0
        }
        receiver._handle_payload(test_payload)

        status = receiver.get_status()
        self.assertEqual(status['packets_received'], 1)
        self.assertEqual(status['last_callsign'], 'T1234567')
        self.assertGreaterEqual(status['active_sondes'], 1)

        active_sondes = receiver.get_active_sondes()
        self.assertEqual(len(active_sondes), 1)
        self.assertEqual(active_sondes[0]['callsign'], 'T1234567')
        self.assertEqual(active_sondes[0]['model'], 'Vaisala RS41')

if __name__ == '__main__':
    unittest.main()
