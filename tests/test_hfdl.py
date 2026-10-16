import os
import unittest
from hfdl_receiver import (
    parse_hfdl_frame,
    HFDL_AC_CACHE,
    format_hfdl_freq,
    clean_reg_str,
    lookup_airline,
    cache_hfdl_ac,
    get_cached_hfdl_ac
)

class TestHfdlReceiver(unittest.TestCase):
    def setUp(self):
        HFDL_AC_CACHE.clear()

    def tearDown(self):
        HFDL_AC_CACHE.clear()

    def test_clean_reg_and_freq(self):
        self.assertEqual(clean_reg_str(".SE-DMR"), "SE-DMR")
        self.assertEqual(clean_reg_str("SE-DMR"), "SE-DMR")
        self.assertEqual(clean_reg_str(""), "")

        self.assertEqual(format_hfdl_freq(8942000), "8942 kHz")
        self.assertEqual(format_hfdl_freq(8843.0), "8843 kHz")
        self.assertEqual(format_hfdl_freq(8843.5), "8843.5 kHz")
        self.assertEqual(format_hfdl_freq("8843"), "8843 kHz")

    def test_airline_lookup(self):
        self.assertEqual(lookup_airline("CCA876"), "Air China")
        self.assertEqual(lookup_airline("SAS949"), "SAS Scandinavian Airlines")
        self.assertEqual(lookup_airline("SK0949"), "SAS Scandinavian Airlines")
        self.assertEqual(lookup_airline("THY8EL"), "Turkish Airlines")
        self.assertEqual(lookup_airline("DLH123"), "Lufthansa")
        self.assertEqual(lookup_airline("BAW456"), "British Airways")

    def test_packet_1_performance_data(self):
        """Pakettyp 1: Performance data (hfnpdu.type.id == 209), CCA876, pos, pdu_stats"""
        pkt1 = {
            "hfdl": {
                "t": {"sec": 1729074000, "usec": 123456},
                "freq": 8843000,
                "bit_rate": 300,
                "sig_level": -26.4376,
                "noise_level": -30.5612,
                "lpdu": {
                    "src": {"type": "Aircraft", "id": 12},
                    "dst": {"type": "Ground station", "id": 4, "name": "Shannon, Ireland"},
                    "type": {"id": 193, "name": "Performance data"},
                    "hfnpdu": {
                        "type": {"id": 209, "name": "Performance data"},
                        "flight_id": "CCA876",
                        "flight_leg_num": 1,
                        "pos": {"lat": 52.666154, "lon": 6.621679},
                        "frequency": {"freq": 8843.0},
                        "time": {"hour": 10, "min": 25, "sec": 30},
                        "pdu_stats": {
                            "rx_packets": {"300bps": 12, "600bps": 5, "1200bps": 0, "1800bps": 0},
                            "spdus_rx_ok_cnt": 45,
                            "spdus_missed_cnt": 2
                        },
                        "last_freq_change_cause": {"id": 1, "descr": "Loss of signal"}
                    }
                }
            }
        }

        res = parse_hfdl_frame(pkt1)
        self.assertIsNotNone(res)
        self.assertEqual(res['frequency'], '8843 kHz')
        self.assertEqual(res['bitrate'], 'HFDL-300bps')
        self.assertEqual(res['snr'], '+4.1 dB')
        self.assertEqual(res['flight'], 'CCA876')
        self.assertEqual(res['alias'], 'Air China')
        self.assertAlmostEqual(res['lat'], 52.666154, places=4)
        self.assertAlmostEqual(res['lon'], 6.621679, places=4)
        self.assertIn("Position: 52.6662, 6.6217", res['message'])
        self.assertIn("Aktiv HF-kanal: 8843 kHz", res['message'])
        self.assertIn("Frekvensbyte: Loss of signal", res['message'])
        self.assertIn("300bps: 12", res['message'])
        self.assertIn("Shannon, Ireland", res['message'])

    def test_packet_2_logon_resume_and_freq_data(self):
        """Pakettyp 2: Logon resume + Frequency data, ac_info, SAS949, SE-DMR, hörda markstationer"""
        pkt2 = {
            "hfdl": {
                "t": {"sec": 1729074050, "usec": 0},
                "freq": 8942000,
                "bit_rate": 300,
                "sig_level": -25.0,
                "noise_level": -30.0,
                "lpdu": {
                    "src": {"type": "Aircraft", "id": 42},
                    "dst": {"type": "Ground station", "id": 4, "name": "Shannon, Ireland"},
                    "type": {"id": 79, "name": "Logon resume"},
                    "ac_info": {
                        "icao": "4A91B2",
                        "regnr": "SE-DMR",
                        "typecode": "A21N",
                        "opercode": "SAS-A21N",
                        "manuf": "Airbus",
                        "model": "Airbus A321-253NX",
                        "owner": "SAS Scandinavian Airlines"
                    },
                    "hfnpdu": {
                        "type": {"id": 213, "name": "Frequency data"},
                        "flight_id": "SAS949",
                        "pos": {"lat": 56.272767, "lon": 11.130888},
                        "utc_time": {"hour": 10, "min": 26, "sec": 15},
                        "freq_data": [
                            {
                                "gs": {"id": 4, "name": "Shannon, Ireland"},
                                "heard_on_freqs": [{"freq": 8942.0}, {"freq": 5547.0}],
                                "listening_on_freqs": [{"freq": 8942.0}, {"freq": 5547.0}, {"freq": 11384.0}]
                            },
                            {
                                "gs": {"id": 1, "name": "Reykjavik, Iceland"},
                                "heard_on_freqs": [{"freq": 8843.0}],
                                "listening_on_freqs": [{"freq": 8843.0}]
                            },
                            {
                                "gs": {"id": 6, "name": "Al Muharraq, Bahrain"},
                                "heard_on_freqs": [],
                                "listening_on_freqs": [{"freq": 10084.0}, {"freq": 13315.0}]
                            }
                        ]
                    }
                }
            }
        }

        res = parse_hfdl_frame(pkt2)
        self.assertIsNotNone(res)
        self.assertEqual(res['reg'], 'SE-DMR')
        self.assertEqual(res['icao'], '4A91B2')
        self.assertEqual(res['flight'], 'SAS949')
        self.assertEqual(res['ac_model'], 'Airbus A321-253NX')
        self.assertEqual(res['alias'], 'SAS Scandinavian Airlines')
        self.assertAlmostEqual(res['lat'], 56.272767, places=4)
        self.assertAlmostEqual(res['lon'], 11.130888, places=4)

        # Verifiera att de hörda markstationerna listas snyggt
        self.assertIn("Hörd GS: Shannon, Ireland (8942, 5547 kHz)", res['message'])
        self.assertIn("Hörd GS: Reykjavik, Iceland (8843 kHz)", res['message'])
        self.assertIn("Lyssnar GS: Al Muharraq, Bahrain (2 frekv)", res['message'])

        # Verifiera att ac_info sparades i HFDL_AC_CACHE
        cached = get_cached_hfdl_ac(reg="SE-DMR")
        self.assertIsNotNone(cached)
        self.assertEqual(cached['icao'], '4A91B2')
        self.assertEqual(cached['model'], 'Airbus A321-253NX')
        self.assertEqual(cached['owner'], 'SAS Scandinavian Airlines')

    def test_packet_3_turkish_airlines_frequency_data(self):
        """Pakettyp 3: THY8EL TC-LHA, A359, Frequency data"""
        pkt3 = {
            "hfdl": {
                "t": {"sec": 1729074100, "usec": 0},
                "freq": 8942000,
                "bit_rate": 600,
                "sig_level": -22.0,
                "noise_level": -28.0,
                "lpdu": {
                    "src": {"type": "Aircraft", "id": 55},
                    "dst": {"type": "Ground station", "id": 4, "name": "Shannon, Ireland"},
                    "type": {"id": 80, "name": "Frequency data"},
                    "ac_info": {
                        "icao": "4BAA51",
                        "regnr": "TC-LHA",
                        "typecode": "A359",
                        "opercode": "THY-A359",
                        "manuf": "Airbus",
                        "model": "Airbus A350-941",
                        "owner": "Turkish Airlines"
                    },
                    "hfnpdu": {
                        "type": {"id": 213, "name": "Frequency data"},
                        "flight_id": "THY8EL",
                        "pos": {"lat": 55.0104, "lon": 14.1683},
                        "utc_time": {"hour": 10, "min": 27, "sec": 0},
                        "freq_data": [
                            {
                                "gs": {"id": 4, "name": "Shannon, Ireland"},
                                "heard_on_freqs": [{"freq": 8942.0}],
                                "listening_on_freqs": [{"freq": 8942.0}]
                            },
                            {
                                "gs": {"id": 8, "name": "Agana, Guam"},
                                "heard_on_freqs": [],
                                "listening_on_freqs": [{"freq": 13321.0}]
                            }
                        ]
                    }
                }
            }
        }

        res = parse_hfdl_frame(pkt3)
        self.assertIsNotNone(res)
        self.assertEqual(res['reg'], 'TC-LHA')
        self.assertEqual(res['icao'], '4BAA51')
        self.assertEqual(res['flight'], 'THY8EL')
        self.assertEqual(res['ac_model'], 'Airbus A350-941')
        self.assertEqual(res['alias'], 'Turkish Airlines')
        self.assertAlmostEqual(res['lat'], 55.0104, places=4)
        self.assertAlmostEqual(res['lon'], 14.1683, places=4)
        self.assertIn("Hörd GS: Shannon, Ireland (8942 kHz)", res['message'])
        self.assertIn("Lyssnar GS: Agana, Guam (1 frekv)", res['message'])

    def test_packet_4_acars_q0_and_cache_enrichment(self):
        """
        Pakettyp 4: ACARS Q0 Link test med .SE-DMR.
        Verifiera:
        1. Inledande punkt tas bort: '.SE-DMR' -> 'SE-DMR'.
        2. Om paket 2 körts innan berikas paketet med icao och flygplanstyp från HFDL_AC_CACHE!
        """
        # Först lägger vi in paket 2 (eller förbereder cachen)
        cache_hfdl_ac(
            reg="SE-DMR",
            flight_id="SAS949",
            icao="4A91B2",
            model="Airbus A321-253NX",
            typecode="A21N",
            owner="SAS Scandinavian Airlines",
            pos=(56.2728, 11.1309)
        )

        pkt4 = {
            "hfdl": {
                "t": {"sec": 1729074150, "usec": 0},
                "freq": 8942000,
                "bit_rate": 300,
                "sig_level": -24.0,
                "noise_level": -30.0,
                "lpdu": {
                    "src": {"type": "Aircraft", "id": 42},
                    "dst": {"type": "Ground station", "id": 4, "name": "Shannon, Ireland"},
                    "type": {"id": 3, "name": "Unnumbered ack data"},
                    "hfnpdu": {
                        "type": {"id": 255, "name": "Enveloped data"},
                        "acars": {
                            "err": False,
                            "crc_ok": True,
                            "more": False,
                            "reg": ".SE-DMR",
                            "mode": "2",
                            "label": "Q0",
                            "blk_id": "3",
                            "ack": "!",
                            "flight": "SK0949",
                            "msg_num": "S35",
                            "msg_num_seq": "A",
                            "msg_text": ""
                        }
                    }
                }
            }
        }

        res = parse_hfdl_frame(pkt4)
        self.assertIsNotNone(res)
        self.assertEqual(res['reg'], 'SE-DMR')
        self.assertEqual(res['flight'], 'SK0949')
        # Berikad från cachen:
        self.assertEqual(res['icao'], '4A91B2')
        self.assertEqual(res['ac_model'], 'Airbus A321-253NX')
        self.assertEqual(res['alias'], 'SAS Scandinavian Airlines')
        self.assertEqual(res['metadata']['label'], 'Q0')
        self.assertIn("Label: Q0 (ACARS Länkbekräftelse)", res['message'])
        self.assertIn("Block: 3 (Msg: S35A)", res['message'])

    def test_strict_no_emojis(self):
        """Strikt förbud mot emojis i hfdl_receiver.py och templates/settings.html"""
        with open("hfdl_receiver.py", "r", encoding="utf-8") as f:
            code = f.read()

        import re
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
        self.assertFalse(bool(emoji_pattern.search(code)), "Emoji hittades i hfdl_receiver.py!")

        with open("templates/settings.html", "r", encoding="utf-8") as f:
            tmpl = f.read()
        self.assertFalse(bool(emoji_pattern.search(tmpl)), "Emoji hittades i templates/settings.html!")

if __name__ == '__main__':
    unittest.main()
