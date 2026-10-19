import unittest
import json
import time
from aero_receiver import (
    lookup_ges_name,
    format_aero_freq,
    extract_aero_coordinates,
    parse_aero_frame,
    AeroReceiver,
    aero_receiver,
    send_test_aero_message,
    get_aero_status
)
from app import app
from database import get_settings, update_setting

class TestAeroReceiver(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_lookup_ges_name(self):
        """Verifiera uppslag av markstationer (GES) för Classic Aero."""
        self.assertEqual(lookup_ges_name(1), "Santa Paula (USA)")
        self.assertEqual(lookup_ges_name(2), "Southbury (USA)")
        self.assertEqual(lookup_ges_name(5), "Burum (Nederländerna)")
        self.assertEqual(lookup_ges_name(6), "Perth (Australien)")
        self.assertEqual(lookup_ges_name(14), "Fucino (Italien)")
        self.assertEqual(lookup_ges_name("14"), "Fucino (Italien)")
        self.assertEqual(lookup_ges_name(None), "")
        self.assertEqual(lookup_ges_name(""), "")

    def test_format_aero_freq(self):
        """Verifiera formatering av satellitfrekvenser (L-band MHz)."""
        self.assertEqual(format_aero_freq(1545150000), "1545.150M")
        self.assertEqual(format_aero_freq(1545.150), "1545.150M")
        self.assertEqual(format_aero_freq("1545.150M"), "1545.150M")
        self.assertEqual(format_aero_freq(None), "1545.150M")
        self.assertEqual(format_aero_freq(0), "1545.150M")

    def test_extract_aero_coordinates(self):
        """Verifiera extraktion av lat/lon från positionsrapporter."""
        # 1. Decimalformat
        lat, lon = extract_aero_coordinates("Pos: 58.1234, 18.5678")
        self.assertEqual((lat, lon), (58.1234, 18.5678))

        # 2. Riktat format (N/S, E/W)
        lat, lon = extract_aero_coordinates("N 59.350, E 18.100")
        self.assertEqual((lat, lon), (59.35, 18.1))

        # 3. Kompakt grad/minut-format
        lat, lon = extract_aero_coordinates("POS 5921N 01806E")
        self.assertIsNotNone(lat)
        self.assertIsNotNone(lon)
        self.assertAlmostEqual(lat, 59.35, places=2)
        self.assertAlmostEqual(lon, 18.10, places=2)

        # 4. Ogiltig eller tom text
        self.assertEqual(extract_aero_coordinates(""), (None, None))
        self.assertEqual(extract_aero_coordinates("Inga koordinater här"), (None, None))

    def test_parse_aero_frame_satdump(self):
        """Verifiera parsning av SatDump inmarsat_aero JSON-ram."""
        satdump_frame = {
            "station": "SatDump",
            "freq": 1545150000,
            "channel": "P-Channel",
            "ges_id": 5,
            "ges_name": "Burum",
            "aes_id": "4ACA8E",
            "acars": {
                "flight": "SK903",
                "tail": "SE-RTN",
                "label": "H1",
                "msgno": "M42A",
                "block_id": "1",
                "text": "FMS POS RPT\nFLIGHT SK903\nPOS 59.3500N 018.1000E\nALT FL380"
            }
        }

        parsed = parse_aero_frame(satdump_frame)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['address'], "SK903 (SE-RTN)")
        self.assertEqual(parsed['flight'], "SK903")
        self.assertEqual(parsed['reg'], "SE-RTN")
        self.assertEqual(parsed['icao'], "4ACA8E")
        self.assertEqual(parsed['frequency'], "1545.150M")
        self.assertEqual(parsed['bitrate'], "AERO-P-Channel")
        self.assertIn("SAS", parsed['alias'])
        self.assertEqual(parsed['station_id'], "Burum")
        self.assertIsNotNone(parsed['lat'])
        self.assertIsNotNone(parsed['lon'])
        self.assertAlmostEqual(parsed['lat'], 59.35, places=2)
        self.assertAlmostEqual(parsed['lon'], 18.10, places=2)
        self.assertIn("FMS POS RPT", parsed['message'])

    def test_parse_aero_frame_cpdlc(self):
        """Verifiera parsning av CPDLC / Oceanic Oceanic Clearance."""
        cpdlc_frame = {
            "station": "SatDump",
            "freq": 1545150000,
            "channel": "P-Channel",
            "ges_id": 2,
            "aes_id": "461F6D",
            "acars": {
                "flight": "AY1422",
                "tail": "OH-LXL",
                "label": "21",
                "msgno": "M15B",
                "text": "/CPDLC OCEANIC CLEARANCE CLR TO BOSTON VIA 58N020W MAINTAIN FL370"
            }
        }

        parsed = parse_aero_frame(cpdlc_frame)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['flight'], "AY1422")
        self.assertEqual(parsed['reg'], "OH-LXL")
        self.assertIn("Finnair", parsed['alias'])
        self.assertEqual(parsed['station_id'], "Southbury (USA)")
        self.assertIn("CPDLC", parsed['message'])

    def test_receiver_status_and_defaults(self):
        """Verifiera standardinställningar och status för AeroReceiver."""
        rx = AeroReceiver()
        status = rx.get_status()
        self.assertEqual(status['status'], 'stopped')
        self.assertEqual(status['port'], 6559)
        self.assertEqual(status['host'], '0.0.0.0')
        self.assertTrue(status['enabled'])

    def test_api_aero_status_endpoint(self):
        """Verifiera /api/aero/status endpoint."""
        resp = self.app.get('/api/aero/status')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('status', data)
        self.assertIn('port', data)
        self.assertIn('messages_decoded', data)

    def test_api_aero_test_endpoint(self):
        """Verifiera /api/aero/test endpoint med CPDLC och positionsrapporter."""
        # 1. Standardtest (CPDLC)
        resp = self.app.post('/api/aero/test', json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn('AY1422', data.get('address', ''))

        # 2. Positionstest (FMS/ADS-C)
        resp_pos = self.app.post('/api/aero/test', json={'pos': True})
        self.assertEqual(resp_pos.status_code, 200)
        data_pos = resp_pos.get_json()
        self.assertEqual(data_pos.get('status'), 'success')
        self.assertIn('SK903', data_pos.get('address', ''))

    def test_settings_aero_save_and_restart(self):
        """Verifiera att inställningar för Inmarsat AERO kan sparas via /settings och startas om."""
        resp = self.app.post('/api/settings', json={
            'aero_enabled': 'true',
            'aero_host': '0.0.0.0',
            'aero_port': '6559',
            'aero_only_messages': 'true'
        })
        self.assertEqual(resp.status_code, 200)
        st = get_settings()
        self.assertEqual(st.get('aero_port'), '6559')
        self.assertEqual(st.get('aero_enabled'), 'true')

if __name__ == '__main__':
    unittest.main()
