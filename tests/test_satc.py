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
        """Verifiera korrekt formatering av frekvenser för RF-grafen inklusive station_id."""
        self.assertEqual(format_satc_frequency("1.537.106"), "1537.106M")
        self.assertEqual(format_satc_frequency("1.539.481."), "1539.481M")
        self.assertEqual(format_satc_frequency(1539421000), "1539.421M")
        self.assertEqual(format_satc_frequency("1539421000"), "1539.421M")
        self.assertEqual(format_satc_frequency(1539.975), "1539.975M")
        self.assertEqual(format_satc_frequency(1537700000), "1537.700M")
        self.assertEqual(format_satc_frequency(1541450000), "1541.450M")
        self.assertEqual(format_satc_frequency("1537.700 MHz"), "1537.700M")
        self.assertEqual(format_satc_frequency("1537.7M"), "1537.700M")
        self.assertEqual(format_satc_frequency(None), "1537.700M")

    def test_satdump_control_packets_filtering_and_formatting(self):
        """
        Verifierar de 4 skarpa SatDump-pakettyperna:
        1. Bulletin Board (type 7)
        2. Signalling Channel (type 6)
        3. Announcement (type 1)
        4. Logical Channel Assignment (type 3)
        Filtreras bort vid satc_only_messages=True och formateras på svenska vid satc_only_messages=False.
        """
        bulletin_board = {
            "channel_type": 1,
            "channel_type_name": "NCS",
            "descriptor": {"is_long": False, "is_medium": False, "is_short": True, "length": 14, "type": 7},
            "empty_frame": True,
            "frame_2_count": 0,
            "frame_number": 1896,
            "les_id": 44,
            "les_name": "344, NCS",
            "local_id": 0,
            "network_version": 216,
            "randomizing_interval": 10,
            "sat_id": 3,
            "sat_name": "Indian Ocean Region (IOR)",
            "seconds_of_day": 16381.44,
            "services": {"SafetyNet": True, "StoreFwd": True},
            "source": {"app": {"name": "SatDump", "version": "1.2.3-65aa43cd"}, "station_id": "1.537.106"},
            "status": {"in_service": True, "return_link_speed": 600},
            "timestamp": 1792125181.44
        }

        signalling_channel = {
            "descriptor": {"is_long": False, "is_medium": False, "is_short": True, "length": 13, "type": 6},
            "services": {"InmarsatC": True},
            "source": {"app": {"name": "SatDump", "version": "1.2.3-65aa43cd"}, "station_id": "1.537.106"},
            "tdm_slots": [0, 0, 0, 2, 0, 0],
            "timestamp": 1792125181.629,
            "uplink_freq_mhz": 1641.025
        }

        announcement = {
            "descriptor": {"is_long": False, "is_medium": True, "is_short": False, "length": 19, "type": 1},
            "direction": "To Mobile",
            "direction_b": 0,
            "downlink_freq_mhz": 1539.975,
            "last_count": 66,
            "les_id": 17,
            "les_name": "317, Morsviazsputnik, Russia",
            "logical_channel_number": 209,
            "mes_id": 14557376,
            "message_reference_number": 603706,
            "number_of_packets": 1,
            "presentation": 7,
            "priority": "Routine",
            "priority_b": 0,
            "sat_id": 3,
            "sat_name": "Indian Ocean Region (IOR)",
            "service": "Store And Forward",
            "service_b": 0,
            "source": {"app": {"name": "SatDump", "version": "1.2.3-65aa43cd"}, "station_id": "1.537.106"},
            "sub_address": 0,
            "timestamp": 1792125346.491
        }

        channel_assignment = {
            "am_pm_bit": False,
            "descriptor": {"is_long": False, "is_medium": True, "is_short": False, "length": 18, "type": 3},
            "direction": "From Mobile",
            "direction_b": 1,
            "downlink_freq_mhz": 1539.915,
            "duration": 1,
            "frame_length": 1,
            "frame_offset": 126,
            "last_count": 112,
            "les_id": 12,
            "les_name": "312, Stratos Global (Burum), Netherlands",
            "logical_channel_number": 114,
            "mes_id": 8037449,
            "message_channel": 11702,
            "number_of_packets": 0,
            "sat_id": 3,
            "sat_name": "Indian Ocean Region (IOR)",
            "service": "Store And Forward",
            "service_b": 0,
            "slot_number": 1,
            "source": {"app": {"name": "SatDump", "version": "1.2.3-65aa43cd"}, "station_id": "1.539.421"},
            "timestamp": 1792125346.1399999,
            "uplink_freq_mhz": 6.9133116446886e-310
        }

        # A) Verifiera att samtliga 4 filtreras bort när only_messages=True
        self.assertIsNone(parse_satc_frame(bulletin_board, only_messages=True))
        self.assertIsNone(parse_satc_frame(signalling_channel, only_messages=True))
        self.assertIsNone(parse_satc_frame(announcement, only_messages=True))
        self.assertIsNone(parse_satc_frame(channel_assignment, only_messages=True))

        # B) Verifiera svensk formatering och badgar när only_messages=False
        # 1. Bulletin Board
        res_bb = parse_satc_frame(bulletin_board, only_messages=False)
        self.assertIsNotNone(res_bb)
        self.assertEqual(res_bb['frequency'], '1537.106M')
        self.assertIn('[ Bulletin Board (NCS) ]', res_bb['message'])
        self.assertIn('Satellit: Indian Ocean Region (IOR)', res_bb['message'])
        self.assertIn('LES: 344, NCS', res_bb['message'])
        self.assertIn('Ram: #1896', res_bb['message'])
        self.assertIn('Uplink: 600 bps', res_bb['message'])
        self.assertIn('\nRådata: ', res_bb['message'])
        self.assertEqual(res_bb['metadata']['sat_badge'], 'Sat: IOR')
        self.assertEqual(res_bb['metadata']['les_badge'], 'LES: 344, NCS')
        self.assertFalse(contains_emoji(res_bb['message']))

        # 2. Signalling Channel
        res_sig = parse_satc_frame(signalling_channel, only_messages=False)
        self.assertIsNotNone(res_sig)
        self.assertEqual(res_sig['frequency'], '1537.106M')
        self.assertIn('[ Signalling Channel ]', res_sig['message'])
        self.assertIn('Uplink: 1641.025 MHz | TDM-tidluckor', res_sig['message'])
        self.assertFalse(contains_emoji(res_sig['message']))

        # 3. Announcement
        res_ann = parse_satc_frame(announcement, only_messages=False)
        self.assertIsNotNone(res_ann)
        self.assertEqual(res_ann['frequency'], '1537.106M')
        self.assertIn('[ Upprop / Announcement ] Till terminal (MES): 14557376', res_ann['message'])
        self.assertIn('Tjänst: Store And Forward (Routine)', res_ann['message'])
        self.assertIn('Hänvisad downlink: 1539.975 MHz (Kanal #209)', res_ann['message'])
        self.assertIn('Referens: #603706', res_ann['message'])
        self.assertEqual(res_ann['metadata']['mes_badge'], 'MES: 14557376')
        self.assertEqual(res_ann['metadata']['sat_badge'], 'Sat: IOR')
        self.assertFalse(contains_emoji(res_ann['message']))

        # 4. Logical Channel Assignment
        res_lca = parse_satc_frame(channel_assignment, only_messages=False)
        self.assertIsNotNone(res_lca)
        self.assertEqual(res_lca['frequency'], '1539.421M')
        self.assertIn('[ Kanalallokering ] Terminal (MES): 8037449', res_lca['message'])
        self.assertIn('Tjänst: Store And Forward', res_lca['message'])
        self.assertIn('Downlink: 1539.915 MHz (Kanal #114, Slot 1)', res_lca['message'])
        self.assertEqual(res_lca['metadata']['mes_badge'], 'MES: 8037449')
        self.assertEqual(res_lca['metadata']['les_badge'], 'LES: 312, Stratos Global (Burum), Netherlands')
        self.assertFalse(contains_emoji(res_lca['message']))

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

    def test_satc_configurable_host_ip(self):
        """Verifiera att användaren kan konfigurera en specifik IP-adress istället för 0.0.0.0 samt default port 6558."""
        receiver = SatCReceiver()
        self.assertEqual(receiver.host, '0.0.0.0')
        self.assertEqual(receiver.port, 6558)

        # Starta med anpassad IP
        receiver.start(host='192.168.1.150', port=6558, enabled=False)
        self.assertEqual(receiver.host, '192.168.1.150')
        status = receiver.get_status()
        self.assertEqual(status['host'], '192.168.1.150')
        self.assertEqual(status['port'], 6558)
        receiver.stop()

    def test_strict_no_emojis_in_source_code(self):
        """Verifiera att inga emojis förekommer i källkodsfilerna eller mallarna."""
        base_dir = os.path.dirname(os.path.dirname(__file__))
        check_files = [
            'satc_receiver.py',
            'app.py',
            'database.py',
            os.path.join('templates', 'settings.html'),
            os.path.join('templates', 'index.html'),
            os.path.join('templates', 'larm.html'),
            os.path.join('templates', 'statistics.html'),
            os.path.join('static', 'style.css')
        ]
        for rel_path in check_files:
            target = os.path.join(base_dir, rel_path)
            with open(target, 'r', encoding='utf-8') as f:
                code = f.read()
            self.assertFalse(contains_emoji(code), f"Fel: otillåtna emojis hittades i {rel_path}!")

if __name__ == '__main__':
    unittest.main()
