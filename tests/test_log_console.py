import unittest
import json
import logging
from app import app
from log_streamer import setup_log_capture, log_manager

class TestLogConsole(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        log_manager.clear()

    def test_log_capture_and_history(self):
        logger = logging.getLogger("test_module")
        logger.info("Test meddelande info")
        logger.warning("Test meddelande varning")
        logger.error("Test meddelande fel")

        res = self.client.get('/api/logs/history')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertGreaterEqual(len(data['logs']), 3)

        messages = [l['message'] for l in data['logs']]
        self.assertIn("Test meddelande info", messages)
        self.assertIn("Test meddelande varning", messages)
        self.assertIn("Test meddelande fel", messages)

    def test_filter_by_level(self):
        logger = logging.getLogger("filter_test")
        logger.info("Information log")
        logger.error("Critical failure log")

        res_error = self.client.get('/api/logs/history?level=ERROR')
        self.assertEqual(res_error.status_code, 200)
        logs = res_error.get_json()['logs']
        for l in logs:
            self.assertEqual(l['level'], 'ERROR')

    def test_clear_logs(self):
        logger = logging.getLogger("clear_test")
        logger.info("Message to be cleared")

        res_clear = self.client.post('/api/logs/clear')
        self.assertEqual(res_clear.status_code, 200)

        res_history = self.client.get('/api/logs/history')
        self.assertEqual(len(res_history.get_json()['logs']), 0)

    def test_filter_by_decoded(self):
        logger = logging.getLogger("sdr_processor")
        logger.info("[RIKS 1] RAW: POCSAG1200: Address: 1234567")
        logger.info("[RIKS 1] DECODED -> Address: 1234567, Alias: Test Station, Msg: Alarm text")
        logger.info("SDR Heartbeat: [RIKS 1] OK")

        res = self.client.get('/api/logs/history?level=DECODED')
        self.assertEqual(res.status_code, 200)
        logs = res.get_json()['logs']
        self.assertEqual(len(logs), 1)
        self.assertIn("DECODED ->", logs[0]['message'])

if __name__ == '__main__':
    unittest.main()
