"""wfo_executor 测试 —— 注入 fake run_walkforward,验证线程 + artifact + DB 状态。"""
import json
import os
import tempfile
import threading
import time

import pytest

from backtest.walkforward import WfoConfig, WfoResult, WfoSummary
from server.db import init_db
from server.jobs import (
    create_wfo_run, get_wfo_run,
)
from server.wfo_executor import execute_wfo_once, submit_wfo_background


@pytest.fixture
def db_conn():
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        db_path = tmp.name
    conn = init_db(db_path)
    yield conn
    conn.close()
    os.unlink(db_path)


@pytest.fixture
def artifact_dir(tmp_path):
    d = tmp_path / 'artifacts'
    d.mkdir()
    return str(d)


def _minimal_config_json():
    return json.dumps({
        'symbol': '000001', 'start': '20200101', 'end': '20210101',
        'cash': 100000.0, 'use_market_filter': False,
        'strategy_id': 'swing_ma_boll',
        'param_grid': {'fast_ma': [10.0, 20.0]},
        'train_days': 120, 'test_days': 60, 'step_days': 60,
    })


def test_execute_wfo_once_writes_artifact_and_marks_completed(db_conn, artifact_dir, monkeypatch):
    """execute_wfo_once:fake 引擎返回 WfoResult → 写 artifact → mark_completed。"""
    from backtest.walkforward import FoldResult

    def fake_run_walkforward(config, run, trading_calendar, on_fold_complete=None):
        return WfoResult(
            config=config,
            folds=(FoldResult(
                fold_index=0, train_start='20200101', train_end='20200601',
                test_start='20200602', test_end='20200801',
                best_params={'fast_ma': 20}, is_sharpe=1.5, is_return_pct=5.0,
                oos_sharpe=0.8, oos_return_pct=3.0, oos_drawdown_pct=1.0,
                oos_trade_count=5,
            ),),
            summary=WfoSummary(
                fold_count=1, failed_folds=0,
                mean_is_sharpe=1.5, mean_oos_sharpe=0.8, efficiency=0.53,
                oos_win_folds=1, param_stability={},
            ),
        )

    monkeypatch.setattr('server.wfo_executor.run_walkforward', fake_run_walkforward)

    row = create_wfo_run(db_conn, _minimal_config_json(), 'swing_ma_boll',
                         '000001', '20200101', '20210101')
    execute_wfo_once(db_conn, row['id'], artifact_dir=artifact_dir)

    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'completed'
    assert fetched['artifact_path']
    assert os.path.exists(fetched['artifact_path'])
    with open(fetched['artifact_path'], encoding='utf-8') as f:
        artifact = json.load(f)
    assert artifact['result_type'] == 'wfo'
    assert len(artifact['folds']) == 1


def test_execute_wfo_once_marks_failed_on_exception(db_conn, artifact_dir, monkeypatch):
    """execute_wfo_once:引擎抛异常 → status=failed,error 字段记录。"""

    def boom(config, run, trading_calendar, on_fold_complete=None):
        raise RuntimeError('simulated')

    monkeypatch.setattr('server.wfo_executor.run_walkforward', boom)

    row = create_wfo_run(db_conn, _minimal_config_json(), 'swing_ma_boll',
                         '000001', '20200101', '20210101')
    execute_wfo_once(db_conn, row['id'], artifact_dir=artifact_dir)

    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'failed'
    assert 'simulated' in fetched['error']
