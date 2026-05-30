import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backtest.service import BacktestRequest
from server.db import DEFAULT_DB_PATH, init_db
from server.executor import submit_background
from server.jobs import create_or_reuse_job, get_job, get_job_result, list_jobs
from server.models import JobCreateRequest


def _serialize_job(row: dict) -> dict:
    payload = dict(row)
    payload['use_market_filter'] = bool(payload['use_market_filter'])
    payload['cache_hit'] = bool(payload.get('cache_hit', 0))
    return payload


def create_app(db_path: str = DEFAULT_DB_PATH) -> FastAPI:
    app = FastAPI(title='QuantX Backtest Dashboard')
    conn = init_db(db_path)
    app.state.db = conn

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173'],
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.get('/api/health')
    def health():
        return {'status': 'ok'}

    @app.post('/api/jobs')
    def create_job(payload: JobCreateRequest):
        req = BacktestRequest(
            symbol=payload.symbol,
            start=payload.start,
            end=payload.end,
            cash=payload.cash,
            use_market_filter=payload.use_market_filter,
            risk_percent=payload.risk_percent,
            fast_ma=payload.fast_ma,
            slow_ma=payload.slow_ma,
        )
        job = create_or_reuse_job(conn, req, force=payload.force)
        if job['status'] == 'queued' and not job.get('cache_hit'):
            submit_background(conn, job['id'])
        return _serialize_job(job)

    @app.get('/api/jobs')
    def jobs(limit: int = 50):
        return [_serialize_job(row) for row in list_jobs(conn, limit)]

    @app.get('/api/jobs/{job_id}')
    def job_detail(job_id: int):
        job = get_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail='job not found')
        return _serialize_job(job)

    @app.get('/api/jobs/{job_id}/result')
    def job_result(job_id: int):
        result = get_job_result(conn, job_id)
        if result is None or not result.get('artifact_path'):
            raise HTTPException(status_code=404, detail='result not found')
        with open(result['artifact_path'], encoding='utf-8') as f:
            return json.load(f)

    @app.post('/api/jobs/{job_id}/rerun')
    def rerun(job_id: int):
        job = get_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail='job not found')
        req = BacktestRequest(
            symbol=job['symbol'],
            start=job['start_date'],
            end=job['end_date'],
            cash=float(job['cash']),
            use_market_filter=bool(job['use_market_filter']),
            risk_percent=float(job['risk_percent']),
            fast_ma=int(job['fast_ma']),
            slow_ma=int(job['slow_ma']),
        )
        new_job = create_or_reuse_job(conn, req, code_version=job['code_version'], force=True)
        submit_background(conn, new_job['id'])
        return _serialize_job(new_job)

    @app.post('/api/jobs/{job_id}/compare-market-filter')
    def compare_market_filter(job_id: int):
        job = get_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail='job not found')
        req = BacktestRequest(
            symbol=job['symbol'],
            start=job['start_date'],
            end=job['end_date'],
            cash=float(job['cash']),
            use_market_filter=not bool(job['use_market_filter']),
            risk_percent=float(job['risk_percent']),
            fast_ma=int(job['fast_ma']),
            slow_ma=int(job['slow_ma']),
        )
        comparison_job = create_or_reuse_job(conn, req, code_version=job['code_version'])
        if comparison_job['status'] == 'queued' and not comparison_job.get('cache_hit'):
            submit_background(conn, comparison_job['id'])
        return {
            'source_job_id': job_id,
            'comparison_job': _serialize_job(comparison_job),
        }

    return app
