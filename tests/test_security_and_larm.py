import os
import tempfile
import sqlite3
import pytest
from app import app, APP_VERSION
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
    assert 'LARM' in html.upper() or 'ALARM' in html.upper()
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
        assert f'v{APP_VERSION}' in html

def test_get_all_messages_no_limit(client):
    """Testa att /api/messages utan limit-parameter returnerar alla meddelanden utan 200-gräns."""
    initial_count = len(client.get('/api/messages').get_json())
    for i in range(250):
        database.save_message("1000000", f"Test message #{i}")

    res = client.get('/api/messages')
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == initial_count + 250

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
    assert f'v{APP_VERSION}' in html

def test_settings_autosave_api(client):
    """Verifiera att uppdatering av visningsinställningar via POST /api/settings lyckas."""
    payload = {
        'message_font': 'JetBrains Mono',
        'message_font_size': '1.1',
        'garbage_filter': 'true',
        'garbage_filter_sensitivity': '45',
        'duplicate_handling': 'merge',
        'duplicate_window': '180',
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
    assert saved['duplicate_handling'] == 'merge'
    assert saved['duplicate_window'] == '180'

def test_messages_limit_options(client):
    """Verifiera att /api/messages hanterar limit-parametrar korrekt (standard 500, explicit limit, och 'all')."""
    with database.get_connection() as conn:
        conn.execute("DELETE FROM messages")
    for i in range(550):
        database.save_message("1000000", f"Volume test #{i}")

    # Standard (inget limit angivet) -> max 500
    res_default = client.get('/api/messages?ensure_protocols=0')
    assert res_default.status_code == 200
    assert len(res_default.get_json()) == 500

    # Explicit gräns -> 25
    res_custom = client.get('/api/messages?limit=25&ensure_protocols=0')
    assert res_custom.status_code == 200
    assert len(res_custom.get_json()) == 25

    # limit=all -> alla sparade
    res_all = client.get('/api/messages?limit=all&ensure_protocols=0')
    assert res_all.status_code == 200
    assert len(res_all.get_json()) >= 550

def test_copy_button_in_templates(client):
    """Verifiera att kopieringsknapp och skript finns i index, larm och statistics vyerna."""
    for endpoint in ['/', '/larm', '/statistics']:
        res = client.get(endpoint)
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert 'copyMessageText' in html
        assert 'copy-btn' in html

def test_alert_words_table_rendered_in_rules(client):
    """Verifiera att tabellen för befintliga larmord renderas i /rules och /alerts."""
    for path in ['/rules', '/alerts']:
        res = client.get(path)
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert 'alertsTableBody' in html
        assert 'Configured Alert Words' in html or 'Befintliga larmord' in html

def test_alert_word_unicode_case_insensitive_matching(client):
    """Verifiera att larmord med svenska tecken som STÖLD och SKADA matchar i sökningar."""
    database.save_alert_word("STÖLD", "#ef4444", True)
    database.save_alert_word("SKADA", "#ef4444", True)
    database.save_message("1234567", "Larm om stöld i butik")
    database.save_message("1234568", "Trafikolycka med skada på person")

    res = client.get('/api/messages?alerts_only=1')
    assert res.status_code == 200
    messages = res.get_json()
    texts = [m['message'] for m in messages]
    assert any("stöld" in t.lower() for t in texts)
    assert any("skada" in t.lower() for t in texts)

def test_duplicate_handling_hide_in_api(client):
    """Verifiera att /api/messages respekterar duplicate_handling='hide' och kan åsidosättas med include_duplicates=1."""
    database.update_setting('duplicate_handling', 'hide')
    database.save_message("1000001", "Unikt första meddelande", is_duplicate=False)
    database.save_message("1000001", "Dubblett meddelande", is_duplicate=True)

    # Standard ska dölja duplikat när 'hide' är aktivt
    res = client.get('/api/messages')
    assert res.status_code == 200
    messages = res.get_json()
    assert any(m['message'] == "Unikt första meddelande" for m in messages)
    assert not any(m['message'] == "Dubblett meddelande" for m in messages)

    # include_duplicates=1 ska inkludera samtliga
    res_all = client.get('/api/messages?include_duplicates=1')
    assert res_all.status_code == 200
    texts = [m['message'] for m in res_all.get_json()]
    assert "Unikt första meddelande" in texts
    assert "Dubblett meddelande" in texts

    # Återställ inställning
    database.update_setting('duplicate_handling', 'mark')

def test_settings_duplicate_and_theme_styling(client):
    """Verifiera att inställningsvyn har subpanels och form-input på duplikatkontroller."""
    res = client.get('/settings')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'class="settings-subpanel"' in html
    assert 'id="duplicate_handling" class="form-input"' in html
    assert 'id="duplicate_window" class="form-input"' in html

def test_live_pause_and_activity_ribbon_rendered(client):
    """Verifiera att Live-Paus-knapp och Eteraktivitet finns i Dashboard och Larm."""
    res_dash = client.get('/')
    assert res_dash.status_code == 200
    dash_html = res_dash.data.decode('utf-8')
    assert 'id="livePauseBtn"' in dash_html
    assert 'id="pausedNotificationBar"' in dash_html
    assert 'id="activityRibbonPanel"' in dash_html
    assert 'waterfall.js' in dash_html

    res_larm = client.get('/larm')
    assert res_larm.status_code == 200
    larm_html = res_larm.data.decode('utf-8')
    assert 'id="livePauseBtn"' in larm_html
    assert 'id="pausedNotificationBar"' in larm_html

def test_duplicate_merge_and_repeat_count(client):
    """Verifiera att upprepade meddelanden kan slås samman med repeat_count och last_timestamp."""
    # Spara ett grundmeddelande
    msg_id, _ = database.save_message("187249", "PRI-1-Alarm: Reset till Alarm Brandlarm")
    assert msg_id is not None

    # Hämta och verifiera initial repeat_count
    msgs = database.get_recent_messages(limit=10)
    target = next((m for m in msgs if m['id'] == msg_id), None)
    assert target is not None
    assert target.get('repeat_count') == 1

    # Öka repeat count
    new_count = database.increment_message_repeat(msg_id, "2026-10-12T19:35:00")
    assert new_count == 2

    # Hämta igen och kontrollera repeat_count och last_timestamp
    msgs_updated = database.get_recent_messages(limit=10)
    target_updated = next((m for m in msgs_updated if m['id'] == msg_id), None)
    assert target_updated is not None
    assert target_updated.get('repeat_count') == 2
    assert target_updated.get('last_timestamp') == "2026-10-12T19:35:00"

def test_actions_column_narrow_width_styling(client):
    """Verifiera att tabellernas action-kolumner är konfigurerade med smal bredd för vertikal stapling."""
    for path in ['/', '/larm', '/statistics']:
        res = client.get(path)
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert 'col-actions' in html
        assert '38px !important' in html

def test_activity_ribbon_collapsed_and_table_layout_fixed(client):
    """Verifiera att RF Activity startar kollapsad och att dashboard-tabellen har table-layout: fixed."""
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'class="activity-ribbon-panel collapsed"' in html
    assert 'table-layout: fixed !important;' in html
    assert 'overflow-wrap: anywhere' in html

def test_universal_confirm_dialog_and_static_asset(client):
    """Verifiera att confirm.js serveras och att scriptet inkluderas på alla vyer."""
    # Testa att confirm.js serveras
    res_asset = client.get('/static/confirm.js')
    assert res_asset.status_code == 200
    js_content = res_asset.data.decode('utf-8')
    assert 'window.showConfirmDialog' in js_content
    assert 'window.showConfirm' in js_content

    # Testa att confirm.js inkluderas i vyerna
    for path in ['/', '/larm', '/statistics', '/settings']:
        res = client.get(path)
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert 'src="/static/confirm.js' in html

def test_clone_sdr_instance_api(client):
    """Verifiera att kloning av SDR kopierar alla hårdvaru- och avkodningsinställningar."""
    # Skapa ursprunglig mottagare med anpassade värden
    initial_config = {
        'name': 'Primary Pager Station',
        'frequency': '169.8M',
        'gain': '35',
        'device_serial': '10000001',
        'ppm_error': '2',
        'sample_rate': '250000',
        'resample_rate': '22050',
        'enable_dc_removal': 'true',
        'enable_deemp': 'true',
        'enable_high_quality_fir': 'false',
        'atan_math': 'fast',
        'oversampling': '4',
        'multimon_verbosity': '2',
        'multimon_charset': 'SE',
        'multimon_format': 'auto',
        'multimon_input_type': 'raw',
        'protocol': 'POCSAG',
        'enabled': 1
    }
    database.save_sdr_instance(initial_config)
    instances = database.get_sdr_instances()
    source = next(i for i in instances if i['name'] == 'Primary Pager Station')
    source_id = source['id']

    # Klona via API med nytt namn och ny frekvens
    clone_res = client.post(f'/api/sdr/{source_id}/clone', json={
        'name': 'Secondary Backup Station',
        'frequency': '161.4375M'
    })
    assert clone_res.status_code == 200
    res_data = clone_res.get_json()
    assert res_data['status'] == 'success'
    new_id = res_data['id']

    # Verifiera att alla hårdvaruvärden och filterinställningar kopierades exakt
    get_res = client.get(f'/api/sdr/{new_id}')
    assert get_res.status_code == 200
    cloned = get_res.get_json()

    assert cloned['name'] == 'Secondary Backup Station'
    assert cloned['frequency'] == '161.4375M'
    assert cloned['gain'] == '35'
    assert cloned['device_serial'] == '10000001'
    assert cloned['ppm_error'] == '2'
    assert cloned['sample_rate'] == '250000'
    assert cloned['resample_rate'] == '22050'
    assert cloned['enable_dc_removal'] == 'true'
    assert cloned['enable_deemp'] == 'true'
    assert cloned['atan_math'] == 'fast'
    assert cloned['oversampling'] == '4'
    assert cloned['multimon_charset'] == 'SE'
    assert cloned['protocol'] == 'POCSAG'
    assert cloned['enabled'] == 0  # Skapas avaktiverad för att förhindra portkrock

    # Verifiera att Copy-knappen och Copy-modalen finns i settings-HTML
    settings_page = client.get('/settings')
    assert settings_page.status_code == 200
    settings_html = settings_page.data.decode('utf-8')
    assert 'openCopySdrModal' in settings_html
    assert 'id="copySdrModal"' in settings_html


def test_clear_basestation_messages_api(client):
    """Verifiera att /api/messages/basestations raderar basstationsloggar och sparar skyddade meddelanden."""
    # Spara några basstationer och vanliga meddelanden
    database.save_message('RAKEL-240-01', 'Aktiv TETRA Basstation på 427.3M', 'Rakel', 0, 'TETRA-NET', frequency='427.3M')
    database.save_message('12345', 'Brand i byggnad', 'Räddningstjänst', 0, 'POCSAG 1200', frequency='169.8M')
    # Spara en skyddad basstationsrad
    msg_id, _ = database.save_message('RAKEL-240-02', 'Aktiv Basstation på 421.225M', 'Rakel', 0, 'TETRA-NET', frequency='421.225M')
    database.toggle_message_lock(msg_id, True)

    resp = client.delete('/api/messages/basestations')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'success'
    assert data['deleted_count'] >= 1

    # Verifiera att vanliga meddelanden och låsta basstationer finns kvar
    remaining = database.get_recent_messages(limit=10)
    messages_text = [m['message'] for m in remaining]
    assert 'Brand i byggnad' in messages_text
    assert 'Aktiv Basstation på 421.225M' in messages_text
    assert 'Aktiv TETRA Basstation på 427.3M' not in messages_text


def test_tetra_settings_save_and_sdr_instance_fields(client):
    """Verifiera att tetra_scan_mode och tetra_dwell_time kan sparas via /api/settings och i sdr_instances."""
    # Testa globala inställningar
    post_data = {
        'tetra_scan_mode': 'explorer',
        'tetra_dwell_time': '45',
        'tetra_skip_encrypted': 'true'
    }
    resp = client.post('/api/settings', json=post_data)
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'success'

    settings = database.get_settings()
    assert settings.get('tetra_scan_mode') == 'explorer'
    assert settings.get('tetra_dwell_time') == '45'
    assert settings.get('tetra_skip_encrypted') == 'true'

    # Testa att sdr_instances sparar tetra_mode, tetra_dwell_time och tetra_skip_encrypted
    sdr_config = {
        'name': 'TETRA Scan Station',
        'frequency': '420M-430M',
        'protocol': 'TETRA',
        'tetra_mode': 'explorer',
        'tetra_dwell_time': '75',
        'tetra_skip_encrypted': 'true'
    }
    database.save_sdr_instance(sdr_config)
    instances = database.get_sdr_instances()
    tetra_inst = next((i for i in instances if i['name'] == 'TETRA Scan Station'), None)
    assert tetra_inst is not None
    assert tetra_inst.get('tetra_mode') == 'explorer'
    assert tetra_inst.get('tetra_dwell_time') == '75'
    assert tetra_inst.get('tetra_skip_encrypted') == 'true'





