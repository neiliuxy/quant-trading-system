import hashlib
import json
import subprocess
from dataclasses import asdict
from typing import Any

from backtest.service import BacktestRequest
from market.market_analyzer import MarketConfig


def current_code_version() -> str:
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return 'unknown'


def run_key_for_request(request: BacktestRequest, code_version: str | None = None) -> str:
    req = request.normalized()
    payload = {
        'request': asdict(req),
        'market_config_hash': MarketConfig().hash(),
        'code_version': code_version or current_code_version(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _row_to_dict(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def create_or_reuse_job(conn, request: BacktestRequest, code_version: str | None = None, force: bool = False) -> dict[str, Any]:
    req = request.normalized()
    version = code_version or current_code_version()
    run_key = run_key_for_request(req, version)

    if not force:
        existing = conn.execute(
            "SELECT * FROM jobs WHERE run_key = ? AND status = 'completed' ORDER BY id DESC LIMIT 1",
            (run_key,),
        ).fetchone()
        if existing:
            row = dict(existing)
            row['cache_hit'] = True
            return row

    cur = conn.execute(
        """
        INSERT INTO jobs (
            run_key, status, symbol, start_date, end_date, cash, use_market_filter,
            risk_percent, fast_ma, slow_ma, strategy_id, strategy_params_json, code_version, cache_hit
        ) VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            run_key, req.symbol, req.start, req.end, req.cash, int(req.use_market_filter),
            req.risk_percent, int(req.strategy_params.get('fast_ma', 10)),
            int(req.strategy_params.get('slow_ma', 20)),
            req.strategy_id, json.dumps(req.strategy_params, sort_keys=True, separators=(',', ':')),
            version,
        ),
    )
    conn.commit()
    return get_job(conn, cur.lastrowid) | {'cache_hit': False}


def get_job(conn, job_id: int) -> dict[str, Any] | None:
    return _row_to_dict(conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone())


def list_jobs(conn, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return [dict(row) for row in rows]


def update_job_status(conn, job_id: int, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE jobs SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, error, job_id),
    )
    conn.commit()


def request_from_job(job: dict[str, Any]) -> BacktestRequest:
    strategy_params = json.loads(job.get('strategy_params_json', '{}'))
    # Merge legacy fast_ma/slow_ma from DB columns into params for backward compat
    strategy_params.setdefault('fast_ma', int(job.get('fast_ma', 10)))
    strategy_params.setdefault('slow_ma', int(job.get('slow_ma', 20)))
    return BacktestRequest(
        symbol=job['symbol'],
        start=job['start_date'],
        end=job['end_date'],
        cash=float(job['cash']),
        use_market_filter=bool(job['use_market_filter']),
        risk_percent=float(job['risk_percent']),
        fast_ma=int(job.get('fast_ma', 10)),
        slow_ma=int(job.get('slow_ma', 20)),
        strategy_id=job.get('strategy_id', 'swing_ma_boll'),
        strategy_params=strategy_params,
    )


def mark_job_completed(conn, job_id: int, summary: dict[str, Any], artifact_path: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO job_results (
            job_id, final_value, total_return_pct, max_drawdown_pct, trade_count, win_rate_pct, artifact_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            float(summary['final_value']),
            float(summary['total_return_pct']),
            float(summary['max_drawdown_pct']),
            int(summary['trade_count']),
            float(summary['win_rate_pct']),
            artifact_path,
        ),
    )
    update_job_status(conn, job_id, 'completed')


def get_job_result(conn, job_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT jobs.*, job_results.final_value, job_results.total_return_pct,
               job_results.max_drawdown_pct, job_results.trade_count,
               job_results.win_rate_pct, job_results.artifact_path
        FROM jobs
        LEFT JOIN job_results ON jobs.id = job_results.job_id
        WHERE jobs.id = ?
        """,
        (job_id,),
    ).fetchone()
    return _row_to_dict(row)


def delete_job(conn, job_id: int) -> None:
    """Delete a job and its associated result (CASCADE via foreign key)."""
    conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
    conn.commit()


def delete_all_jobs(conn) -> int:
    """Delete all jobs and their results. Returns the count of deleted jobs."""
    cursor = conn.execute('SELECT COUNT(*) FROM jobs')
    count = cursor.fetchone()[0]
    conn.execute('DELETE FROM jobs')
    conn.commit()
    return count
