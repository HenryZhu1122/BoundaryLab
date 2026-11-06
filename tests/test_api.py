from fastapi.testclient import TestClient
from lab.server import app

client=TestClient(app)


def test_health_has_no_credentials():
    r=client.get('/api/health')
    assert r.status_code==200
    assert r.json()['simulator_ready']
    assert 'api_key' not in r.text.lower()
    assert 'sk-' not in r.text


def test_contract_rejects_reversed_domains():
    r=client.post('/api/studies',json={'contract':{'frequency_min_hz':10000,'frequency_max_hz':500}})
    assert r.status_code==422


def test_invalid_measurement_id_cannot_read_files():
    assert client.get('/api/measurements/not-a-valid-id').status_code==404
    assert client.get('/api/studies/not-a-valid-id').status_code==404


def test_manual_experiment_uses_real_engine():
    r=client.post('/api/experiments',json={'experiment':{'frequency_hz':1000,'amplitude_v':.02}})
    assert r.status_code==200
    d=r.json()
    assert d['engine']=='ngspice-47'
    assert d['passed']
    assert len(d['waveform']['output_v'])==1024


def test_static_assets_are_available():
    for path in ['/','/style.css','/app.js','/mark.svg']:
        assert client.get(path).status_code==200
