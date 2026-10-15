import unittest
import base64
import zlib
from vdl2_receiver import parse_vdl2_frame, extract_position_and_telemetry, send_test_vdl2_message, humanize_acars_message, decode_miam_base85

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
        self.assertEqual(res['station'], 'Arlanda ESSA')
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
        self.assertIn('Rutt: ESSA -> HAAB (Avgång/Ankomst)   Tid: 20:29 UTC', res['message'])
        self.assertIn('Höjd: 22605 ft   Fart: 305 kt   Kurs: 166.9 deg   Bränsle: 43000', res['message'])
        self.assertIn('Position: 58.54, 18.94', res['message'])

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
        # Kontrollera att den enorma sifferväggen är trunkerad och inte läcker ut till UI
        self.assertNotIn('0256400672166766750', res['message'])

if __name__ == '__main__':
    unittest.main()

