import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.service import BacktestRequest
from server.db import init_db
from server.jobs import create_or_reuse_job, get_job, get_job_result, mark_job_completed, run_key_for_request, delete_job, delete_all_jobs, list_jobs


def test_run_key_changes_with_code_version():
    req = BacktestRequest(symbol='000001', start='20240101', end='20240630')
    a = run_key_for_request(req, code_version='abc123')
    b = run_key_for_request(req, code_version='def456')
    assert a != b


def test_run_key_changes_when_only_strategy_changes():
    req_a = BacktestRequest(symbol='000001', start='20240101', end='20240630', strategy_id='swing_ma_boll')
    req_b = BacktestRequest(symbol='000001', start='20240101', end='20240630', strategy_id='bollinger_reversal')
    assert run_key_for_request(req_a, code_version='abc123') != run_key_for_request(req_b, code_version='abc123')


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


def test_delete_job_removes_job_and_result(tmp_path):
    """Test that deleting a job also deletes its result via CASCADE."""
    db_path = tmp_path / 'jobs.sqlite'
    conn = init_db(str(db_path))

    # Create a job
    req = BacktestRequest(symbol='000001', start='20240101', end='20240630')
    job = create_or_reuse_job(conn, req)
    job_id = job['id']

    # Verify job exists
    assert get_job(conn, job_id) is not None

    # Delete the job
    delete_job(conn, job_id)

    # Verify job is gone
    assert get_job(conn, job_id) is None

    # Verify result is also gone (CASCADE delete)
    assert get_job_result(conn, job_id) is None


def test_delete_job_with_nonexistent_id_does_not_raise(tmp_path):
    """Test that deleting a nonexistent job doesn't raise an error."""
    db_path = tmp_path / 'jobs.sqlite'
    conn = init_db(str(db_path))

    # Should not raise
    delete_job(conn, 99999)


def test_delete_all_jobs_removes_all_jobs(tmp_path):
    """Test that delete_all_jobs removes all jobs and returns count."""
    db_path = tmp_path / 'jobs.sqlite'
    conn = init_db(str(db_path))

    # Create multiple jobs
    for i in range(3):
        req = BacktestRequest(symbol=f'{i:06d}', start='20240101', end='20240630')
        create_or_reuse_job(conn, req)

    # Verify jobs exist
    assert len(list_jobs(conn, limit=100)) == 3

    # Delete all
    count = delete_all_jobs(conn)

    # Verify count and empty list
    assert count == 3
    assert len(list_jobs(conn, limit=100)) == 0
