import unittest
import json
from app import app
from database import init_db, save_alert_word, delete_alert_word, get_alert_words, save_message, get_connection

class TestRulesAlertHits(unittest.TestCase):
    def setUp(self):
        init_db()
        self.app = app.test_client()
        self.app.testing = True

    def test_alert_words_with_stats_database(self):
        # Skapa ett unikt alert word
        word = "TESTUNIKLARM"
        save_alert_word(word, "#ef4444", is_active=True)
        
        # Spara ett meddelande idag med detta ord
        save_message("999999", f"Detta är ett viktigt meddelande med {word} idag")
        
        alerts = get_alert_words(include_stats=True)
        target = next((a for a in alerts if a['word'] == word), None)
        self.assertIsNotNone(target)
        self.assertGreaterEqual(target['hits_today'], 1)
        self.assertGreaterEqual(target['hits_total'], 1)
        self.assertGreaterEqual(target['avg_per_day'], 1.0)
        
        # Rensa bort testordet
        delete_alert_word(target['id'])

    def test_api_alerts_returns_hits_stats(self):
        word = "TESTAPILARM"
        save_alert_word(word, "#38bdf8", is_active=True)
        save_message("888888", f"Larm händelse med {word}")

        res = self.app.get('/api/alerts?include_stats=1')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode('utf-8'))
        
        target = next((a for a in data if a.get('word') == word), None)
        self.assertIsNotNone(target)
        self.assertIn('hits_today', target)
        self.assertIn('hits_total', target)
        self.assertIn('avg_per_day', target)
        self.assertGreaterEqual(target['hits_today'], 1)
        self.assertGreaterEqual(target['hits_total'], 1)

        delete_alert_word(target['id'])

    def test_rules_html_contains_new_columns(self):
        res = self.app.get('/rules')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('Hits / Day', html)
        self.assertIn('Total Hits', html)
        self.assertIn('colspan="6"', html)

if __name__ == '__main__':
    unittest.main()
