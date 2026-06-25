"""WFO API 测试:POST/GET 3 个端点。"""
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from server.api import create_app
from server.db import init_db


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / 'test.sqlite')
    artifact_dir = tmp_path / 'artifacts'
    artifact_dir.mkdir()
    app = create_app(db_path=db_path)
    # patch DEFAULT_ARTIFACT_DIR via monkeypatching module attr
    import server.wfo_executor as exec_mod
    orig = exec_mod.DEFAULT_ARTIFACT_DIR
    exec_mod.DEFAULT_ARTIFACT_DIR = str(artifact_dir)
    yield TestClient(app)
    exec_mod.DEFAULT_ARTIFACT_DIR = orig


def _valid_config():
    return {
        'symbol': '000001', 'start': '20200101', 'end': '20210101',
        'cash': 100000.0, 'use_market_filter': False,
        'strategy_id': 'swing_ma_boll',
        'param_grid': {'fast_ma': [10.0, 20.0]},
        'train_days': 120, 'test_days': 60, 'step_days': 60,
    }


def test_post_wfo_rejects_grid_overflow(client, monkeypatch):
    """网格超 MAX_GRID_RUNS → 400, 不建表。"""
    # 简单构造超限:fast_ma 50 取值 × slow_ma 50 取值 = 2500 组合 × 1 fold
    payload = _valid_config()
    payload['param_grid'] = {
        'fast_ma': [float(i) for i in range(50)],
        'slow_ma': [float(i) for i in range(50)],
    }
    # monkeypatch trading_calendar 让 fold_count > 0
    import server.wfo_executor as exec_mod
    monkeypatch.setattr(exec_mod, 'default_trading_calendar',
                        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)])
    resp = client.post('/api/wfo', json=payload)
    assert resp.status_code == 400
    assert '网格过大' in resp.json()['detail']


def test_post_wfo_rejects_unknown_param(client, monkeypatch):
    """参数名不在策略声明 → 400。"""
    payload = _valid_config()
    payload['param_grid'] = {'nonexistent_param': [1.0, 2.0]}
    monkeypatch.setattr(
        'server.wfo_executor.default_trading_calendar',
        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)],
    )
    resp = client.post('/api/wfo', json=payload)
    assert resp.status_code == 400
    assert '未知参数' in resp.json()['detail']


def test_post_wfo_creates_run_and_submits_background(client, monkeypatch):
    """正常 POST → 200 + 返回 id/status/total_folds + 起后台线程。"""
    # 让 run_walkforward 直接返回一个空 fold 的结果,避免真跑回测
    from backtest.walkforward import WfoResult, WfoSummary
    monkeypatch.setattr(
        'server.wfo_executor.default_trading_calendar',
        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)],
    )
    monkeypatch.setattr(
        'server.wfo_executor.run_walkforward',
        lambda config, run, trading_calendar, on_fold_complete=None: WfoResult(
            config=config, folds=(),
            summary=WfoSummary(
                fold_count=0, failed_folds=0, mean_is_sharpe=0.0,
                mean_oos_sharpe=0.0, efficiency=None, oos_win_folds=0,
                param_stability={},
            ),
        ),
    )

    payload = _valid_config()
    resp = client.post('/api/wfo', json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 'id' in body
    assert body['status'] in ('queued', 'running', 'completed')
    assert 'total_folds' in body


def test_get_wfo_status_returns_progress(client, monkeypatch):
    """GET /api/wfo/{id} 返回状态行(含 current_fold/total_folds)。"""
    monkeypatch.setattr(
        'server.wfo_executor.default_trading_calendar',
        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)],
    )
    monkeypatch.setattr(
        'server.wfo_executor.run_walkforward',
        lambda config, run, trading_calendar, on_fold_complete=None: type('R', (), {
            'to_dict': lambda self: {'result_type': 'wfo', 'config': {}, 'folds': [], 'summary': {}},
        })(),
    )

    payload = _valid_config()
    post_resp = client.post('/api/wfo', json=payload)
    wfo_id = post_resp.json()['id']

    # 等待后台线程结束
    import time
    for _ in range(20):
        get_resp = client.get(f'/api/wfo/{wfo_id}')
        if get_resp.json()['status'] in ('completed', 'failed'):
            break
        time.sleep(0.05)

    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body['id'] == wfo_id
    assert 'current_fold' in body
    assert 'total_folds' in body


def test_get_wfo_result_returns_full_payload_with_result_type(client, monkeypatch):
    """GET /api/wfo/{id}/result 完成后返回完整 WfoResult 含 result_type='wfo'。"""
    monkeypatch.setattr(
        'server.wfo_executor.default_trading_calendar',
        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)],
    )
    fake_payload = {
        'result_type': 'wfo',
        'config': _valid_config(),
        'folds': [],
        'summary': {
            'fold_count': 0, 'failed_folds': 0,
            'mean_is_sharpe': 0.0, 'mean_oos_sharpe': 0.0,
            'efficiency': None, 'oos_win_folds': 0,
            'param_stability': {},
        },
    }
    monkeypatch.setattr(
        'server.wfo_executor.run_walkforward',
        lambda config, run, trading_calendar, on_fold_complete=None: type('R', (), {
            'to_dict': lambda self: fake_payload,
        })(),
    )

    payload = _valid_config()
    post_resp = client.post('/api/wfo', json=payload)
    wfo_id = post_resp.json()['id']

    import time
    for _ in range(20):
        get_resp = client.get(f'/api/wfo/{wfo_id}/result')
        if get_resp.status_code == 200:
            break
        time.sleep(0.05)

    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body['result_type'] == 'wfo'
    assert 'folds' in body
    assert 'summary' in body
