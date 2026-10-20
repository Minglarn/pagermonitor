import pytest
import re
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_settings_sidebar_structure(client):
    """Verifiera 2-kolumns layout med vertikal sidomeny och kategorier."""
    res = client.get('/settings')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Sidomeny och containrar
    assert 'class="settings-sidebar"' in html
    assert 'class="settings-main-flow"' in html
    assert 'class="settings-content-body"' in html

    # Kategorier i sidomenyn
    assert 'SYSTEM' in html
    assert 'HÅRDVARA' in html
    assert 'AVKODARE & PROTOKOLL' in html

    # Klickbara flikar i sidomenyn
    assert 'Appearance & Display' in html
    assert 'Database & Storage' in html
    assert 'SDR Receivers' in html
    assert 'VHF Flygdata (VDL2 & ACARS)' in html
    assert 'Inmarsat (SAT-C & AERO)' in html
    assert 'HFDL (Kortvåg)' in html
    assert 'Radiosonder' in html

    # SDR Receivers aktiv som standard
    assert 'switchTab(\'radio\')' in html
    assert 'settings-nav-item active' in html

def test_settings_merged_tabs_content(client):
    """Verifiera sammanslagna flikar VHF Flygdata och Inmarsat samt sektioner."""
    res = client.get('/settings')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # tab-vhf innehåller både VDL2 och ACARS
    assert 'id="tab-vhf"' in html
    assert 'vdl2StatusBadge' in html
    assert 'acarsStatusBadge' in html
    assert 'vdl2_enabled' in html
    assert 'acars_enabled' in html

    # tab-inmarsat innehåller både STD-C och Classic Aero
    assert 'id="tab-inmarsat"' in html
    assert 'satcStatusBadge' in html
    assert 'aeroStatusBadge' in html
    assert 'satc_enabled' in html
    assert 'aero_enabled' in html

    # Hårdvara / SDR lista
    assert 'id="tab-radio"' in html
    assert 'id="sdrList"' in html

    # tab-maintenance innehåller Signal Filtering & Duplicate Handling
    assert 'id="tab-maintenance"' in html
    assert 'garbage_filter' in html
    assert 'duplicate_handling' in html

    # tab-tetra-rds finns under AVKODARE & PROTOKOLL
    assert 'id="tab-tetra-rds"' in html
    assert 'log_tetra_basestations' in html
    assert 'tetra_scan_mode' in html
    assert 'rds_heartbeat_interval' in html
    assert 'clearBasestationLogs' in html

    # tab-display innehåller ENDAST Interface & Typography och Real-Time Preview
    assert 'id="tab-display"' in html
    assert 'message_font' in html
    assert 'preview-card' in html

def test_settings_display_tab_cleaned(client):
    """Verifiera att Appearance & Display rensats från radio-/logginställningar."""
    res = client.get('/settings')
    html = res.data.decode('utf-8')

    # Extrahera endast innehållet i tab-display
    start = html.find('id="tab-display"')
    assert start != -1
    end = html.find('<!-- TAB 3: DATABASE', start)
    if end == -1:
        end = html.find('id="tab-maintenance"', start)
    tab_display_html = html[start:end]

    # Ska finnas i tab-display:
    assert 'Interface & Typography' in tab_display_html
    assert 'Real-time Preview' in tab_display_html

    # Får ABSOLUT INTE finnas i tab-display:
    assert 'garbage_filter' not in tab_display_html
    assert 'duplicate_handling' not in tab_display_html
    assert 'log_tetra_basestations' not in tab_display_html
    assert 'tetra_scan_mode' not in tab_display_html
    assert 'rds_heartbeat' not in tab_display_html

def test_no_double_headers_and_header_bar(client):
    """Verifiera att global dubbel 'Settings'-rubrik är borttagen och ersatt med dynamisk header-bar."""
    res = client.get('/settings')
    html = res.data.decode('utf-8')

    # Ingen gammal global rubrik "Settings - Configure SDR receivers..."
    assert 'Settings - Configure SDR receivers' not in html

    # Dynamisk header-bar med flexbox och autosave-badge
    assert 'class="settings-header-bar"' in html
    assert 'id="settingsTabTitle"' in html
    assert 'id="autoSaveBadge"' in html

def test_no_emojis_in_settings(client):
    """Strikt förbud mot emojis på hela hemsidan."""
    res = client.get('/settings')
    html = res.data.decode('utf-8')
    emoji_pattern = re.compile(r'[\U0001F300-\U0001F9FF\U00002600-\U000026FF\U00002700-\U000027BF]')
    matches = emoji_pattern.findall(html)
    assert len(matches) == 0, f"Emojis funna i settings.html: {matches}"
