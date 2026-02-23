import os
import tempfile
import json
import pytest
from app import app
from database import init_db, DB_PATH

@pytest.fixture(scope='function')
def client():
    # Use a temporary database for isolation
    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    # Override DB_PATH in the app module
    app.config['TESTING'] = True
    # Patch the DB_PATH used by database functions
    original_db_path = DB_PATH
    # Monkeypatch the module variable
    import database
    database.DB_PATH = temp_path
    # Reinitialize DB
    init_db()
    with app.test_client() as client:
        yield client
    # Cleanup
    os.remove(temp_path)
    database.DB_PATH = original_db_path

def test_stats_dates(client):
    # Insert a dummy message
    from database import save_message
    save_message('12345', 'Test', alias='')
    resp = client.get('/api/stats/dates')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1

def test_stats_day(client):
    from database import save_message
    save_message('12345', 'DayMsg')
    # Get the date of the inserted message
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    resp = client.get(f'/api/stats/day/{today}')
    assert resp.status_code == 200
    msgs = resp.get_json()
    assert isinstance(msgs, list)
    assert any(m['message'] == 'DayMsg' for m in msgs)

def test_stats_count_per_day(client):
    resp = client.get('/api/stats/count-per-day')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    # Should contain dicts with day and count
    for entry in data:
        assert 'day' in entry and 'count' in entry

def test_stats_count_per_hour(client):
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    resp = client.get(f'/api/stats/count-per-hour/{today}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    for entry in data:
        assert 'hour' in entry and 'count' in entry

def test_stats_alert_hits(client):
    # Ensure at least one alert word exists
    from database import save_alert_word
    save_alert_word('TESTWORD', '#ff0000')
    # Insert a message containing the alert word
    from database import save_message
    save_message('11111', 'This contains TESTWORD')
    resp = client.get('/api/stats/alert-hits')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    # Should have entry for TESTWORD
    assert any(entry['word'] == 'TESTWORD' for entry in data)

def test_stats_freq_hits(client):
    from database import save_message
    save_message('11111', 'Msg 1', frequency='169.8M')
    save_message('22222', 'Msg 2', frequency='170.0M')
    resp = client.get('/api/stats/freq-hits')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert any(entry['frequency'] == '169.8M' for entry in data)
    assert any(entry['frequency'] == '170.0M' for entry in data)
