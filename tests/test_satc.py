import unittest
import re
import json
import os
from database import init_db, get_connection
from satc_receiver import (
    SatCReceiver, parse_satc_frame, extract_coordinates,
    format_satc_frequency, normalize_satc_priority, classify_satc_service,
    send_test_satc_message, get_satc_status
)

def contains_emoji(text):
    """Kontrollerar om en textsträng innehåller några otillåtna emojis."""
    if not text:
        return False
    # Regex för emojis (Emoticons, Miscellaneous Symbols and Pictographs, Transport, Supplemental, etc.)
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Misc Symbols & Pictographs
        "\U0001F680-\U0001F6FF"  # Transport & Map
        "\U0001F1E0-\U0001F1FF"  # Flags
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols & Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    return bool(emoji_pattern.search(str(text)))

class TestSatCReceiver(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_parse_safetynet_message(self):
        """Testar parsning av ett Inmarsat EGC SafetyNET navigationsvarningsmeddelande."""
        frame = {
            "station": "SatDump",
            "freq": 1537700000,
            "type": "EGC",
            "les_id": 2,
            "les_name": "Burum",
            "service": "SafetyNET",
            "priority": "Safety",
            "navarea": "NAVAREA I",
            "text": "151200 UTC OCT\nNAVAREA I 123\nENGLAND, SOUTH COAST. DOVER STRAIT.\nLIGHT BUOY OFF STATION AT 51-12.4N 001-24.8E.\nVESSELS IN VICINITY REQUESTED TO KEEP A SHARP LOOKOUT."
        }

        parsed = parse_satc_frame(frame, only_messages=True)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['address'], 'LES: Burum')
        self.assertEqual(parsed['alias'], 'SafetyNET (EGC)')
        self.assertEqual(parsed['frequency'], '1537.700M')
        self.assertEqual(parsed['priority'], 'Safety')
        self.assertFalse(parsed['is_alert'])
        self.assertEqual(parsed['navarea'], 'NAVAREA I')
        self.assertEqual(parsed['service_badge'], 'EGC: Navwarn / Sjöfartsvarning')

        # Verifiera koordinater
        self.assertIsNotNone(parsed['lat'])
        self.assertIsNotNone(parsed['lon'])
        self.assertAlmostEqual(parsed['lat'], 51.20667, places=4)
        self.assertAlmostEqual(parsed['lon'], 1.41333, places=4)

        # Verifiera svensk sammanfattning överst
        self.assertTrue(parsed['message'].startswith('[Inmarsat SafetyNET / Sjöfartsvarning]'))
        self.assertIn('Område: NAVAREA I', parsed['message'])
        self.assertIn('Jordstation: Burum', parsed['message'])
        self.assertIn('Prioritet: Safety', parsed['message'])

        # Verifiera att Rådata-sektionen finns
        self.assertIn('\nRådata: ', parsed['message'])
        raw_part = parsed['message'].split('\nRådata: ')[1]
        raw_obj = json.loads(raw_part)
        self.assertEqual(raw_obj['les_name'], 'Burum')

        # Verifiera inga emojis
        self.assertFalse(contains_emoji(parsed['message']))
        self.assertFalse(contains_emoji(parsed['address']))
        self.assertFalse(contains_emoji(parsed['alias']))
        self.assertFalse(contains_emoji(parsed['service_badge']))

    def test_parse_distress_sar_message(self):
        """Testar parsning av ett Inmarsat EGC Distress / SAR sjöräddningslarm."""
        frame = {
            "station": "SatDump",
            "freq": 1537700000,
            "type": "EGC",
            "les_id": 2,
            "les_name": "Burum",
            "service": "SAR",
            "priority": "Distress",
            "navarea": "NAVAREA I",
            "text": "151800 UTC OCT\nDISTRESS ALERT RELAY\nMRCC OSTEND DE INMARSAT-C\nVESSEL 'NORDIC SEA' IN DISTRESS POSITION 58-34.2N 016-12.5E\nVESSEL TAKING IN WATER. 4 PERSONS ON BOARD IN LIFE RAFT.\nALL SHIPS IN VICINITY PROCEED AND ASSIST."
        }

        parsed = parse_satc_frame(frame, only_messages=True)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['address'], 'LES: Burum')
        self.assertEqual(parsed['alias'], 'SAR / Distress')
        self.assertEqual(parsed['priority'], 'DISTRESS')
        self.assertTrue(parsed['is_alert'])
        self.assertEqual(parsed['service_badge'], 'EGC: SAR (Sjöräddning)')

        # Verifiera koordinater
        self.assertIsNotNone(parsed['lat'])
        self.assertIsNotNone(parsed['lon'])
        self.assertAlmostEqual(parsed['lat'], 58.57, places=4)
        self.assertAlmostEqual(parsed['lon'], 16.20833, places=4)

        # Verifiera svensk sammanfattning
        self.assertTrue(parsed['message'].startswith('[Inmarsat SafetyNET / Sjöräddning (SAR)]'))
        self.assertIn('Prioritet: DISTRESS', parsed['message'])

        # Verifiera inga emojis
        self.assertFalse(contains_emoji(parsed['message']))
        self.assertFalse(contains_emoji(parsed['alias']))

    def test_filter_empty_tdm_signalling_frames(self):
        """Verifiera att tomma TDM/signaleringsramar filtreras bort om only_messages=True."""
        bb_frame = {
            "type": "Bulletin Board",
            "les_id": 1,
            "frame_num": 128
        }
        res_filtered = parse_satc_frame(bb_frame, only_messages=True)
        self.assertIsNone(res_filtered)

        res_allowed = parse_satc_frame(bb_frame, only_messages=False)
        self.assertIsNotNone(res_allowed)
        self.assertIn("Bulletin Board", res_allowed['message'])

        sig_frame = {
            "type": "Signalling channel descriptor",
            "les_id": 2
        }
        self.assertIsNone(parse_satc_frame(sig_frame, only_messages=True))

    def test_extract_coordinates_formats(self):
        """Verifiera robust extrahering ur olika sjöfartsformat."""
        # 1. Hyphenated
        lat, lon = extract_coordinates("PSN 58-34.2N 016-12.5E")
        self.assertAlmostEqual(lat, 58.57, places=4)
        self.assertAlmostEqual(lon, 16.20833, places=4)

        # 2. Spaced
        lat, lon = extract_coordinates("POSITION 58 34N 016 12E")
        self.assertAlmostEqual(lat, 58.56667, places=4)
        self.assertAlmostEqual(lon, 16.2, places=4)

        # 3. Kompakt
        lat, lon = extract_coordinates("IN VICINITY 5834N 01612E")
        self.assertAlmostEqual(lat, 58.56667, places=4)
        self.assertAlmostEqual(lon, 16.2, places=4)

        # 4. Syd och Väst (negativa grader)
        lat, lon = extract_coordinates("REPORTED AT 12-30.0S 045-15.0W")
        self.assertAlmostEqual(lat, -12.5, places=4)
        self.assertAlmostEqual(lon, -45.25, places=4)

        # 5. Decimalgrader
        lat, lon = extract_coordinates("COORDINATES 58.5700N 016.2083E")
        self.assertAlmostEqual(lat, 58.5700, places=4)
        self.assertAlmostEqual(lon, 16.2083, places=4)

        # 6. Tom eller ogiltig sträng
        self.assertEqual(extract_coordinates(""), (None, None))
        self.assertEqual(extract_coordinates("Inga koordinater här"), (None, None))

    def test_format_satc_frequency(self):
        """Verifiera korrekt formatering av frekvenser för RF-grafen."""
        self.assertEqual(format_satc_frequency(1537700000), "1537.700M")
        self.assertEqual(format_satc_frequency(1541450000), "1541.450M")
        self.assertEqual(format_satc_frequency("1537.700 MHz"), "1537.700M")
        self.assertEqual(format_satc_frequency("1537.7M"), "1537.700M")
        self.assertEqual(format_satc_frequency(None), "1537.700M")

    def test_send_test_satc_message_api(self):
        """Verifiera sändning av syntetiska testmeddelanden och status."""
        receiver = SatCReceiver()
        received_events = []
        receiver.set_callback(lambda d: received_events.append(d))

        res_safety = send_test_satc_message(is_distress=False)
        self.assertEqual(res_safety['status'], 'success')
        self.assertEqual(res_safety['address'], 'LES: Burum')

        res_distress = send_test_satc_message(is_distress=True)
        self.assertEqual(res_distress['status'], 'success')
        self.assertEqual(res_distress['alias'], 'SAR / Distress')

        status = get_satc_status()
        self.assertIn('packets_received', status)
        self.assertIn('messages_decoded', status)
        self.assertIn('status', status)

    def test_strict_no_emojis_in_source_code(self):
        """Verifiera att inga emojis förekommer i källkodsfilen satc_receiver.py."""
        receiver_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'satc_receiver.py')
        with open(receiver_path, 'r', encoding='utf-8') as f:
            code = f.read()
        self.assertFalse(contains_emoji(code), "Fel: otillåtna emojis hittades i satc_receiver.py!")

if __name__ == '__main__':
    unittest.main()
