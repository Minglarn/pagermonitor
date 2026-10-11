import os
import tempfile
import sqlite3
import pytest
from app import app
import database

@pytest.fixture(scope='function')
def client():
    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    app.config['TESTING'] = True
    database.DB_PATH = temp_path
    database.init_db()

    with app.test_client() as client:
        yield client

    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except OSError:
            pass

def test_larm_page_accessible(client):
    """Testa att /larm returnerar 200 OK och har rätt rubriker."""
    response = client.get('/larm')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'LARM' in html
    assert 'alarmsTable' in html

def test_security_headers(client):
    """Testa att säkerhetsheaders returneras."""
    response = client.get('/')
    assert response.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    assert 'Content-Security-Policy' in response.headers

def test_alerts_only_filtering(client):
    """Testa att alerts_only i get_recent_messages och /api/messages enbart returnerar meddelanden med träff."""
    # Spara ett bevakat ord
    database.save_alert_word("BRAND", "#ef4444", True)

    # Spara två meddelanden: ett med larmord, ett utan
    database.save_message("1234567", "LARM: STOR BRAND PÅ STORGATAN")
    database.save_message("7654321", "Testmeddelande om fika i köket")

    # Alla meddelanden
    res_all = client.get('/api/messages')
    data_all = res_all.get_json()
    assert len(data_all) == 2

    # Enbart larm
    res_larm = client.get('/api/messages?alerts_only=1')
    data_larm = res_larm.get_json()
    assert len(data_larm) == 1
    assert "STOR BRAND" in data_larm[0]['message']

def test_basic_auth_enabled_and_disabled(monkeypatch):
    """Testa HTTP Basic Auth när AUTH_PASS är aktiverat."""
    from app import app
    app.config['TESTING'] = True

    # 1. Med lösenord konfigurerat
    monkeypatch.setattr('app.AUTH_USER', 'larmoperatör')
    monkeypatch.setattr('app.AUTH_PASS', 'SuperHemligt123')

    with app.test_client() as c:
        # Utan auth ska ge 401
        res_unauth = c.get('/')
        assert res_unauth.status_code == 401
        assert 'WWW-Authenticate' in res_unauth.headers

        # Med felaktiga inloggningsuppgifter ska ge 401
        res_wrong = c.get('/', headers={'Authorization': 'Basic d3Jvbmc6d3Jvbmc='})
        assert res_wrong.status_code == 401

        # Med rätt inloggningsuppgifter
        import base64
        token = base64.b64encode(b'larmoperat\xc3\xb6r:SuperHemligt123').decode('utf-8')
        res_ok = c.get('/', headers={'Authorization': f'Basic {token}'})
        assert res_ok.status_code == 200

    # 2. Utan lösenord konfigurerat (öppet läge)
    monkeypatch.setattr('app.AUTH_USER', '')
    monkeypatch.setattr('app.AUTH_PASS', '')

    with app.test_client() as c:
        res_open = c.get('/')
        assert res_open.status_code == 200

def test_rules_page_and_sidebar_calver(client):
    """Testa att /rules, /aliases och /alerts returnerar 200 OK och innehåller CalVer i sidomenyn."""
    for path in ['/rules', '/aliases', '/alerts']:
        res = client.get(path)
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert 'Rules &amp; Triggers' in html or 'Rules & Triggers' in html
        assert 'CapCode Aliases' in html
        assert 'Alert Words' in html
        assert 'sidebar-version' in html
        assert 'v2026.10.11' in html

def test_get_all_messages_no_limit(client):
    """Testa att /api/messages utan limit-parameter returnerar alla meddelanden utan 200-gräns."""
    for i in range(250):
        database.save_message("1000000", f"Test message #{i}")

    res = client.get('/api/messages')
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 250

def test_garbage_filter_allows_short_alphanumeric_codes():
    """Testa att korta nätverkskoder som AB, CD, OK inte kastas av skräpfiltret."""
    from sdr_processor import is_garbage_message
    assert is_garbage_message("AB", 50) is False
    assert is_garbage_message("CD", 50) is False
    assert is_garbage_message("OK", 50) is False
    assert is_garbage_message("", 50) is True

def test_garbage_filter_allows_long_system_messages():
    """Testa att långa legitima systemmeddelanden/varningar inte felaktigt klassas som repetitivt brus."""
    from sdr_processor import is_garbage_message, parse_multimon_line
    raw = 'POCSAG1200: Address: 1355350  Function: 3  Alpha:   High Volume Warning  UserId 905442   655 messages in 5 minutes:High message volume detected.<CR><LF><CR><LF>UserId      : 905442<CR><LF>Messages    : 655<CR><LF>Time window : 2026-10-11 20:15   20:20 <CR><LF>UTC hour    : 20:00   20:59<CR><LF>Threshold   : 200 messages per 5-minute window (configured for hour 20)<CR><LF><CR><LF>Please review the traffic manually and block the account if it appears suspicious.<NUL>'
    parsed = parse_multimon_line(raw, 'SE')
    assert parsed is not None
    assert is_garbage_message(parsed['message'], 50) is False
    assert is_garbage_message(parsed['message'], 80) is False


def test_settings_page_renders_with_autosave_and_wide_layout(client):
    """Verifiera att inställningssidan renderas i fullbredd med auto-save och förhandsgranskning."""
    res = client.get('/settings')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'settings-container' in html
    assert 'autoSaveBadge' in html
    assert 'previewTextContent' in html
    assert 'addSdrModal' in html
    assert 'v2026.10.11.6' in html

def test_settings_autosave_api(client):
    """Verifiera att uppdatering av visningsinställningar via POST /api/settings lyckas."""
    payload = {
        'message_font': 'JetBrains Mono',
        'message_font_size': '1.1',
        'garbage_filter': 'true',
        'garbage_filter_sensitivity': '45',
        'auto_prune_enabled': 'true',
        'auto_prune_days': '45'
    }
    res = client.post('/api/settings', json=payload)
    assert res.status_code == 200
    assert res.get_json()['status'] == 'success'

    # Verifiera att inställningarna faktiskt sparats
    get_res = client.get('/api/settings')
    assert get_res.status_code == 200
    saved = get_res.get_json()
    assert saved['message_font'] == 'JetBrains Mono'
    assert saved['message_font_size'] == '1.1'
    assert saved['garbage_filter_sensitivity'] == '45'

