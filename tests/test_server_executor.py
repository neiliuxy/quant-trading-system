import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.service import BacktestResult
from server.db import init_db
from server.executor import execute_job_once
from server.jobs import create_or_reuse_job, get_job, get_job_result


class FakeRequest:
    pass


def test_execute_job_once_writes_artifact(tmp_path, monkeypatch):
    conn = init_db(str(tmp_path / 'jobs.sqlite'))
    artifacts_dir = tmp_path / 'results'

    from backtest.service import BacktestRequest
    req = BacktestRequest(symbol='000001', start='20240101', end='20240131')
    job = create_or_reuse_job(conn, req, code_version='abc123')

    def fake_runner(request):
        return BacktestResult(
            symbol=request.symbol,
            start=request.start,
            end=request.end,
            initial_cash=request.cash,
            final_value=101000.0,
            total_return_pct=1.0,
            max_drawdown_pct=0.5,
            trade_count=2,
            win_rate_pct=50.0,
            equity_curve=[{'date': '20240102', 'value': 100000.0, 'cash': 100000.0}],
            trades=[],
            market_scores=[],
            market_score_summary={},
        )

    monkeypatch.setattr('server.executor.run_backtest_service', fake_runner)

    execute_job_once(conn, job['id'], str(artifacts_dir))

    saved = get_job(conn, job['id'])
    result = get_job_result(conn, job['id'])
    assert saved['status'] == 'completed'
    assert result['artifact_path'].endswith(f"{job['id']}.json")
    with open(result['artifact_path'], encoding='utf-8') as f:
        payload = json.load(f)
    assert payload['final_value'] == 101000.0
