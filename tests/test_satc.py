import unittest
import re
import json
import os
from database import init_db, get_connection, check_alert_words, extract_body_for_alert_matching, save_alert_word
from satc_receiver import (
    SatCReceiver, parse_satc_frame, extract_coordinates,
    format_satc_frequency, normalize_satc_priority, classify_satc_service,
    send_test_satc_message, get_satc_status, clean_control_characters,
    is_binary_or_gibberish, decode_mime_headers
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
        # Larmflaggan (is_alert) styrs nu uteslutande av användarens larmordslista, inte av SATC-prioritet ensamt
        self.assertFalse(parsed['is_alert'])
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

    def test_satc_fragment_filtering(self):
        """
        Verifiera att ofullständiga delpaket (Multi-part fragments) filtreras bort när satc_only_messages=True:
        - 'EGC Double Header 1', 'EGC Double Header 2', 'Message Packet' ignoreras.
        - Endast 'Full Message' och 'Full EGC Message' sparas.
        - Meddelanden utan pkt_name släpps igenom om de inte har fragmentindikatorer.
        """
        # Delramar med pkt_name
        frag_dh1 = {
            "station": "SatDump",
            "pkt_name": "EGC Double Header 1",
            "text": "LES21 Marlink 10"
        }
        frag_dh2 = {
            "station": "SatDump",
            "pkt_name": "EGC Double Header 2",
            "text": ".10.107.29... NA"
        }
        frag_msg = {
            "station": "SatDump",
            "pkt_name": "Message Packet",
            "text": "VIGATE WITH CAUT"
        }
        full_egc = {
            "station": "SatDump",
            "pkt_name": "Full EGC Message",
            "text": "LES21 Marlink 10.10.107.29... NAVIGATE WITH CAUTION IN VICINITY 58-34N 016-12E"
        }
        full_msg = {
            "station": "SatDump",
            "pkt_name": "Full Message",
            "text": "COMPLETE STD-C MESSAGE DATA"
        }

        # Filtreras när only_messages=True
        self.assertIsNone(parse_satc_frame(frag_dh1, only_messages=True))
        self.assertIsNone(parse_satc_frame(frag_dh2, only_messages=True))
        self.assertIsNone(parse_satc_frame(frag_msg, only_messages=True))

        # Släpps igenom när det är Full Message / Full EGC Message
        res_full_egc = parse_satc_frame(full_egc, only_messages=True)
        self.assertIsNotNone(res_full_egc)
        self.assertIn("NAVIGATE WITH CAUTION", res_full_egc['message'])

        res_full_msg = parse_satc_frame(full_msg, only_messages=True)
        self.assertIsNotNone(res_full_msg)
        self.assertIn("COMPLETE STD-C MESSAGE DATA", res_full_msg['message'])

        # Paket med continuation eller is_fragment
        frag_cont = {
            "station": "SatDump",
            "continuation": True,
            "text": "PARTIAL DATA"
        }
        self.assertIsNone(parse_satc_frame(frag_cont, only_messages=True))

        # Paket utan pkt_name men komplett text släpps igenom
        no_pkt_name = {
            "station": "SatDump",
            "text": "SINGLE STANDALONE MESSAGE"
        }
        res_standalone = parse_satc_frame(no_pkt_name, only_messages=True)
        self.assertIsNotNone(res_standalone)
        self.assertIn("SINGLE STANDALONE MESSAGE", res_standalone['message'])

    def test_clean_control_characters(self):
        """
        Verifiera att icke-utskrivbara binära kontrolltecken (ASCII < 32 utom \n, \r, \t samt 0x7F)
        rensas bort från brödtexten så att krypterade eller råa paket hålls rena.
        """
        dirty_text = "HELLO\x00\x02WORLD\x18\x7F!\nRAD 2\tTABELL\r\nSLUT\x1F"
        cleaned = clean_control_characters(dirty_text)
        self.assertEqual(cleaned, "HELLOWORLD!\nRAD 2\tTABELL\r\nSLUT")

        # Testa även i parse_satc_frame (utan only_messages för råa tecken)
        frame = {
            "station": "SatDump",
            "pkt_name": "Full Message",
            "text": "RAW\x00\x02CLEANED\x18TEXT"
        }
        parsed = parse_satc_frame(frame, only_messages=False)
        self.assertIsNotNone(parsed)
        self.assertIn("RAWCLEANEDTEXT", parsed['message'])
        self.assertNotIn("\x00", parsed['message'])
        self.assertNotIn("\x02", parsed['message'])
        self.assertNotIn("\x18", parsed['message'])

    def test_satc_binary_and_gibberish_filtering(self):
        """
        Verifiera att strikta binär- och skräpfiltret (is_binary_or_gibberish) filtrerar bort:
        1. Ryska 5PRCRYPTO/5PSCRYPTO-paket med kontrolltecken.
        2. Binär telemetri tolkad som ASCII (inga 4-bokstavsord, hög andel specialtecken).
        3. Verifiera samtidigt att riktiga e-postmeddelanden släpps igenom!
        """
        # Paket 1: Rysk 5PSCRYPTO med binära kontrolltecken från skarp drift
        pkg1_text = "\u0002\u0000\u0000\u0004  \u0018 ,\b.\u000b\u0010D\u0006\u0018P\u0004 X\thj\u0000  4273152303*\u0001@\u0000\u00005PSCRYPTO 2.1\r\n0 0200 7 kWO TO 0R> | < ] ]3 E ZD3"
        self.assertTrue(is_binary_or_gibberish(pkg1_text))
        frame1 = {
            "station": "SatDump",
            "pkt_name": "Full Message",
            "text": pkg1_text
        }
        self.assertIsNone(parse_satc_frame(frame1, only_messages=True))

        # Paket 2: Binär telemetri tolkad som ASCII från skarp drift
        pkg2_text = "H0 2 l5 &0 N c0 vVb AL 9 E$ @ P'I"
        self.assertTrue(is_binary_or_gibberish(pkg2_text))
        frame2 = {
            "station": "SatDump",
            "pkt_name": "Full Message",
            "text": pkg2_text
        }
        self.assertIsNone(parse_satc_frame(frame2, only_messages=True))

        # Riktigt e-postmeddelande 1 från skarp drift (släpps igenom)
        real_email1 = "NL BURUM LES 12-OCT-2026 14:22:00 123456\r\nSubject: INMS email Inactivity detected for terminal 427315230\r\nPlease verify connection status."
        self.assertFalse(is_binary_or_gibberish(real_email1))
        frame_real1 = {
            "station": "SatDump",
            "pkt_name": "Full Message",
            "text": real_email1
        }
        res_real1 = parse_satc_frame(frame_real1, only_messages=True)
        self.assertIsNotNone(res_real1)
        self.assertIn("Inactivity detected", res_real1['message'])

        # Riktigt e-postmeddelande 2 från skarp drift (släpps igenom)
        real_email2 = "Subject: SAT C TEST ON PHOENIX LES BURUM\r\nTEST MESSAGE FROM SHIP STATION\r\nMSG WELL RCVD OK"
        self.assertFalse(is_binary_or_gibberish(real_email2))
        frame_real2 = {
            "station": "SatDump",
            "pkt_name": "Full Message",
            "text": real_email2
        }
        res_real2 = parse_satc_frame(frame_real2, only_messages=True)
        self.assertIsNotNone(res_real2)
        self.assertIn("SAT C TEST ON PHOENIX", res_real2['message'])

    def test_alert_words_isolated_from_raw_data_and_synthetic_header(self):
        """
        Verifiera att larmordsmatchning ENDAST sker mot den faktiska brödtexten:
        - Ord i Rådata (t.ex. 'SafetyNet', 'MaritimeDistressAlerting') triggar INTE larm om de bara finns i JSON.
        - Ord i det syntetiska huvudet (t.ex. '[Inmarsat STD-C / Textmeddelande] Prioritet: Safety') triggar INTE larm.
        - När ett larmord finns i brödtexten ska det däremot trigga larm.
        """
        # Rensa eventuella kvardröjande larmord från tidigare körningar
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM alert_words WHERE word IN ('SafetyNet', 'MaritimeDistressAlerting', 'TESTUNIKBOTTEN')")
        conn.commit()
        conn.close()

        # Skapa ett meddelande med syntetiskt huvud, harmlös brödtext och rå-JSON med känsliga nycklar
        msg_with_raw = (
            "[Inmarsat SafetyNET / Sjöfartsvarning] Område: NAVAREA I | Prioritet: Safety\n"
            "VÄDERPROGNOS FÖR TESTUNIKBOTTEN: GOD SIKT OCH LÄTT VIND.\n"
            "Rådata: {\"SafetyNet\": true, \"MaritimeDistressAlerting\": true, \"emergency_flag\": 1}"
        )

        # Kontrollera extrahering av brödtext för larmordsmatchning
        isolated_body = extract_body_for_alert_matching(msg_with_raw)
        self.assertEqual(isolated_body.strip(), "VÄDERPROGNOS FÖR TESTUNIKBOTTEN: GOD SIKT OCH LÄTT VIND.")

        # Om användaren har lagt till "SafetyNet" eller "MaritimeDistressAlerting" som larmord,
        # ska det INTE trigga på msg_with_raw eftersom det endast finns i Rådata
        save_alert_word("SafetyNet", "#ff0000")
        save_alert_word("MaritimeDistressAlerting", "#ff0000")

        matches = check_alert_words(msg_with_raw)
        self.assertFalse(matches, "Larmord i Rådata ska inte trigga larm!")

        # Om brödtexten däremot innehåller ett larmord, t.ex. "TESTUNIKBOTTEN":
        save_alert_word("TESTUNIKBOTTEN", "#ff0000")
        matches_body = check_alert_words(msg_with_raw)
        self.assertIsNotNone(matches_body)
        self.assertEqual(matches_body.get('word'), "TESTUNIKBOTTEN")

        # Städa upp
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM alert_words WHERE word IN ('SafetyNet', 'MaritimeDistressAlerting', 'TESTUNIKBOTTEN', 'BOTTENHAVET')")
        conn.commit()
        conn.close()

    def test_satc_mime_header_decoding(self):
        """Verifiera att RFC 2047 MIME-headers automatiskt avkodas till UTF-8."""
        from satc_receiver import decode_mime_headers

        # Rysk Inmarsat-C e-post header i KOI8-R Base64
        # "Полуаршинов" i KOI8-R Base64 är "8M/M1cHS28nOz9c="
        raw_header = "From: =?koi8-r?b?8M/M1cHS28nOz9c=?= <poluarshinov@marsat.ru>"
        decoded = decode_mime_headers(raw_header)
        self.assertIn("Полуаршинов", decoded)
        self.assertNotIn("=?koi8-r", decoded)
        self.assertIn("<poluarshinov@marsat.ru>", decoded)

        # Svensk UTF-8 Q-encoding
        raw_utf8 = "Subject: =?utf-8?Q?V=C3=A4derrapport_f=C3=B6r_Stockholm?="
        decoded_utf8 = decode_mime_headers(raw_utf8)
        self.assertEqual(decoded_utf8, "Subject: Väderrapport för Stockholm")

        # Flerradig e-post med MIME-headers och brödtext
        full_email = "From: =?koi8-r?b?8M/M1cHS28nOz9c=?= <test@marsat.ru>\nSubject: Provmeddelande\nDetta är brödtext"
        decoded_email = decode_mime_headers(full_email)
        self.assertIn("Полуаршинов", decoded_email)
        self.assertIn("Provmeddelande", decoded_email)

    def test_satc_leaflet_minimap_and_hover_pause_in_ui(self):
        """
        Verifiera att index.html och style.css innehåller:
        1. Leaflet CSS och JS-inkludering.
        2. msg-minimap-container och msg-cell-flex has-minimap för inbäddade minikartor.
        3. hoverPausePill och setupHoverPause för paus vid mus-hover.
        4. zoomMinimap och extractUniversalCoordinates funktioner.
        5. data-proto och OpenSeaMap-overlay för sjöfart (SATC).
        """
        base_dir = os.path.dirname(os.path.dirname(__file__))
        index_path = os.path.join(base_dir, 'templates', 'index.html')
        css_path = os.path.join(base_dir, 'static', 'style.css')

        with open(index_path, 'r', encoding='utf-8') as f:
            index_html = f.read()
        with open(css_path, 'r', encoding='utf-8') as f:
            style_css = f.read()

        # 1. Leaflet resurser
        self.assertIn('leaflet.css', index_html)
        self.assertIn('leaflet.js', index_html)

        # 2. Minikarta markup och CSS
        self.assertIn('msg-minimap-container', index_html)
        self.assertIn('msg-row-layout', index_html)
        self.assertIn('msg-main-content', index_html)
        self.assertIn('msg-badges', index_html)
        self.assertIn('metaBarBadges', index_html)
        self.assertIn('.msg-minimap-container', style_css)
        self.assertIn('.msg-row-layout', style_css)
        self.assertIn('.msg-main-content', style_css)

        # 2b. Låsning av pillren längst ner (margin-top: auto) och vertikal flex-kolumn
        self.assertIn('flex-direction: column', style_css)
        self.assertIn('margin-top: auto', style_css)

        # 3. Flödespaus
        self.assertIn('hoverPausePill', index_html)
        self.assertIn('Flödet Pausat', index_html)
        self.assertIn('setupHoverPause', index_html)
        self.assertIn('isHoverPaused', index_html)
        self.assertIn('.hover-pause-pill', style_css)

        # 4. Universell koordinathantering, zoom 6 och stor Kart-modal
        self.assertIn('zoomMinimap', index_html)
        self.assertIn('extractUniversalCoordinates', index_html)
        self.assertIn('data-proto', index_html)
        self.assertIn('openseamap.org', index_html)
        self.assertIn('initialZoom = 6', index_html)
        self.assertIn('mapModal', index_html)
        self.assertIn('openMapModal', index_html)
        self.assertIn('closeMapModal', index_html)
        self.assertIn('largeModalMap', index_html)
        self.assertIn('.map-modal-content', style_css)

    def test_decode_mime_headers(self):
        """Verifiera korrekt avkodning av RFC 2047 MIME-ord (t.ex. koi8-r, utf-8, windows-1251)."""
        raw_koi8r = "From: =?koi8-r?B?58HTyd4g7chSydE=?= <mgasich@marsat.ru>"
        decoded = decode_mime_headers(raw_koi8r)
        self.assertNotIn("=?koi8-r?", decoded)
        self.assertIn("<mgasich@marsat.ru>", decoded)
        raw_qp = "Subject: =?utf-8?Q?Varning_f=C3=B6r_h=C3=A5rd_vind?="
        decoded_qp = decode_mime_headers(raw_qp)
        self.assertIn("Varning för hård vind", decoded_qp)

    def test_csp_allows_leaflet_and_tiles(self):
        """Verifiera att CSP-headern i app.py tillåter unpkg.com, OpenStreetMap/OpenSeaMap och cdn.jsdelivr.net."""
        base_dir = os.path.dirname(os.path.dirname(__file__))
        app_path = os.path.join(base_dir, 'app.py')
        with open(app_path, 'r', encoding='utf-8') as f:
            app_code = f.read()
        self.assertIn("https://unpkg.com", app_code)
        self.assertIn("tile.openstreetmap.org", app_code)
        self.assertIn("tiles.openseamap.org", app_code)
        self.assertIn("https://cdn.jsdelivr.net", app_code)

    def test_statistics_has_escapehtml(self):
        """Verifiera att escapeHtml är definierad i statistics.html för att förhindra ReferenceError."""
        base_dir = os.path.dirname(os.path.dirname(__file__))
        stats_path = os.path.join(base_dir, 'templates', 'statistics.html')
        with open(stats_path, 'r', encoding='utf-8') as f:
            stats_code = f.read()
        self.assertIn("function escapeHtml(", stats_code)

    def test_strict_no_emojis_in_source_code(self):
        """Verifiera att inga emojis förekommer i källkodsfilerna, mallarna eller dokumentationen."""
        base_dir = os.path.dirname(os.path.dirname(__file__))
        check_files = [
            'satc_receiver.py',
            'app.py',
            'database.py',
            'README.md',
            'CHANGELOG.md',
            'WALKTHROUGH.md',
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
