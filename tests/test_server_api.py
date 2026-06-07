import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from server.api import create_app


def test_create_job_and_list_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr('server.api.submit_background', lambda conn, job_id: None)
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)

    response = client.post('/api/jobs', json={
        'symbol': '000001',
        'start': '20240101',
        'end': '20240630',
        'cash': 100000,
        'use_market_filter': False,
        'risk_percent': 0.95,
        'fast_ma': 10,
        'slow_ma': 20,
    })

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'queued'
    assert body['symbol'] == '000001'

    list_response = client.get('/api/jobs')
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_missing_result_returns_404(tmp_path):
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)
    response = client.get('/api/jobs/999/result')
    assert response.status_code == 404


def test_strategies_endpoint_lists_registered_strategies(tmp_path):
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)
    response = client.get('/api/strategies')
    assert response.status_code == 200
    body = response.json()
    assert [item['id'] for item in body] == [
        'b1_strategy',
        'swing_ma_boll',
        'bollinger_reversal',
        'citic_wave',
        'sector_rotation',
    ]


def test_create_job_persists_strategy_fields(tmp_path, monkeypatch):
    monkeypatch.setattr('server.api.submit_background', lambda conn, job_id: None)
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)
    response = client.post('/api/jobs', json={
        'symbol': '000001',
        'start': '20240101',
        'end': '20240630',
        'cash': 100000,
        'use_market_filter': False,
        'risk_percent': 0.95,
        'strategy_id': 'bollinger_reversal',
        'strategy_params': {'boll_period': 20, 'boll_devfactor': 2.0},
    })
    assert response.status_code == 200
    body = response.json()
    assert body['strategy_id'] == 'bollinger_reversal'
    assert json.loads(body['strategy_params_json']) == {'boll_period': 20, 'boll_devfactor': 2.0}


def test_compare_market_filter_creates_counterpart_job(tmp_path, monkeypatch):
    monkeypatch.setattr('server.api.submit_background', lambda conn, job_id: None)
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)

    response = client.post('/api/jobs', json={
        'symbol': '000001',
        'start': '20240101',
        'end': '20240630',
        'cash': 100000,
        'use_market_filter': True,
        'risk_percent': 0.95,
        'fast_ma': 10,
        'slow_ma': 20,
    })
    source = response.json()

    compare_response = client.post(f"/api/jobs/{source['id']}/compare-market-filter")

    assert compare_response.status_code == 200
    body = compare_response.json()
    assert body['source_job_id'] == source['id']
    assert body['comparison_job']['use_market_filter'] is False


def test_delete_job_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr('server.api.submit_background', lambda conn, job_id: None)
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)

    response = client.post('/api/jobs', json={
        'symbol': '000001',
        'start': '20240101',
        'end': '20240630',
        'cash': 100000,
        'use_market_filter': False,
        'risk_percent': 0.95,
        'fast_ma': 10,
        'slow_ma': 20,
    })
    job_id = response.json()['id']

    delete_response = client.delete(f'/api/jobs/{job_id}')
    assert delete_response.status_code == 200
    assert delete_response.json() == {'deleted': True}

    get_response = client.get(f'/api/jobs/{job_id}')
    assert get_response.status_code == 404


def test_delete_job_endpoint_nonexistent_returns_404(tmp_path):
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)

    delete_response = client.delete('/api/jobs/999')
    assert delete_response.status_code == 404


def test_delete_all_jobs_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr('server.api.submit_background', lambda conn, job_id: None)
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)

    client.post('/api/jobs', json={
        'symbol': '000001',
        'start': '20240101',
        'end': '20240630',
        'cash': 100000,
        'use_market_filter': False,
        'risk_percent': 0.95,
        'fast_ma': 10,
        'slow_ma': 20,
    })
    client.post('/api/jobs', json={
        'symbol': '000002',
        'start': '20240101',
        'end': '20240630',
        'cash': 100000,
        'use_market_filter': False,
        'risk_percent': 0.95,
        'fast_ma': 10,
        'slow_ma': 20,
    })

    list_response = client.get('/api/jobs')
    assert len(list_response.json()) == 2

    delete_response = client.delete('/api/jobs')
    assert delete_response.status_code == 200
    assert delete_response.json() == {'deleted_count': 2}

    list_response = client.get('/api/jobs')
    assert len(list_response.json()) == 0
