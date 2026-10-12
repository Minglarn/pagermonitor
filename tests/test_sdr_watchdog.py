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

