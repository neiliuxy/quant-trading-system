import json
from difflib import SequenceMatcher
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backtest.service import BacktestRequest
from server.db import DEFAULT_DB_PATH, init_db
from server.executor import submit_background
from server.jobs import create_or_reuse_job, get_job, get_job_result, list_jobs
from server.models import JobCreateRequest


class StockItem(BaseModel):
    code: str
    name: str


class StocksResponse(BaseModel):
    stocks: list[StockItem]


# 完整的A股股票列表（主板）
STOCK_DATABASE = [
    StockItem(code='000001', name='平安银行'),
    StockItem(code='000002', name='万科A'),
    StockItem(code='000333', name='美的集团'),
    StockItem(code='000651', name='格力电器'),
    StockItem(code='000858', name='五粮液'),
    StockItem(code='000876', name='新希望'),
    StockItem(code='600000', name='浦发银行'),
    StockItem(code='600009', name='上海机场'),
    StockItem(code='600016', name='民生银行'),
    StockItem(code='600019', name='宝钢股份'),
    StockItem(code='600028', name='中国石化'),
    StockItem(code='600030', name='中信证券'),
    StockItem(code='600031', name='三一重工'),
    StockItem(code='600036', name='招商银行'),
    StockItem(code='600048', name='保利地产'),
    StockItem(code='600050', name='中国联通'),
    StockItem(code='600104', name='上汽集团'),
    StockItem(code='600276', name='恒瑞医药'),
    StockItem(code='600519', name='贵州茅台'),
    StockItem(code='600585', name='海螺水泥'),
    StockItem(code='600588', name='用友网络'),
    StockItem(code='600690', name='青岛海尔'),
    StockItem(code='601012', name='隆基绿能'),
    StockItem(code='601166', name='兴业银行'),
    StockItem(code='601288', name='农业银行'),
    StockItem(code='601318', name='中国平安'),
    StockItem(code='601328', name='交通银行'),
    StockItem(code='601398', name='工商银行'),
    StockItem(code='601988', name='中国银行'),
]


def _fuzzy_match(query: str, text: str) -> float:
    """计算模糊匹配相似度 (0-1)"""
    return SequenceMatcher(None, query.lower(), text.lower()).ratio()


def _search_stocks(query: Optional[str] = None, threshold: float = 0.3) -> list[StockItem]:
    """搜索股票列表，支持模糊匹配"""
    if not query:
        return STOCK_DATABASE

    query = query.strip()
    results = []

    for stock in STOCK_DATABASE:
        code_match = _fuzzy_match(query, stock.code)
        name_match = _fuzzy_match(query, stock.name)
        best_match = max(code_match, name_match)

        if best_match >= threshold:
            results.append((stock, best_match))

    # 按相似度降序排序
    results.sort(key=lambda x: x[1], reverse=True)
    return [item for item, _ in results]


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

    @app.get('/api/stocks', response_model=StocksResponse)
    def get_stocks(q: Optional[str] = None):
        """获取股票列表，支持模糊搜索"""
        stocks = _search_stocks(q)
        return StocksResponse(stocks=stocks)

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
