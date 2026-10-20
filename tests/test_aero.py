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

    def test_parse_mdwxr_weather_and_dispatch(self):
        """Verifiera tolkning av #MDWXR vädermeddelande och callsign-extraktion (Reach / US Air Force)."""
        raw_frame = {
            "station": "SatDump",
            "freq": 1545150000,
            "channel": "P-Channel",
            "ges_id": 5,
            "acars": {
                "label": "H1",
                "message": ". - #MDWXR/ID00172A,RCH241,JMZN2922C285/MR1,44/MTLTAG,0757,TAF LTAG 0757Z VRB02KT CAVOK T21C A3015 REQUEST PIREP AS MISSON PERMITSFC54"
            }
        }
        parsed = parse_aero_frame(raw_frame)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['flight'], 'RCH241')
        self.assertEqual(parsed['airline'], 'Air Mobility Command')
        self.assertEqual(parsed['address'], 'RCH241')
        self.assertEqual(parsed['alias'], 'Air Mobility Command')
        self.assertIn("Flygplatsväder (TAF)", parsed['message'])
        self.assertIn("LTAG", parsed['message'])
        self.assertIn("07:57 UTC", parsed['message'])
        self.assertIn("RCH241", parsed['message'])
        self.assertIn("JMZN2922C285", parsed['message'])
        self.assertIn("CAVOK", parsed['message'])
        self.assertIn("21 C", parsed['message'])
        self.assertIn("Begär pilotrapport (PIREP)", parsed['message'])
        self.assertEqual(parsed['metadata']['dst_airport'], 'LTAG')

    def test_parse_n66000_w020000_position(self):
        """Verifiera att kompakta Inmarsat-koordinater (N66000, W020000) beräknas och sätts i lat/lon."""
        raw_frame = {
            "station": "SatDump",
            "freq": 1545150000,
            "channel": "P-Channel",
            "ges_id": 5,
            "acars": {
                "label": "H1",
                "message": "N66000, W020000"
            }
        }
        parsed = parse_aero_frame(raw_frame)
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(parsed['lat'])
        self.assertIsNotNone(parsed['lon'])
        self.assertEqual(parsed['lat'], 66.0)
        self.assertEqual(parsed['lon'], -20.0)
        self.assertIn("Position: 66.0000, -20.0000", parsed['message'])

    def test_parse_short_requests_and_time_sync(self):
        """Verifiera tolkning av PACEPOSREQ, REQPOS och Label 52 UTC-tidssynk."""
        # 1. PACEPOSREQ (Label 2F)
        p1 = parse_aero_frame({
            "station": "SatDump",
            "acars": {"label": "2F", "message": "PACEPOSREQ"}
        })
        self.assertIn("Begäran om positionsrapport (AOC Position Request)", p1['message'])

        # 2. REQPOS (Label 15)
        p2 = parse_aero_frame({
            "station": "SatDump",
            "acars": {"label": "15", "message": "REQPOS"}
        })
        self.assertIn("Begäran om positionsrapport (REQPOS)", p2['message'])

        # 3. Label 52 UTC Time Synchronisation (2610202061500 -> 2026-10-20 kl 06:15:00 UTC)
        p3 = parse_aero_frame({
            "station": "SatDump",
            "acars": {"label": "52", "message": "2610202061500"}
        })
        self.assertIn("Tidssynkronisering (UTC)", p3['message'])
        self.assertIn("2026-10-20", p3['message'])
        self.assertIn("06:15:00 UTC", p3['message'])

if __name__ == '__main__':
    unittest.main()
