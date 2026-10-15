import unittest
from acars_human_parser import (
    parse_human_acars, lookup_airline, lookup_ground_station, lookup_label,
    build_acars_metadata_header, rule_label_83_csv_position,
    format_libacars_data
)

class TestAcarsHumanParser(unittest.TestCase):
    def test_airline_lookup(self):
        self.assertEqual(lookup_airline("ET0715"), "Ethiopian Airlines")
        self.assertEqual(lookup_airline("ETH715"), "Ethiopian Airlines")
        self.assertEqual(lookup_airline("SK1401"), "SAS")
        self.assertEqual(lookup_airline("SAS1401"), "SAS Scandinavian Airlines")
        self.assertEqual(lookup_airline("AY8892"), "Finnair")
        self.assertEqual(lookup_airline("DY123"), "Norwegian")
        self.assertEqual(lookup_airline("D8456"), "Norwegian")
        self.assertEqual(lookup_airline("LH800"), "Lufthansa")
        self.assertEqual(lookup_airline("BA777"), "British Airways")
        self.assertEqual(lookup_airline("KL120"), "KLM")
        self.assertEqual(lookup_airline("AF101"), "Air France")
        self.assertEqual(lookup_airline("FR284"), "Ryanair")
        self.assertEqual(lookup_airline("W61234"), "Wizz Air")
        self.assertEqual(lookup_airline("BT301"), "airBaltic")
        self.assertEqual(lookup_airline("QR160"), "Qatar Airways")
        self.assertEqual(lookup_airline("EK157"), "Emirates")
        self.assertEqual(lookup_airline("TK1792"), "Turkish Airlines")
        self.assertEqual(lookup_airline("ZZZ9999"), "")

    def test_ground_station_lookup(self):
        self.assertEqual(lookup_ground_station("119AAA"), "Arlanda Airport (ESSA)")
        self.assertEqual(lookup_ground_station("1153706"), "Arlanda Airport (ESSA)")
        self.assertEqual(lookup_ground_station("999999"), "")

    def test_lookup_label(self):
        self.assertIn("ATIS", lookup_label("B9"))
        self.assertIn("Media Advisory", lookup_label("SA"))
        self.assertIn("FMS", lookup_label("H1"))

    def test_build_acars_metadata_header(self):
        avlc = {
            'src': {'addr': '040127', 'status': 'Airborne'},
            'dst': {'addr': '119AAA'},
            'acars': {
                'reg': '.ET-ATK',
                'flight': 'ET0715',
                'mode': '2',
                'msg_num': 'M37',
                'msg_num_seq': 'A'
            }
        }
        res = build_acars_metadata_header(avlc=avlc)
        expected = "Flight: ET0715 (Ethiopian Airlines)   Reg: ET-ATK   ICAO: 040127   To: Arlanda ESSA   Status: Airborne"
        self.assertEqual(res, expected)

    def test_build_acars_metadata_header_on_ground(self):
        avlc = {
            'src': {'addr': '461F50', 'status': 'On ground'},
            'dst': {'addr': '1153706'},
            'acars': {
                'reg': 'OH-LWI',
                'flight': 'AY1338',
                'mode': '2'
            }
        }
        res = build_acars_metadata_header(avlc=avlc)
        self.assertIn("Status: On Ground", res)
        self.assertIn("To: Arlanda ESSA", res)

    def test_rule_label_83_csv_position(self):
        raw = "ESSA,HAAB,142029, 58.54,  18.94,22605,305, 166.9, 43000"
        res = rule_label_83_csv_position(raw)
        expected = "Rutt: ESSA -> HAAB (Avgång/Ankomst)   Tid: 20:29 UTC\nHöjd: 22605 ft   Fart: 305 kt   Kurs: 166.9 deg   Bränsle: 43000\nPosition: 58.54, 18.94"
        self.assertEqual(res, expected)

    def test_label_83_csv_position_via_parse_human_acars(self):
        raw = "[83: Operativt meddelande / Dispatch (IN)] ESSA,HAAB,142029, 58.54,  18.94,22605,305, 166.9, 43000"
        res = parse_human_acars(raw)
        expected = "[83: Operativt meddelande / Dispatch (IN)] Rutt: ESSA -> HAAB (Avgång/Ankomst)   Tid: 20:29 UTC\nHöjd: 22605 ft   Fart: 305 kt   Kurs: 166.9 deg   Bränsle: 43000\nPosition: 58.54, 18.94"
        self.assertEqual(res, expected)

    def test_pattern_1_finnair_weather_and_position(self):
        raw = "/AY8892/141026/E 17.655/N 59.387/37969/-------/      /- 57/33535/ 88 /46/"
        res = parse_human_acars(raw, label="38")
        expected = "Flight: AY8892\nHöjd: 37969 ft   Temperatur: -57 C   Vind: 335 deg (35 kt)\nPosition: N 59.387, E 17.655"
        self.assertEqual(res, expected)

    def test_pattern_1_with_prefix(self):
        raw = "[38: Väderbegäran / METAR] /AY8892/141026/E 17.655/N 59.387/37969/-------/      /- 57/33535/ 88 /46/"
        res = parse_human_acars(raw)
        expected = "[38: Väderbegäran / METAR] Flight: AY8892\nHöjd: 37969 ft   Temperatur: -57 C   Vind: 335 deg (35 kt)\nPosition: N 59.387, E 17.655"
        self.assertEqual(res, expected)

    def test_pattern_2_fms_posn_route_and_weather(self):
        raw = "POSN59197E017265,N55208E004569,201749,380,N60045E021311,203531,N60157E022414,M58,33488,10132A6 | Lat: 59.3283, Lon: 17.4417"
        res = parse_human_acars(raw, label="H1")
        expected = "Höjd: FL380   Temperatur: -58 C   Vind: 334 deg (88 kt)\nNästa brytpunkt: N55208E004569 (kl 20:17:49 UTC)\nPosition: 59.3283, 17.4417"
        self.assertEqual(res, expected)

    def test_pattern_3_resreq_ack(self):
        raw = "RESREQ/AK,1158AF6"
        res = parse_human_acars(raw, label="H1")
        expected = "Systemkvittens: Resursförfrågan bekräftad (ACK) [CRC: 1158AF6]"
        self.assertEqual(res, expected)

    def test_pattern_4_eta_report(self):
        raw = "V09CA032/ETA-30/2046/"
        res = parse_human_acars(raw, label="83")
        expected = "Ankomststatus: Beräknad ankomst (ETA) kl 20:46 UTC (Status: ETA-30, Kod: V09CA032)"
        self.assertEqual(res, expected)

    def test_pattern_5_mm_telemetry_2_points(self):
        raw = "MM2014241014ACD\n20122316 340 215\n20124316 1282826"
        res = parse_human_acars(raw, label="H1")
        expected = "Telemetrilogg (MM2014241014ACD): 2 mätpunkter mottagna (20:12:23 - 20:12:43 UTC)"
        self.assertEqual(res, expected)

    def test_label_sa_media_advisory(self):
        raw = "0E21955032HS"
        res = parse_human_acars(raw, label="SA")
        self.assertIn("Länk upprättad på VDL2 kl 19:55:03 UTC", res)
        self.assertIn("HF, Satcom", res)

    def test_label_h1_fpn_flight_plan(self):
        raw = "FPN/RI/ESSA/HAAB/FL370/"
        res = parse_human_acars(raw, label="H1")
        self.assertEqual(res, "Färdplan (FPN): ESSA -> HAAB   Höjd: FL370")

    def test_label_h1_icao_fpl(self):
        raw = "(FPL-SAS1401-IS-A320/M-S/C-ESSA1200-N0450F360-EKCH0110)"
        res = parse_human_acars(raw, label="H1")
        self.assertEqual(res, "Färdplan (FPL): SAS1401   Rutt: ESSA -> EKCH")

    def test_label_h1_ini_preparation(self):
        raw = "INI/ESSA/ENGM/1420"
        res = parse_human_acars(raw, label="H1")
        self.assertEqual(res, "Färdförberedelse (INI): ESSA -> ENGM   Tid: 14:20 UTC")

    def test_label_80_oooi_report(self):
        raw = "OUT/ESSA/1435"
        res = parse_human_acars(raw, label="80")
        self.assertEqual(res, "Flygstatus: Pushback från gate (OUT)   Flygplats: ESSA   Tid: 14:35 UTC")

    def test_label_b6_cpdlc(self):
        raw = "/CLIMB TO FL350 AND MAINTAIN"
        res = parse_human_acars(raw, label="B6")
        self.assertEqual(res, "Flygledningsmeddelande (CPDLC): CLIMB TO FL350 AND MAINTAIN")

    def test_label_5u_weather_request(self):
        raw = "REQ/METAR/ESSA"
        res = parse_human_acars(raw, label="5U")
        self.assertIn("ESSA", res)

    def test_label_q0_link_test(self):
        raw = "PING"
        res = parse_human_acars(raw, label="Q0")
        self.assertEqual(res, "ACARS Länktest (Link Test Ping)")

    def test_format_libacars_data_adsc(self):
        acars_obj = {
            'arinc622': {
                'adsc': {
                    'basic_report': {
                        'lat': 59.3283,
                        'lon': 17.4417,
                        'alt': 35000
                    },
                    'earth_ref': {
                        'wind_dir': 270,
                        'wind_spd': 45,
                        'temp': -52
                    }
                }
            }
        }
        res = format_libacars_data(acars_dict=acars_obj)
        self.assertIn("ADS-C Positionsrapport", res)
        self.assertIn("Position: 59.3283, 17.4417", res)
        self.assertIn("Höjd: 35000 ft", res)
        self.assertIn("Vind: 270 deg (45 kt)", res)
        self.assertIn("Temperatur: -52 C", res)

    def test_generic_fallback_telemetry(self):
        raw = "FREE TEXT WITH ROUTE ESSA/ENGM AND ETA 1430 AT FL360"
        res = parse_human_acars(raw)
        self.assertIn("Rutt: ESSA (Stockholm/Arlanda) → ENGM (Oslo/Gardermoen)   ETA: 14:30 UTC   Höjd: FL360", res)
        self.assertIn("FREE TEXT WITH ROUTE", res)

    def test_fallback_unmatched_returns_original(self):
        raw = "[H1: FMS / Färddator-rapport] OKÄND TEXT SOM INTE MATCHAR REGLERNA"
        res = parse_human_acars(raw)
        self.assertEqual(res, raw)

if __name__ == '__main__':
    unittest.main()
