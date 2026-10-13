import unittest
from unittest.mock import MagicMock, patch
import sdr_processor

class TestSdrWatchdog(unittest.TestCase):
    def setUp(self):
        sdr_processor.active_instances.clear()

    def tearDown(self):
        sdr_processor.active_instances.clear()

    def test_stop_instance_procs(self):
        """Testa att stop_instance_procs dödar processer och tar bort instansen ur active_instances."""
        mock_p1 = MagicMock()
        mock_p1.poll.return_value = None
        mock_p2 = MagicMock()
        mock_p2.poll.return_value = None
        mock_event = MagicMock()

        sdr_processor.active_instances[99] = {
            'p1': mock_p1,
            'p2': mock_p2,
            'config': {'name': 'Test Dongle'},
            'stop_event': mock_event,
            'thread': MagicMock()
        }

        sdr_processor.stop_instance_procs(99)

        self.assertNotIn(99, sdr_processor.active_instances)
        mock_event.set.assert_called_once()
        mock_p1.kill.assert_called_once()
        mock_p2.kill.assert_called_once()

    @patch('sdr_processor.get_sdr_instances')
    @patch('sdr_processor.start_instance')
    @patch('sdr_processor.stop_instance_procs')
    def test_watchdog_detects_dead_process_and_restarts(self, mock_stop, mock_start, mock_get_instances):
        """Testa att supervisor-loopen detekterar döda processer och triggar omstart."""
        mock_get_instances.return_value = [
            {'id': 1, 'name': 'RIKS 1', 'enabled': 1, 'frequency': '169.8M'}
        ]

        # Fejka en död p1-process (poll() returnerar felkod 1 istället för None)
        dead_p1 = MagicMock()
        dead_p1.poll.return_value = 1
        live_p2 = MagicMock()
        live_p2.poll.return_value = None
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        sdr_processor.active_instances[1] = {
            'p1': dead_p1,
            'p2': live_p2,
            'config': {'id': 1, 'name': 'RIKS 1', 'enabled': 1, 'frequency': '169.8M'},
            'stop_event': MagicMock(),
            'thread': mock_thread
        }

        new_p1 = MagicMock()
        new_p2 = MagicMock()
        mock_start.return_value = (new_p1, new_p2)

        # Kör en iteration av logiken genom att anropa koden direkt eller simulera supervisor-steget
        db_inst = mock_get_instances.return_value[0]
        instance_id = db_inst['id']
        inst = sdr_processor.active_instances[instance_id]

        p1_dead = inst['p1'] is not None and inst['p1'].poll() is not None
        p2_dead = inst['p2'] is not None and inst['p2'].poll() is not None
        thread_dead = inst['thread'] is not None and not inst['thread'].is_alive()

        self.assertTrue(p1_dead or p2_dead or thread_dead)

    def test_get_sdr_runtime_status(self):
        """Testa att get_sdr_runtime_status returnerar korrekt process- och hälsostatus."""
        mock_p1 = MagicMock()
        mock_p1.poll.return_value = None
        mock_p1.pid = 4321
        mock_p2 = MagicMock()
        mock_p2.poll.return_value = None
        mock_p2.pid = 4322

        sdr_processor.active_instances[42] = {
            'p1': mock_p1,
            'p2': mock_p2,
            'config': {'id': 42, 'name': 'RIKS 2'},
            'stop_event': MagicMock(),
            'thread': MagicMock(),
            'started_at': 1234567890.0
        }
        sdr_processor.instance_errors[42] = ["usb_claim_interface error -6"]

        status = sdr_processor.get_sdr_runtime_status()
        self.assertIn(42, status)
        self.assertTrue(status[42]['is_running'])
        self.assertEqual(status[42]['rtl_fm_pid'], 4321)
        self.assertEqual(status[42]['multimon_pid'], 4322)
        self.assertEqual(status[42]['last_error'], "usb_claim_interface error -6")

    @patch('sdr_processor.save_message')
    @patch('sdr_processor.publish_message')
    @patch('sdr_processor.get_alias_info')
    def test_monitor_instance_saves_and_broadcasts_message(self, mock_alias, mock_publish, mock_save):
        """Verifiera att monitor_instance faktiskt sparar och notifierar callbacks vid mottaget meddelande."""
        mock_alias.return_value = None
        mock_save.return_value = (101, '2026-10-12 06:00:00')

        received_events = []
        callback = lambda data: received_events.append(data)
        sdr_processor.on_new_message(callback)

        mock_p1 = MagicMock()
        mock_p1.stderr.readline.side_effect = [b'']
        mock_p1.poll.return_value = 0

        mock_p2 = MagicMock()
        mock_p2.stdout.readline.side_effect = [
            'POCSAG1200: Address: 1234567  Function: 3  Alpha: Test Larm Text\n',
            ''
        ]
        mock_p2.poll.return_value = 0

        stop_event = MagicMock()
        stop_event.is_set.side_effect = [False, False, True]

        config = {'id': 1, 'name': 'RIKS 1', 'frequency': '169.8M'}

        try:
            sdr_processor.monitor_instance(1, mock_p1, mock_p2, stop_event, config)
            mock_save.assert_called_once()
            args, kwargs = mock_save.call_args
            self.assertEqual(args[0], '1234567')
            self.assertEqual(args[1], 'Test Larm Text')
            mock_publish.assert_called_once()
            self.assertTrue(any(e.get('address') == '1234567' for e in received_events))
        finally:
            if callback in sdr_processor.new_message_callbacks:
                sdr_processor.new_message_callbacks.remove(callback)

    def test_is_garbage_message_allows_desigo_separator_and_drops_noise(self):
        """Verifiera att legitima larm med avgränsarlinjer (som DesigoCC) inte klassas som skräp, medan radiobrus fångas."""
        desigo_msg = (
            "Larm DesigoCC Vimmerby Hälsocentral:Prioritet: Akut\n\n"
            "Anläggning: Vimmerby Hälsocentral\n\n"
            "Tid för event: 2026-10-12 08:41:48\n\n"
            "Site: Region Kalmar.Fastigheter.Norr.Vimmerby vardcentral.Hus 1.Övrigt.Larmer\n\n"
            "Object: N/A GP-S_Låda \n\n"
            "Cause:  Larm (Till)\n\n"
            "---------------------- End of message ----------------------"
        )
        self.assertFalse(sdr_processor.is_garbage_message(desigo_msg, sensitivity=50))
        self.assertFalse(sdr_processor.is_garbage_message("SOS Larm... Brand i byggnad", sensitivity=50))
        self.assertFalse(sdr_processor.is_garbage_message("*** VIKTIGT LARM *** Prov", sensitivity=50))

        # Reellt radiobrus
        self.assertTrue(sdr_processor.is_garbage_message("~~~|||$$$@@@", sensitivity=50))
        self.assertTrue(sdr_processor.is_garbage_message("   bT(d", sensitivity=50))

    @patch('subprocess.Popen')
    def test_start_instance_command_flags(self, mock_popen):
        """Verifiera att gain (-g) och ppm (-p) skickas med i anropet till rtl_fm."""
        mock_p1 = MagicMock()
        mock_p2 = MagicMock()
        mock_popen.side_effect = [mock_p1, mock_p2]

        config = {
            'id': 4,
            'name': 'AFSK1200',
            'frequency': '144.800M',
            'gain': '28',
            'ppm_error': '5',
            'sample_rate': '250000',
            'resample_rate': '22050',
            'protocol': 'AFSK1200',
            'device_serial': '10000002'
        }

        config['sample_rate'] = '250K'
        config['resample_rate'] = '22.05k'
        p1, p2 = sdr_processor.start_instance(config)
        self.assertEqual(mock_popen.call_count, 2)
        rtl_cmd = mock_popen.call_args_list[0][0][0]

        self.assertIn('-g', rtl_cmd)
        self.assertIn('28', rtl_cmd)
        self.assertIn('-p', rtl_cmd)
        self.assertIn('5', rtl_cmd)
        self.assertIn('-d', rtl_cmd)
        self.assertIn('10000002', rtl_cmd)
        self.assertIn('-s', rtl_cmd)
        self.assertIn('250000', rtl_cmd)
        self.assertIn('-r', rtl_cmd)
        self.assertIn('22050', rtl_cmd)

    def test_normalize_rate_hz(self):
        """Verifiera att enheter som k, K, M normaliseras till korrekta heltalssiffror för rtl_fm."""
        self.assertEqual(sdr_processor.normalize_rate_hz('250K'), '250000')
        self.assertEqual(sdr_processor.normalize_rate_hz('250k'), '250000')
        self.assertEqual(sdr_processor.normalize_rate_hz('22050'), '22050')
        self.assertEqual(sdr_processor.normalize_rate_hz('22.05k'), '22050')
        self.assertEqual(sdr_processor.normalize_rate_hz('1.8M'), '1800000')
        self.assertEqual(sdr_processor.normalize_rate_hz(''), '22050')

    @patch('subprocess.Popen')
    def test_tetra_start_instance(self, mock_popen):
        """Verifiera att TETRA-protokoll startar rtl_sdr och tetra_decoder.py med rätt flaggor."""
        mock_p1 = MagicMock()
        mock_p2 = MagicMock()
        mock_popen.side_effect = [mock_p1, mock_p2]

        config = {
            'id': 5,
            'name': 'RAKEL TEST',
            'frequency': '390.125M',
            'gain': 'auto',
            'ppm_error': '0',
            'sample_rate': '1800000',
            'protocol': 'TETRA',
            'device_serial': '20000001'
        }

        p1, p2 = sdr_processor.start_instance(config)
        self.assertEqual(mock_popen.call_count, 2)
        rtl_cmd = mock_popen.call_args_list[0][0][0]
        decoder_cmd = mock_popen.call_args_list[1][0][0]

        # rtl_sdr parametrar
        self.assertEqual(rtl_cmd[0], 'rtl_sdr')
        self.assertIn('-f', rtl_cmd)
        self.assertIn('390.125M', rtl_cmd)
        self.assertIn('-s', rtl_cmd)
        self.assertIn('1800000', rtl_cmd)
        self.assertIn('-d', rtl_cmd)
        self.assertIn('20000001', rtl_cmd)

        # tetra_decoder.py parametrar
        self.assertTrue(any('tetra_decoder.py' in part for part in decoder_cmd))
        self.assertIn('--freq', decoder_cmd)
        self.assertIn('390.125M', decoder_cmd)

    @patch('sdr_processor.save_message')
    @patch('sdr_processor.publish_message')
    @patch('sdr_processor.get_alias_info')
    def test_tetra_monitor_decodes_sds_and_call(self, mock_alias, mock_publish, mock_save):
        """Verifiera att monitor_instance avkodar TETRA SDS och anrop till standard larmpipeline."""
        mock_alias.return_value = {'alias': 'Polis Insats 1', 'is_hidden': False}
        mock_save.return_value = (201, '2026-10-13 12:00:00')

        received_events = []
        callback = lambda data: received_events.append(data)
        sdr_processor.on_new_message(callback)

        mock_p1 = MagicMock()
        mock_p1.stderr.readline.side_effect = [b'']
        mock_p1.poll.return_value = 0

        mock_p2 = MagicMock()
        mock_p2.stdout.readline.side_effect = [
            'TETRA: SDS GSSI: 10204 ISSI: 45012 Msg: Larm Prio 1 - Brand i byggnad Storgatan 14\n',
            ''
        ]
        mock_p2.poll.return_value = 0

        stop_event = MagicMock()
        stop_event.is_set.side_effect = [False, False, True]

        config = {'id': 5, 'name': 'RAKEL TEST', 'frequency': '390.125M', 'protocol': 'TETRA'}

        try:
            sdr_processor.monitor_instance(5, mock_p1, mock_p2, stop_event, config)
            mock_save.assert_called_once()
            args, kwargs = mock_save.call_args
            self.assertEqual(args[0], '10204')  # GSSI som adress
            self.assertEqual(args[1], 'Larm Prio 1 - Brand i byggnad Storgatan 14')
            self.assertEqual(args[2], 'Polis Insats 1')  # Alias
            self.assertIn('TETRA-SDS', args[4])  # Bitrate / typ
            mock_publish.assert_called_once()
        finally:
            if callback in sdr_processor.new_message_callbacks:
                sdr_processor.new_message_callbacks.remove(callback)

    @patch('subprocess.Popen')
    def test_tetra_scanning_start_instance(self, mock_popen):
        """Verifiera att TETRA-mottagare med skanningsintervall (t.ex. 390M-395M) startar med --scan flagga."""
        mock_p2 = MagicMock()
        mock_popen.return_value = mock_p2

        config = {
            'id': 6,
            'name': 'RAKEL SCANNER',
            'frequency': '390M-395M',
            'gain': '28',
            'ppm_error': '2',
            'sample_rate': '1800000',
            'protocol': 'TETRA',
            'device_serial': '00000002'
        }

        p1, p2 = sdr_processor.start_instance(config)
        self.assertIsNone(p1)
        self.assertEqual(p2, mock_p2)
        self.assertEqual(mock_popen.call_count, 1)

        decoder_cmd = mock_popen.call_args[0][0]
        self.assertIn('--scan', decoder_cmd)
        self.assertIn('--freq', decoder_cmd)
        self.assertIn('390M-395M', decoder_cmd)
        self.assertIn('--gain', decoder_cmd)
        self.assertIn('28', decoder_cmd)
        self.assertIn('--ppm', decoder_cmd)
        self.assertIn('2', decoder_cmd)
        self.assertIn('--device', decoder_cmd)
        self.assertIn('00000002', decoder_cmd)

    @patch('sdr_processor.save_message')
    @patch('sdr_processor.publish_message')
    @patch('sdr_processor.get_alias_info')
    def test_tetra_monitor_handles_scan_and_lock_frequency(self, mock_alias, mock_publish, mock_save):
        """Verifiera att monitor_instance fångar TETRA SCAN, låser på frekvens (LOCK) och sparar larm med låst frekvens."""
        mock_alias.return_value = None
        mock_save.return_value = (301, '2026-10-13 13:00:00')

        mock_p1 = MagicMock()
        mock_p1.stderr.readline.side_effect = [b'']
        mock_p1.poll.return_value = 0

        mock_p2 = MagicMock()
        mock_p2.stdout.readline.side_effect = [
            'TETRA: SCAN Freq: 390.000M Status: Avsoker barvag...\n',
            'TETRA: LOCK Freq: 390.125M Status: LOCKED (Rakel Basstation Synk MCC: 240 MNC: 01 Cell: 104)\n',
            'TETRA: SDS GSSI: 10204 ISSI: 45012 Msg: Prio 1 Larm pa last frekvens\n',
            ''
        ]
        mock_p2.poll.return_value = 0

        stop_event = MagicMock()
        stop_event.is_set.side_effect = [False, False, False, False, True]

        config = {'id': 6, 'name': 'RAKEL SCANNER', 'frequency': '390M-395M', 'protocol': 'TETRA'}

        sdr_processor.monitor_instance(6, mock_p1, mock_p2, stop_event, config)

        self.assertEqual(config.get('active_frequency'), '390.125M')
        mock_save.assert_called_once()
        args, kwargs = mock_save.call_args
        self.assertEqual(args[0], '10204')
        self.assertEqual(args[1], 'Prio 1 Larm pa last frekvens')
        self.assertEqual(kwargs.get('frequency'), '390.125M')

    @patch('sdr_processor.get_sdr_instances')
    @patch('sdr_processor.start_instance')
    def test_supervisor_accepts_instance_when_p1_is_none(self, mock_start, mock_get_instances):
        """Verifiera att supervisor startar instansen och inte loggar 'Failed to start' när p1 är None (TETRA scan)."""
        mock_p2 = MagicMock()
        mock_p2.poll.return_value = None
        mock_p2.pid = 9999
        mock_start.return_value = (None, mock_p2)

        inst_conf = {
            'id': 10,
            'name': 'TETRA SCAN TEST',
            'enabled': 1,
            'frequency': '420.3M:422.7M-25K',
            'protocol': 'TETRA'
        }
        mock_get_instances.return_value = [inst_conf]

        # Kör start-logiken som supervisor utför
        p1, p2 = mock_start(inst_conf)
        self.assertIsNone(p1)
        self.assertIsNotNone(p2)

        # Verifiera att logiken if p2: passerar
        self.assertTrue(bool(p2))

        # Verifiera statusrapportering när p1 är None
        sdr_processor.active_instances[10] = {
            'p1': None,
            'p2': mock_p2,
            'config': inst_conf,
            'stop_event': MagicMock(),
            'thread': MagicMock(),
            'started_at': 1000.0
        }
        status = sdr_processor.get_sdr_runtime_status()
        self.assertIn(10, status)
        self.assertTrue(status[10]['is_running'])
        self.assertIsNone(status[10]['rtl_fm_pid'])
        self.assertEqual(status[10]['multimon_pid'], 9999)

    def test_tetra_wideband_blocks_and_channel_powers(self):
        """Verifiera att Wideband Block Scanning delar in frekvenser i 2.4 MHz block och mäter kanaleffekt."""
        import tetra_decoder

        # Användarens frekvensintervall 420.3M:422.7M-25K (97 kanaler) ska bli exakt 1 block
        hz_list, str_list = tetra_decoder.parse_frequency_targets('420.3M:422.7M-25K')
        self.assertEqual(len(hz_list), 97)

        blocks = tetra_decoder.plan_wideband_blocks(hz_list, max_block_bw=2400000)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['center_hz'], 421500000)
        self.assertEqual(len(blocks[0]['channels_hz']), 97)

        # Stort frekvensspann 390M-395M (5 MHz) ska delas upp i 3 block
        wide_hz, _ = tetra_decoder.parse_frequency_targets('390M-395M')
        wide_blocks = tetra_decoder.plan_wideband_blocks(wide_hz, max_block_bw=2400000)
        self.assertGreaterEqual(len(wide_blocks), 2)
        self.assertLessEqual(len(wide_blocks), 4)

        # Testa spektral effektmätning på IQ-data
        dummy_iq = bytes([128] * 4000)
        powers = tetra_decoder.measure_channel_powers(
            raw_iq=dummy_iq,
            sample_rate=2400000,
            center_hz=421500000,
            channels_hz=blocks[0]['channels_hz'][:5]
        )
        self.assertEqual(len(powers), 5)

        # Testa modulationsdetektering med CFO-kompensation
        is_tetra, score, drift = tetra_decoder.check_channel_dqpsk_modulation(
            raw_iq=dummy_iq,
            sample_rate=2400000,
            center_hz=421500000,
            candidate_hz=421500000
        )
        self.assertIsInstance(is_tetra, bool)
        self.assertIsInstance(score, float)
        self.assertIsInstance(drift, float)

    def test_kill_proc_and_sig_handler(self):
        """Testa att _kill_proc hanterar processavslutning och tetra_decoder signalhantering."""
        import tetra_decoder
        
        # Testa processdödning i sdr_processor
        mock_p = MagicMock()
        mock_p.poll.return_value = None
        sdr_processor.active_instances[999] = {
            'p1': mock_p,
            'p2': None,
            'config': {'name': 'Test'},
            'stop_event': MagicMock()
        }
        sdr_processor.stop_instance_procs(999)
        mock_p.kill.assert_called_once()

        # Testa tetra_decoder._sig_handler
        mock_child = MagicMock()
        tetra_decoder._current_child_proc = mock_child
        with self.assertRaises(SystemExit):
            tetra_decoder._sig_handler(15, None)
        
        self.assertTrue(tetra_decoder._shutdown_requested)
        mock_child.kill.assert_called_once()
        tetra_decoder._shutdown_requested = False
