import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.service import BacktestRequest
from server.db import init_db
from server.jobs import create_or_reuse_job, get_job, mark_job_completed, run_key_for_request


def test_run_key_changes_with_code_version():
    req = BacktestRequest(symbol='000001', start='20240101', end='20240630')
    a = run_key_for_request(req, code_version='abc123')
    b = run_key_for_request(req, code_version='def456')
    assert a != b


def test_create_and_reuse_completed_job(tmp_path):
    db_path = tmp_path / 'jobs.sqlite'
    conn = init_db(str(db_path))
    req = BacktestRequest(symbol='000001', start='20240101', end='20240630')

    first = create_or_reuse_job(conn, req, code_version='abc123')
    mark_job_completed(conn, first['id'], {
        'final_value': 101000.0,
        'total_return_pct': 1.0,
        'max_drawdown_pct': 0.5,
        'trade_count': 2,
        'win_rate_pct': 50.0,
    }, artifact_path='data/results/test.json')
    second = create_or_reuse_job(conn, req, code_version='abc123')

    assert second['id'] == first['id']
    assert second['cache_hit'] is True
    assert get_job(conn, first['id'])['status'] == 'completed'
