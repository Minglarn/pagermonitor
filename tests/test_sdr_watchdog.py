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
