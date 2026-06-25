"""server/jobs.py 的 wfo helper 测试。"""
import json
import os
import tempfile

import pytest

from server.db import init_db
from server.jobs import (
    create_wfo_run, get_wfo_run, update_wfo_run_status,
    update_wfo_run_progress, mark_wfo_run_completed,
)


@pytest.fixture
def db_conn():
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        db_path = tmp.name
    conn = init_db(db_path)
    yield conn
    conn.close()
    os.unlink(db_path)


def _sample_config_json():
    return json.dumps({
        'symbol': '000001', 'start': '20200101', 'end': '20210101',
        'cash': 100000.0, 'use_market_filter': False,
        'strategy_id': 'swing_ma_boll',
        'param_grid': {'fast_ma': [10.0, 20.0]},
        'train_days': 120, 'test_days': 60, 'step_days': 60,
    })


def test_create_wfo_run_returns_queued_row(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    assert row['status'] == 'queued'
    assert row['symbol'] == '000001'
    assert row['strategy_id'] == 'swing_ma_boll'
    assert row['run_key']


def test_get_wfo_run_returns_row(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched is not None
    assert fetched['id'] == row['id']


def test_update_wfo_run_status(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    update_wfo_run_status(db_conn, row['id'], 'running')
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'running'
    update_wfo_run_status(db_conn, row['id'], 'failed', 'some error')
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'failed'
    assert fetched['error'] == 'some error'


def test_update_wfo_run_progress(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    update_wfo_run_progress(db_conn, row['id'], 2, 5)
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['current_fold'] == 2
    assert fetched['total_folds'] == 5


def test_mark_wfo_run_completed(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    artifact_path = '/tmp/wfo_test_artifact.json'
    mark_wfo_run_completed(db_conn, row['id'], artifact_path)
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'completed'
    assert fetched['artifact_path'] == artifact_path
