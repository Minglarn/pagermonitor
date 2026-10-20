import unittest
import json
from libacars_bridge import (
    is_libacars_available,
    decode_acars_apps,
    set_mock_decoder
)
from acars_human_parser import format_libacars_data, parse_human_acars
from aero_receiver import parse_aero_frame, AeroReceiver
from acars_receiver import parse_acars_message, ACARSReceiver

class TestLibacarsBridge(unittest.TestCase):
    def tearDown(self):
        # Återställ mock efter varje test
        set_mock_decoder(None)

    def test_bridge_empty_and_invalid_inputs(self):
        """Verifiera att tomma eller ogiltiga anrop returnerar None utan undantag."""
        self.assertIsNone(decode_acars_apps("", ""))
        self.assertIsNone(decode_acars_apps("H1", ""))
        self.assertIsNone(decode_acars_apps(None, "TEXT"))

    def test_mock_decoder_adsc(self):
        """Verifiera att ADS-C protokollträd tolkas och formateras korrekt av format_libacars_data."""
        mock_tree = {
            "arinc622": {
                "msg_type": "adsc",
                "adsc": {
                    "basic_report": {
                        "lat": 59.3293,
                        "lon": 18.0686,
                        "alt": 37000
                    },
                    "earth_ref": {
                        "temp": -51,
                        "wind_dir": 280,
                        "wind_spd": 65
                    }
                }
            }
        }
        set_mock_decoder(lambda label, text, msg_dir: mock_tree)

        res = decode_acars_apps("H1", "/YQXE2YA.CR1.D-AIGV204993E8E1DAA3600F5B")
        self.assertEqual(res, mock_tree)

        meta = {}
        formatted = format_libacars_data(acars_dict=meta, vdl2_frame=None)
        self.assertEqual(formatted, "")

        meta = {"libacars": res}
        formatted = format_libacars_data(acars_dict=meta)
        self.assertIn("ADS-C Positionsrapport", formatted)
        self.assertIn("Position: 59.3293, 18.0686", formatted)
        self.assertIn("Höjd: 37000 ft", formatted)
        self.assertIn("Vind: 280 deg (65 kt)", formatted)
        self.assertIn("Temperatur: -51 C", formatted)
        # Verifiera koordinatberikning i meta-objektet
        self.assertEqual(meta.get('lat'), 59.3293)
        self.assertEqual(meta.get('lon'), 18.0686)
        self.assertEqual(meta.get('alt_ft'), 37000)

    def test_mock_decoder_cpdlc(self):
        """Verifiera att CPDLC flygledningsmeddelande formateras och tolkas korrekt."""
        mock_tree = {
            "arinc622": {
                "msg_type": "cpdlc",
                "cpdlc": {
                    "atc_uplink_msg": {
                        "text": "CLIMB TO AND MAINTAIN FL390"
                    }
                }
            }
        }
        set_mock_decoder(lambda label, text, msg_dir: mock_tree)

        meta = {"libacars": mock_tree}
        formatted = format_libacars_data(acars_dict=meta)
        self.assertIn("CPDLC Flygledningsmeddelande", formatted)
        self.assertIn("CLIMB TO AND MAINTAIN FL390", formatted)

    def test_satdump_aero_frame_without_libacars(self):
        """
        Kritiskt krav: SatDump skickar inte med libacars-objekt utan bara rå ARINC 622-sträng.
        Verifiera att parse_aero_frame identifierar att libacars saknas, skickar till bryggan,
        lägger in trädet under 'libacars' och extraherar positionen för kartan.
        """
        mock_tree = {
            "arinc622": {
                "msg_type": "adsc",
                "adsc": {
                    "basic_report": {
                        "lat": 64.1234,
                        "lon": -21.9876,
                        "alt": 35000
                    }
                }
            }
        }
        calls = []
        def tracking_decoder(lbl, txt, msg_dir):
            calls.append((lbl, txt))
            return mock_tree

        set_mock_decoder(tracking_decoder)

        raw_satdump_frame = {
            "station": "SatDump",
            "freq": 1545150000,
            "channel": "P-Channel",
            "ges_id": 5,
            "aes_id": "3C6544",
            "acars": {
                "flight": "DLH400",
                "tail": "D-AIGV",
                "label": "CR",
                "msgno": "M01A",
                "message": "/YQXE2YA.CR1.D-AIGV204993E8E1DAA3600F5B"
            }
        }

        parsed = parse_aero_frame(raw_satdump_frame)
        self.assertIsNotNone(parsed)
        # Kontrollera att bryggan anropades med etikett och meddelande
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "CR")
        self.assertIn("204993E8E1DAA3600F5B", calls[0][1])

        # Kontrollera att rådatan inte förorenas av libacars, men att metadata har det
        self.assertNotIn('libacars', raw_satdump_frame['acars'])
        self.assertNotIn('libacars', parsed['metadata']['raw_payload'].get('acars', {}))
        self.assertEqual(parsed['metadata']['libacars'], mock_tree)

        # Kontrollera att koordinater sattes
        self.assertEqual(parsed['lat'], 64.1234)
        self.assertEqual(parsed['lon'], -21.9876)
        self.assertIn("ADS-C Positionsrapport", parsed['message'])

    def test_satdump_aero_frame_already_has_libacars(self):
        """
        Krav 1: Om inkommande paket redan har ett libacars-block (från dumpvdl2 el.dyl.),
        gör ingenting extra (inget dubbelarbete).
        """
        existing_libacars = {
            "arinc622": {
                "adsc": {
                    "basic_report": {
                        "lat": 50.0,
                        "lon": 10.0
                    }
                }
            }
        }
        calls = []
        set_mock_decoder(lambda lbl, txt, md: calls.append(1))

        frame = {
            "acars": {
                "flight": "SAS123",
                "label": "H1",
                "text": "RAW",
                "libacars": existing_libacars
            }
        }

        parsed = parse_aero_frame(frame)
        # Bryggan ska INTE anropas eftersom libacars redan fanns
        self.assertEqual(len(calls), 0)
        self.assertEqual(parsed['metadata']['libacars'], existing_libacars)

    def test_vhf_acars_receiver_with_libacars(self):
        """Verifiera att även acars_receiver (VHF) nyttjar libacars vid behov."""
        mock_tree = {
            "arinc622": {
                "ats": {
                    "text": "REQUEST CLEARANCE PDC"
                }
            }
        }
        set_mock_decoder(lambda lbl, txt, msg_dir: mock_tree)

        frame = {
            "tail": "SE-DSA",
            "flight": "BRA101",
            "label": "B6",
            "text": "/ARINC622/HEXDATA..."
        }

        parsed = parse_acars_message(frame)
        self.assertIsNotNone(parsed)
        self.assertIn('libacars', frame)
        self.assertIn("ATS Meddelande: REQUEST CLEARANCE PDC", parsed['message'])

    def test_status_reports_libacars(self):
        """Verifiera att get_status i mottagarna rapporterar libacars_available."""
        aero_rx = AeroReceiver()
        a_status = aero_rx.get_status()
        self.assertIn('libacars_available', a_status)

        acars_rx = ACARSReceiver()
        ac_status = acars_rx.get_status()
        self.assertIn('libacars_available', ac_status)

    def test_clean_fans_payload_with_routing_header(self):
        """Verifiera att clean_fans_payload extraherar ren hex ur SatDump FANS-1/A-meddelande."""
        from libacars_bridge import clean_fans_payload, decode_acars_apps
        
        # 1. SatDump routing header med .AT1.
        raw = "- #MD/AA PIKCPYA.AT1.00219A221D559DCF0C62C9A738322A004E88\r\n"
        cleaned = clean_fans_payload(raw)
        self.assertEqual(cleaned, "00219A221D559DCF0C62C9A738322A004E88")

        # 2. Meddelande utan header returneras intakt
        plain = "NO ROUTING HEADER HERE"
        self.assertEqual(clean_fans_payload(plain), plain)

        # 3. decode_acars_apps skickar tvättad payload till avkodaren
        received_text = []
        set_mock_decoder(lambda lbl, txt, msg_dir: received_text.append(txt) or {"dummy": True})
        res = decode_acars_apps("H1", raw)
        self.assertIsNotNone(res)
        self.assertEqual(len(received_text), 1)
        self.assertEqual(received_text[0], "00219A221D559DCF0C62C9A738322A004E88")

if __name__ == '__main__':
    unittest.main()

