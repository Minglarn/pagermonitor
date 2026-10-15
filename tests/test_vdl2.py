import unittest
import base64
import zlib
from vdl2_receiver import (
    parse_vdl2_frame, extract_position_and_telemetry, send_test_vdl2_message,
    humanize_acars_message, decode_miam_base85, reset_partial_acars_cache
)

class TestVDL2Receiver(unittest.TestCase):
    def test_miam_airbus_telemetry_extraction(self):
        miam_raw = 'A350,001998...;PAALT,41001;PALAT,5.875309E+01;PALONG,1.543292E+01;PASAT,-6.347548E+01;PAFOB,8810;PAWS,8.014706E+01;PAFMSAWID,RIRIP  ;PAMN,8.354567E-01;PATHDG,5.247856E+01;PAGWTFQMS,180209;:'
        frame = {
            'vdl2': {
                'freq': 136975000,
                'sig_level': -12.0,
                'noise_level': -48.0,
                'avlc': {
                    'src': {'addr': '461F50'},
                    'acars': {
                        'reg': '.OH-LWI',
                        'flight': 'AY1338',
                        'label': 'MA',
                        'msg_text': 'z!K%^RAW_BASE85_STRING_IGNORED',
                        'miam': {
                            'single_transfer': {
                                'miam_core': {
                                    'data': {
                                        'acars': {
                                            'label': 'H1',
                                            'msg_text': miam_raw
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['address'], 'AY1338 (OH-LWI) [461F50]')
        self.assertEqual(res['alias'], 'Finnair')
        self.assertAlmostEqual(res['lat'], 58.75309, places=4)
        self.assertAlmostEqual(res['lon'], 15.43292, places=4)
        self.assertEqual(res['alt_ft'], 41001)
        self.assertTrue(res['is_miam'])
        self.assertNotIn('RAW_BASE85', res['message'])
        self.assertIn('RIRIP', res['message'])
        self.assertIn('FL410', res['message'])
        # SNR returneras separat som pill-data, inte inuti res['message']
        self.assertEqual(res['snr'], '+36.0 dB')
        self.assertEqual(res['snr_db'], 36.0)
        self.assertNotIn('SNR: +36.0 dB', res['message'])

    def test_ryanair_decimal_coordinates(self):
        frame = {
            'vdl2': {
                'freq': 136875000,
                'avlc': {
                    'src': {'addr': '4CA812'},
                    'acars': {
                        'reg': '.EI-DCL',
                        'flight': 'RYR284',
                        'label': '16',
                        'msg_text': '191331,37012,1946,  74,N 56.955 E 17.322'
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['address'], 'RYR284 (EI-DCL) [4CA812]')
        self.assertEqual(res['alias'], 'Ryanair')
        self.assertAlmostEqual(res['lat'], 56.955, places=3)
        self.assertAlmostEqual(res['lon'], 17.322, places=3)
        self.assertEqual(res['alt_ft'], 37012)
        self.assertIn('FL370', res['message'])

    def test_finnair_dm_coordinates(self):
        frame = {
            'vdl2': {
                'freq': 136975000,
                'sig_level': -15.5,
                'noise_level': -45.5,
                'avlc': {
                    'src': {'addr': '461F50'},
                    'acars': {
                        'reg': '.OH-LWI',
                        'flight': 'AY1338',
                        'label': 'H1',
                        'msg_text': 'POSN58525E018360,FL350,ARN,HEL'
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['address'], 'AY1338 (OH-LWI) [461F50]')
        # N58525 = 58 + 52.5/60 = 58.875
        self.assertAlmostEqual(res['lat'], 58.875, places=3)
        # E018360 = 18 + 36.0/60 = 18.600
        self.assertAlmostEqual(res['lon'], 18.600, places=3)
        self.assertEqual(res['alt_ft'], 35000)
        self.assertEqual(res['snr'], '+30.0 dB')
        self.assertEqual(res['snr_db'], 30.0)
        self.assertNotIn('SNR: +30.0 dB', res['message'])

    def test_humanize_media_advisory_label_sa(self):
        # 0E21955032HS -> E=established, 2=VDL2, 19:55:03 UTC, links: VDL2, HF, Satcom
        text = humanize_acars_message('SA', '0E21955032HS')
        self.assertIn('Länk upprättad på VDL2 kl 19:55:03 UTC', text)
        self.assertIn('VDL2, HF, Satcom', text)

    def test_humanize_atis_request_label_b9(self):
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '45AC41'},
                    'acars': {
                        'reg': '.OY-KBO',
                        'flight': 'SAS1401',
                        'label': 'B9',
                        'msg_text': '/EKCH.TI2/024EKCHA6237'
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['label'], 'B9')
        self.assertIn('ATIS', res['label_desc'])
        self.assertIn('Begär landningsväder (Arrival ATIS) för EKCH (Köpenhamn/Kastrup)', res['message'])
        self.assertIn('/EKCH.TI2/024EKCHA6237', res['message'])
        self.assertEqual(res['dst_airport'], 'EKCH')
        self.assertIn('EKCH', res['station'])
        self.assertIn('Köpenhamn/Kastrup', res['station'])

    def test_norwegian_arrival_atis_destination_badge(self):
        """Verifiera Norwegian SE-RPF (D83195) Arrival ATIS (/EKCH.TI2/024EKCHA6237) uppdaterar dst_airport och station."""
        frame = {
            'vdl2': {
                'freq': 136875000,
                'avlc': {
                    'src': {'addr': '4ACA06', 'status': 'Airborne'},
                    'dst': {'addr': '119AAA'},
                    'acars': {
                        'reg': '.SE-RPF',
                        'flight': 'D83195',
                        'label': 'B9',
                        'msg_text': '/EKCH.TI2/024EKCHA6237'
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['flight'], 'D83195')
        self.assertEqual(res['reg'], 'SE-RPF')
        self.assertEqual(res['dst_airport'], 'EKCH')
        self.assertIn('EKCH', res['station'])
        self.assertIn('Köpenhamn/Kastrup', res['station'])
        self.assertIn('Begär landningsväder (Arrival ATIS) för EKCH (Köpenhamn/Kastrup)', res['message'])

    def test_boeing_fms_prefix(self):
        text = humanize_acars_message('H1', '#M1BPOSN59102E017505,FL320')
        self.assertIn('[Boeing/Honeywell FMS]', text)

    def test_xid_handover_with_destination_airport(self):
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '4A8123'},
                    'xid': {
                        'dst_airport': 'ESSA'
                    }
                }
            }
        }
        # filter_empty=True ska släppa igenom XID med dst_airport
        res = parse_vdl2_frame(frame, filter_empty=True)
        self.assertIsNotNone(res)
        self.assertIn('ESSA', res['message'])
        self.assertIn('Stockholm/Arlanda', res['message'])
        self.assertIn('XID', res['message'])

    def test_filter_links_q0(self):
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '4A8123'},
                    'acars': {
                        'label': 'Q0',
                        'msg_text': 'PING'
                    }
                }
            }
        }
        # filter_links=False -> släpps igenom
        self.assertIsNotNone(parse_vdl2_frame(frame, filter_links=False))
        # filter_links=True -> filtreras bort
        self.assertIsNone(parse_vdl2_frame(frame, filter_links=True))

    def test_cpdlc_cotp_extraction(self):
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '4A8123'},
                    'acars': {'flight': 'SAS404', 'reg': '.SE-ROP'},
                    'x25': {
                        'clnp': {
                            'cotp': {
                                'cpdlc': {
                                    'msg_type': 'uplink',
                                    'elements': [{'description': 'CLIMB TO FL370'}]
                                }
                            }
                        }
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertIn('SAS404', res['address'])
        self.assertIn('CPDLC:', res['message'])
        self.assertIn('CLIMB TO FL370', res['message'])

    def test_filter_empty_packets(self):
        empty_frame = {
            'vdl2': {
                'avlc': {
                    'src': {'addr': '123456'},
                    'dst': {'addr': '654321'}
                }
            }
        }
        self.assertIsNone(parse_vdl2_frame(empty_frame, filter_empty=True))
        res = parse_vdl2_frame(empty_frame, filter_empty=False)
        self.assertIsNotNone(res)
        self.assertIn('Signallänk', res['message'])

    def test_ethiopian_label_83_csv_and_acarshub_metadata(self):
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {
                        'addr': '040127',
                        'type': 'Aircraft',
                        'status': 'Airborne'
                    },
                    'dst': {
                        'addr': '119AAA',
                        'type': 'Ground station'
                    },
                    'acars': {
                        'reg': '.ET-ATK',
                        'flight': 'ET0715',
                        'mode': '2',
                        'label': '83',
                        'msg_num': 'M37',
                        'msg_num_seq': 'A',
                        'msg_text': 'ESSA,HAAB,142029, 58.54,  18.94,22605,305, 166.9, 43000'
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['address'], 'ET0715 (ET-ATK) [040127]')
        self.assertEqual(res['alias'], 'Ethiopian Airlines')
        self.assertEqual(res['flight'], 'ET0715')
        self.assertEqual(res['reg'], 'ET-ATK')
        self.assertEqual(res['icao'], '040127')
        self.assertEqual(res['dst_airport'], 'HAAB')
        self.assertEqual(res['station'], 'HAAB (Addis Abeba/Bole)')
        self.assertEqual(res['ground_status'], 'Airborne')

        self.assertEqual(res['label'], '83')
        self.assertIn('Operativt meddelande', res['label_desc'])
        self.assertAlmostEqual(res['lat'], 58.54, places=2)
        self.assertAlmostEqual(res['lon'], 18.94, places=2)
        self.assertEqual(res['alt_ft'], 22605)
        self.assertEqual(res['telemetry']['speed_kt'], 305.0)
        self.assertEqual(res['telemetry']['heading'], 166.9)
        self.assertEqual(res['telemetry']['fuel_weight'], '43000')

        # Verifiera att själva meddelandet är rent utan pipes (|) och utan inbäddad metadata
        self.assertNotIn('|', res['message'])
        self.assertNotIn('[Reg:', res['message'])
        self.assertIn('Rutt: ESSA (Stockholm/Arlanda) → HAAB (Addis Abeba/Bole)   Tid: 20:29 UTC', res['message'])
        self.assertIn('Höjd: 22605 ft   Fart: 305 kt   Kurs: 166.9 deg   Bränsle: 43000', res['message'])
        self.assertIn('Position: 58.54, 18.94', res['message'])
        self.assertEqual(res['dst_airport'], 'HAAB')
        self.assertEqual(res['station'], 'HAAB (Addis Abeba/Bole)')

    def test_label_83_ana_and_airportsdata(self):
        """Test för All Nippon Airways RJTT och global airportsdata-fallback (t.ex. KLAX)."""
        # 1. All Nippon Airways ESSA -> RJTT
        raw_vdl2_ana = {
            "vdl2": {
                "app": {"name": "dumpvdl2"},
                "t": {"sec": 1729000000, "usec": 0},
                "freq": 136775000,
                "sig_level": 29.5,
                "avlc": {
                    "src": {"addr": "86D244", "type": "Airborne", "status": "Airborne"},
                    "dst": {"addr": "02", "type": "Ground station"},
                    "acars": {
                        "reg": ".JA813A",
                        "flight": "NH0222",
                        "label": "83",
                        "msg_text": "ESSA,RJTT,150847,58.32,18.46,26178,309,178.3,157800"
                    }
                }
            }
        }
        res_ana = parse_vdl2_frame(raw_vdl2_ana)
        self.assertIsNotNone(res_ana)
        self.assertIn('Rutt: ESSA (Stockholm/Arlanda) → RJTT (Tokyo/Haneda)   Tid: 08:47 UTC', res_ana['message'])
        self.assertNotIn('(Avgång/Ankomst)', res_ana['message'])
        self.assertEqual(res_ana['dst_airport'], 'RJTT')
        self.assertEqual(res_ana['station'], 'RJTT (Tokyo/Haneda)')

        # 2. Rutt till flygplats från airportsdata (KLAX Los Angeles)
        raw_vdl2_klax = {
            "vdl2": {
                "app": {"name": "dumpvdl2"},
                "t": {"sec": 1729000000, "usec": 0},
                "freq": 136775000,
                "sig_level": 29.5,
                "avlc": {
                    "src": {"addr": "A1B2C3", "type": "Airborne", "status": "Airborne"},
                    "dst": {"addr": "02", "type": "Ground station"},
                    "acars": {
                        "reg": "N12345",
                        "flight": "UA100",
                        "label": "83",
                        "msg_text": "ESSA,KLAX,150847,58.32,18.46,26178,309,178.3,157800"
                    }
                }
            }
        }
        res_klax = parse_vdl2_frame(raw_vdl2_klax)
        self.assertIsNotNone(res_klax)
        self.assertIn('Rutt: ESSA (Stockholm/Arlanda) → KLAX (Los Angeles)   Tid: 08:47 UTC', res_klax['message'])
        self.assertEqual(res_klax['dst_airport'], 'KLAX')
        self.assertEqual(res_klax['station'], 'KLAX (Los Angeles)')


    def test_send_synthetic_test_message(self):
        res = send_test_vdl2_message()
        self.assertEqual(res['status'], 'success')
        self.assertIn('AY1338', res['address'])

    def test_alert_word_whole_word_matching(self):
        from database import check_alert_words, save_alert_word, delete_alert_word, get_alert_words
        # Lägg till LIGHT som test-larmord
        save_alert_word("LIGHT", "#ff0000")
        save_alert_word("PORT", "#00ff00")
        try:
            # "Flight" ska INTE trigga "LIGHT"
            self.assertIsNone(check_alert_words("Flight D84378 to Arlanda"))
            # "Slight delay" ska INTE trigga "LIGHT"
            self.assertIsNone(check_alert_words("Slight delay in arrival"))
            # "Airport" ska INTE trigga om man har "PORT"
            self.assertIsNone(check_alert_words("Arlanda Airport is open"))
            
            # Rent ord LIGHT ska trigga (case-insensitive)
            res1 = check_alert_words("Red light in cockpit")
            self.assertIsNotNone(res1)
            self.assertEqual(res1['word'], 'LIGHT')

            # Med skiljetecken runt ordet ska trigga
            res2 = check_alert_words("Warning: LIGHT! Check system.")
            self.assertIsNotNone(res2)
        finally:
            # Städa upp
            alerts = get_alert_words()
            for a in alerts:
                if a['word'] in ('LIGHT', 'PORT'):
                    delete_alert_word(a['id'])

    def test_miam_raw_fragment_handling(self):
        """Verifiera att ofullständiga Label: MA Base85-fragment aldrig läcker en rå tecken-vägg till UI."""
        raw_fragment = 'T02!<<,:/l,"i9N0X4!234567890abcdefghijklmnopqrstuvwxyz'
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '461F51'},
                    'acars': {
                        'reg': '.OH-LWD',
                        'flight': 'AY1339',
                        'label': 'MA',
                        'msg_text': raw_fragment
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertTrue(res['is_miam'])
        self.assertEqual(res['bitrate'], 'VDL2-MIAM')
        self.assertEqual(res['flight'], 'AY1339')
        self.assertEqual(res['reg'], 'OH-LWD')
        # Verifiera att rå Base85-vägg INTE finns i meddelandet
        self.assertNotIn('234567890abcdefghijklmnopqrstuvwxyz', res['message'])
        # Verifiera ren och snygg presentationsrad med preview och längd
        self.assertIn('[MIAM Komprimerad Telemetri] Krypterat/fragmenterat Airbus-datapaket', res['message'])
        self.assertIn('(T02!<<,:/l,"i9N0...)', res['message'])

    def test_miam_decode_valid_base85_package(self):
        """Verifiera att decode_miam_base85 packar upp en giltig RFC 1924 Base85 + zlib payload och utvinner telemetri."""
        payload = b'A350;PAALT,38000;PALAT,59.1234;PALONG,18.5678;PASAT,-52;PAFMSAWID,HAPIS;PATHDG,220;:'
        raw_b85 = 'T02!' + base64.b85encode(zlib.compress(payload)).decode('ascii')
        
        # 1. Direkt funktionsanrop
        decomp = decode_miam_base85(raw_b85)
        self.assertEqual(decomp, payload.decode('ascii'))

        # 2. Som ACARS msg_text i parse_vdl2_frame
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '461F51'},
                    'acars': {
                        'reg': '.OH-LWD',
                        'flight': 'AY1339',
                        'label': 'MA',
                        'msg_text': raw_b85
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertTrue(res['is_miam'])
        self.assertEqual(res['bitrate'], 'VDL2-MIAM')
        self.assertAlmostEqual(res['lat'], 59.1234, places=3)
        self.assertAlmostEqual(res['lon'], 18.5678, places=3)
        self.assertEqual(res['alt_ft'], 38000)
        self.assertIn('FL380', res['message'])
        self.assertIn('HAPIS', res['message'])

    def test_fms_progress_and_destination_report(self):
        """Verifiera FMS Progress & Destination Report (Label H1 PRG/DT...) inklusive uppdatering av dst_airport och station."""
        raw_fms = 'PRG/DTEGLL,27L,65,083100,/PR1479,322,380,147,,0,20,,M56,50,,,P0,P0,36090,,1332,3372A88'
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '400D2F'},
                    'acars': {
                        'reg': '.G-TTSI',
                        'flight': 'BA779C',
                        'label': 'H1',
                        'msg_text': raw_fms
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['flight'], 'BA779C')
        self.assertEqual(res['reg'], 'G-TTSI')
        self.assertEqual(res['dst_airport'], 'EGLL')
        self.assertIn('EGLL', res['station'])
        self.assertIn('London/Heathrow', res['station'])
        self.assertIn('[FMS Färdrapport]', res['message'])
        self.assertIn('Dest: EGLL (London/Heathrow) Bana 27L', res['message'])
        self.assertIn('ETA: 08:31 UTC', res['message'])
        self.assertIn('Marschhöjd: FL380', res['message'])
        self.assertIn('Temp: -56°C', res['message'])
        self.assertIn('Landningsbränsle: 6 500 kg', res['message'])
        self.assertIn('Rådata: PRG/DTEGLL', res['message'])

    def test_boeing_dfdau_engine_telemetry(self):
        """Verifiera Boeing ACMS/DFDAU numerisk motortelemetri med N1/N2 varvtal, EGT och trunkerad rådata."""
        raw_telemetry = '07336019 8991 9536 9158 9204 9700  533131 00 7858 8423 8589 8926 2168 4845  02 9295 9080 9030 8921 591  0  0 6481000 013 027 007 027 013 0256400672166766750  58  820022011 9047 9052 9047 905010597 8955  77'
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '6B0463'},
                    'acars': {
                        'reg': '.SE-RNE',
                        'flight': 'BLX123',
                        'label': 'H1',
                        'msg_text': raw_telemetry
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertIn('[Boeing Motortelemetri / DFDAU]', res['message'])
        self.assertIn('N1/N2 Varvtal: 89.2%–95.4%', res['message'])
        self.assertIn('EGT: 591°C', res['message'])
        self.assertIn('(37 mätvärden)', res['message'])
        self.assertIn('Rådata: 07336019 8991 9536', res['message'])
        # Fullständig rådata bevaras nu i meddelandet för kollapsbar visning
        self.assertIn('0256400672166766750', res['message'])

    def test_austrian_aoc_1l_telemetry(self):
        """Verifiera Austrian Airlines (OE-LBS, OS096F) Label 1L AOC intern telemetrirapport."""
        raw_msg = '00027266265P.J7.QYQGJGG,KQJQJG4BQ.KKB,Q1,Q4-K999QJB-G'
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '440182'},
                    'acars': {
                        'reg': '.OE-LBS',
                        'flight': 'OS096F',
                        'label': '1L',
                        'msg_text': raw_msg
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['flight'], 'OS096F')
        self.assertEqual(res['reg'], 'OE-LBS')
        self.assertEqual(res['label'], '1L')
        self.assertIn('Lufthansa Group AOC', res['label_desc'])
        self.assertIn('[AOC Flygbolagsdata]', res['message'])
        self.assertIn('Seq: 000272', res['message'])
        self.assertIn(raw_msg, res['message'])

    def test_amdar_weather_report(self):
        """Verifiera Austrian Airlines (OE-LBS, OS096F) Label H2 AMDAR väder- och positionsrapport."""
        raw_msg = (
            '02E15LOWWESSAN55287E01618406503096M407353048G   '
            'QN56167E01639606573096M402348048G   '
            'QN57053E01702107043097M402341044G   '
            'QN57555E01725607112634M290338022G   '
            'QN58465E01750007181950M147312013G   Q'
        )
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '440182'},
                    'acars': {
                        'reg': '.OE-LBS',
                        'flight': 'OS096F',
                        'label': 'H2',
                        'msg_text': raw_msg
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['flight'], 'OS096F')
        self.assertEqual(res['reg'], 'OE-LBS')
        self.assertEqual(res['label'], 'H2')
        self.assertEqual(res['dst_airport'], 'ESSA')
        self.assertAlmostEqual(res['lat'], 58.775, places=3)
        self.assertNotAlmostEqual(res['lat'], 55.4783, places=3)
        self.assertAlmostEqual(res['lon'], 17.8333, places=3)
        self.assertEqual(res['alt_ft'], 19500)
        self.assertIn('[AMDAR Väderrapport]', res['message'])
        self.assertIn('Wien', res['message'])
        self.assertIn('-14.7°C', res['message'])
        self.assertIn('312° / 13 kt', res['message'])
        self.assertIn('5 mätpunkter', res['message'])

    def test_lot_boeing_fms_weather_log(self):
        """Verifiera LOT Polish Airlines (SP-LYM, LO0453) Label H1 Boeing CSV FMS/väderlogg."""
        raw_msg = (
            "ABS026BA_S      ,B7378MAX ,261015,L04AR ,EPWA,ESSA,0146,BCG27-S200-0011\n"
            "N5611.4,E01728.9,150706,40003,-63.3,341,082,ER,00000,0,\n"
            "N5629.6,E01731.7,150709,40002,-63.3,340,081,ER,00000,0,\n"
            "N5647.8,E01734.5,150712,39997,-63.5,336,079,ER,00000,0,\n"
            "N5706.1,E01737.4,150715,39998,-63.5,334,076,ER,00000,0,\n"
            "N5724.6,E01740.4,150718,40001,-63.8,331,074,ER,00000,0,\n"
            "N5743.3,E01743.5,150721,39998,-63.8,329,073,ER,00000,0,"
        )
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '48AD1D'},
                    'acars': {
                        'reg': '.SP-LYM',
                        'flight': 'LO0453',
                        'label': 'H1',
                        'msg_text': raw_msg
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['flight'], 'LO0453')
        self.assertEqual(res['reg'], 'SP-LYM')
        self.assertEqual(res['dst_airport'], 'ESSA')
        self.assertAlmostEqual(res['lat'], 57.7217, places=3)
        self.assertNotAlmostEqual(res['lat'], 56.19, places=2)
        self.assertAlmostEqual(res['lon'], 17.7250, places=3)
        self.assertEqual(res['alt_ft'], 39998)
        self.assertIn('[FMS Färd- & Väderlogg]', res['message'])
        self.assertIn('B7378MAX', res['message'])
        self.assertIn('EPWA (Warszawa/Chopin)', res['message'])
        self.assertIn('ESSA (Stockholm/Arlanda)', res['message'])
        self.assertIn('-63.8°C', res['message'])
        self.assertIn('329° / 73 kt', res['message'])
        self.assertIn('6 mätpunkter', res['message'])

    def test_lot_boeing_plf_fault_report(self):
        """Verifiera LOT Polish Airlines (SP-LYM, LO0453) Boeing Central Maintenance PLF felkodsrapport."""
        raw_msg = (
            "PLF 1 15OCT26 0724 SP-LYM LOT4AR EPWA/ESSA BCG59-U000-08E7 BCG38-0MFC-0017 L 0609 15OCT26\n"
            "FDE 34531131 I 0623 15OCT26\n"
            "MSG 3455991 A 0609 15OCT26 PO H PL\n"
            "OC 0609 15OCT26 : - -\n"
            "FDE 34530331 A 0609 15OCT26"
        )
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '48AD1D'},
                    'acars': {
                        'reg': '.SP-LYM',
                        'flight': 'LO0453',
                        'label': 'H1',
                        'msg_text': raw_msg
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['flight'], 'LO0453')
        self.assertEqual(res['reg'], 'SP-LYM')
        self.assertEqual(res['dst_airport'], 'ESSA')
        self.assertIn('[Underhålls-/Felrapport (PLF)]', res['message'])
        self.assertIn('Warszawa/Chopin', res['message'])
        self.assertIn('Stockholm/Arlanda', res['message'])
        self.assertIn('Rutt: EPWA (Warszawa/Chopin) → ESSA (Stockholm/Arlanda)', res['message'])
        self.assertIn('Cockpit-varningar (FDE): 2 st', res['message'])
        self.assertIn('ATA 34: Navigation', res['message'])
        self.assertIn('Underhållskoder (MSG): 1 st', res['message'])
        self.assertIn('FDE 34531131', res['message'])

    def test_pegasus_airbus_aids_fdimu_report(self):
        """Verifiera Pegasus Airlines (TC-RBH, PC56HA) Airbus FDIMU / AIDS-rapport under Label: H1."""
        raw_msg = (
            "A321,017705,1,1,TB00000/REP009,85,02,1/CCTC-RBH,OCT15,081323,LTFJ,ESSA,0056"
            "/C0TFC05PGTS40101/C106,01009,4130,59,0011,0,1100,61,X/CE0103,13407,301,578,6647,241,F22TS4"
            "/C22500M34P08/C3FAKC2507       /C42"
        )
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '4BA42A'},
                    'acars': {
                        'reg': '.TC-RBH',
                        'flight': 'PC56HA',
                        'label': 'H1',
                        'msg_text': raw_msg
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['flight'], 'PC56HA')
        self.assertEqual(res['reg'], 'TC-RBH')
        self.assertEqual(res['dst_airport'], 'ESSA')
        self.assertEqual(res['alt'], 13407)
        self.assertEqual(res['alt_ft'], 13407)
        self.assertIn('Istanbul/Sabiha Gökçen', res['message'])
        self.assertIn('Stockholm/Arlanda', res['message'])
        self.assertIn('[Airbus FDIMU/Systemrapport #009]', res['message'])
        self.assertIn('13 407 ft', res['message'])
        self.assertIn('301 kt', res['message'])
        self.assertIn('08:13:23 UTC', res['message'])
        self.assertIn('Rutt: LTFJ (Istanbul/Sabiha Gökçen) → ESSA (Stockholm/Arlanda)', res['message'])

    def test_norwegian_label_80_eta_fob_and_pilot_freetext(self):
        """Verifiera Norwegian (SE-RYC, D84505) Label: 80 med /ETA, /FOB och pilotfritext."""
        raw_msg = (
            "3401 ETA 4505/15 ESSA/EDDB .SE-RYC\n"
            "/ETA 0925/FOB 0428\n"
            "HI BER\n"
            "REQ FUEL 5.6T"
        )
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '4AC999'},
                    'acars': {
                        'reg': '.SE-RYC',
                        'flight': 'D84505',
                        'label': '80',
                        'msg_text': raw_msg
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertEqual(res['dst_airport'], 'EDDB')
        self.assertIn('Berlin/Brandenburg', res['station'])
        self.assertIn('ETA: 09:25 UTC', res['message'])
        self.assertNotIn('45:05', res['message'])
        self.assertIn('Bränsle (FOB): 4 280 kg', res['message'])
        self.assertIn('💬 Pilotmeddelande: "HI BER — REQ FUEL 5.6T"', res['message'])
        self.assertIn('Rådata:', res['message'])
        self.assertIn('HI BER', res['message'])

    def test_acars_multi_block_reassembly(self):
        """Verifiera att ACARS multi-block med more: True filtreras bort tills slutblocket more: False anländer."""
        reset_partial_acars_cache()
        # Delblock 1 av 2: Fler block väntas (more: True, reassembly_in_progress) -> skall filtreras bort (None)
        frame1 = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '48AD12'},
                    'acars': {
                        'reg': 'SP-LYM',
                        'flight': 'LO0454',
                        'label': 'H1',
                        'more': True,
                        'assstat': 'reassembly_in_progress',
                        'msg_text': '-010760 9388 '
                    }
                }
            }
        }
        res1 = parse_vdl2_frame(frame1)
        self.assertIsNone(res1, "Delblock med more=True eller assstat=reassembly_in_progress skall ignoreras")

        # Delblock 2 av 2: Sista blocket (more: False, complete)
        frame2 = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '48AD12'},
                    'acars': {
                        'reg': 'SP-LYM',
                        'flight': 'LO0454',
                        'label': 'H1',
                        'more': False,
                        'assstat': 'complete',
                        'msg_text': '-010760 9388 6780018CE0000000003494300000100007F00100000 0007F0010000000000 9158 9204 9700 533131 00 7858 8423 8589 8926'
                    }
                }
            }
        }
        res2 = parse_vdl2_frame(frame2)
        self.assertIsNotNone(res2, "Slutblocket skall producera ett giltigt sammanslaget meddelande")
        self.assertEqual(res2['flight'], 'LO0454')
        self.assertIn('[Boeing Motortelemetri / DFDAU]', res2['message'])
        self.assertIn('Rådata:', res2['message'])
        self.assertIn('-010760 9388', res2['message'])
        self.assertIn('6780018CE0000000003494300000100007F00100000', res2['message'])

        # Del 1b: Egen sammanslagning när dumpvdl2 inte slagit ihop texten i förväg
        reset_partial_acars_cache()
        f_part1 = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '48AD12'},
                    'acars': {'reg': 'SP-LYM', 'label': 'H1', 'more': True, 'msg_text': 'CHUNK_AAA_'}
                }
            }
        }
        self.assertIsNone(parse_vdl2_frame(f_part1))
        f_part2 = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '48AD12'},
                    'acars': {'reg': 'SP-LYM', 'label': 'H1', 'more': False, 'msg_text': 'CHUNK_BBB_END'}
                }
            }
        }
        res_combined = parse_vdl2_frame(f_part2)
        self.assertIsNotNone(res_combined)
        self.assertIn('CHUNK_AAA_CHUNK_BBB_END', res_combined['message'])

    def test_boeing_dfdau_hex_and_negative_telemetry(self):
        """Verifiera DFDAU-telemetri innehållande minustecken (-010760 9388) och hexadecimala statusord (6780018CE000...)."""
        raw_msg = '-010760 9388 6780018CE0000000003494300000100007F00100000 0007F0010000000000 9158 9204 9700 533131 00 7858 8423 8589 8926'
        frame = {
            'vdl2': {
                'freq': 136975000,
                'avlc': {
                    'src': {'addr': '48AD12'},
                    'acars': {
                        'reg': 'SP-LYM',
                        'flight': 'LO0454',
                        'label': 'H1',
                        'msg_text': raw_msg
                    }
                }
            }
        }
        res = parse_vdl2_frame(frame)
        self.assertIsNotNone(res)
        self.assertIn('[Boeing Motortelemetri / DFDAU]', res['message'])
        self.assertIn('Rådata:', res['message'])
        self.assertIn('-010760 9388', res['message'])
        self.assertIn('6780018CE0000000003494300000100007F00100000', res['message'])

if __name__ == '__main__':
    unittest.main()

