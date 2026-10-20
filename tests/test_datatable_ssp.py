import pytest
import sqlite3
from app import app
import database

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_datatable_endpoint_basic(client):
    """Testa grundläggande svar från /api/alarms/datatable och /api/messages/datatable."""
    res1 = client.get('/api/alarms/datatable?draw=1&start=0&length=10')
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert 'draw' in data1
    assert data1['draw'] == 1
    assert 'recordsTotal' in data1
    assert 'recordsFiltered' in data1
    assert 'data' in data1
    assert isinstance(data1['data'], list)
    assert len(data1['data']) <= 10

    # Testa alias
    res2 = client.get('/api/messages/datatable?draw=2&start=0&length=5')
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2['draw'] == 2
    assert len(data2['data']) <= 5

def test_datatable_pagination(client):
    """Testa paginering med start (OFFSET) och length (LIMIT)."""
    res_p1 = client.get('/api/alarms/datatable?draw=1&start=0&length=5')
    res_p2 = client.get('/api/alarms/datatable?draw=2&start=5&length=5')
    assert res_p1.status_code == 200
    assert res_p2.status_code == 200

    d1 = res_p1.get_json()
    d2 = res_p2.get_json()

    if d1['recordsTotal'] > 5:
        # Säkerställ att raderna på sida 1 och sida 2 inte överlappar
        ids_page1 = [r['id'] for r in d1['data']]
        ids_page2 = [r['id'] for r in d2['data']]
        assert set(ids_page1).isdisjoint(set(ids_page2))

def test_datatable_filter_protocol(client):
    """Testa filtrering på enstaka och multipla protokoll."""
    res_pocsag = client.get('/api/alarms/datatable?filter_protocol=POCSAG')
    assert res_pocsag.status_code == 200
    d_pocsag = res_pocsag.get_json()
    assert d_pocsag['recordsFiltered'] <= d_pocsag['recordsTotal']
    for row in d_pocsag['data']:
        assert row.get('protocol') == 'POCSAG'

    # Multi-protokoll
    res_multi = client.get('/api/alarms/datatable?filter_protocol=POCSAG,VDL2')
    assert res_multi.status_code == 200
    d_multi = res_multi.get_json()
    for row in d_multi['data']:
        assert row.get('protocol') in ('POCSAG', 'VDL2')

def test_datatable_filter_search(client):
    """Testa DataTables globala sökning."""
    res_all = client.get('/api/alarms/datatable?length=1')
    total = res_all.get_json()['recordsTotal']

    # Sök efter en sträng som troligen inte finns
    res_none = client.get('/api/alarms/datatable?search[value]=xyznonexistentstring99999')
    assert res_none.status_code == 200
    assert res_none.get_json()['recordsFiltered'] == 0
    assert len(res_none.get_json()['data']) == 0

def test_datatable_alerts_only(client):
    """Testa alerts_only för larmsidan."""
    res = client.get('/api/alarms/datatable?alerts_only=1')
    assert res.status_code == 200
    d = res.get_json()
    assert d['recordsFiltered'] <= d['recordsTotal']
    for row in d['data']:
        assert row.get('is_alert') is True

def test_datatable_sorting(client):
    """Testa sortering fallande och stigande."""
    res_desc = client.get('/api/alarms/datatable?order[0][column]=0&order[0][dir]=desc&length=10')
    res_asc = client.get('/api/alarms/datatable?order[0][column]=0&order[0][dir]=asc&length=10')

    d_desc = res_desc.get_json()
    d_asc = res_asc.get_json()

    if len(d_desc['data']) >= 2 and len(d_asc['data']) >= 2:
        assert d_desc['data'][0]['id'] > d_desc['data'][-1]['id']
        assert d_asc['data'][0]['id'] < d_asc['data'][-1]['id']

def test_frontend_filter_resets_page_and_notice():
    """Verifiera att filterändringar nollställer paginering till sida 1 och att notis för nya larm hanteras."""
    import os
    base_dir = os.path.dirname(os.path.dirname(__file__))

    for tpl in ['index.html', 'larm.html']:
        path = os.path.join(base_dir, 'templates', tpl)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verifiera notis-elementet för historikläge
        assert 'id="newEventsNotice"' in content, f"Saknar newEventsNotice i {tpl}"
        assert 'jumpToFirstPage()' in content, f"Saknar jumpToFirstPage i {tpl}"
        assert 'showNewEventsNotice' in content, f"Saknar showNewEventsNotice i {tpl}"
        assert 'hideNewEventsNotice' in content, f"Saknar hideNewEventsNotice i {tpl}"
        assert 'refreshMinimaps' in content, f"Saknar refreshMinimaps i {tpl}"

    with open(os.path.join(base_dir, 'templates', 'index.html'), 'r', encoding='utf-8') as f:
        idx_content = f.read()

    assert "dataTable.page('first').draw()" in idx_content
    assert "isMessageMatchingActiveFilters" in idx_content
    assert "dataTable.draw(false)" in idx_content
