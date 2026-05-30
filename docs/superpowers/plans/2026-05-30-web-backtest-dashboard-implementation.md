# Web Backtest Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first web dashboard for async single-stock backtest analysis with historical result reuse, ready to deploy later to a server.

**Architecture:** Add a FastAPI backend under `server/`, a React/Vite frontend under `web/`, and a structured backtest service under `backtest/service.py`. SQLite stores task indexes and summaries; larger result payloads live in `data/results/{job_id}.json`; existing `backtest/`, `market/`, and `strategies/` logic remains reusable by CLI and web.

**Tech Stack:** Python, FastAPI, SQLite, Backtrader, Pandas, Pytest, HTTPX/TestClient, React, Vite, TypeScript, Recharts.

---

## File Structure

- Create `requirements.txt`: runtime/test dependencies for backend and existing quant code.
- Modify `.gitignore`: ignore SQLite DB, JSON result artifacts, Vite build output, and node dependencies.
- Create `backtest/service.py`: pure service API for structured backtest execution.
- Modify `strategies/swing_ma_boll.py`: use `self.close()` for full liquidation and keep current market score sizing.
- Create `server/db.py`: SQLite schema, connections, row helpers.
- Create `server/models.py`: Pydantic request/response models.
- Create `server/jobs.py`: run key creation, job CRUD, result artifact paths.
- Create `server/executor.py`: in-process background executor.
- Create `server/api.py`: FastAPI routes.
- Create `server/main.py`: app entrypoint.
- Create `tests/test_backtest_service.py`: service-level tests using synthetic data.
- Create `tests/test_server_jobs.py`: SQLite/run-key/reuse tests.
- Create `tests/test_server_api.py`: FastAPI endpoint tests.
- Create `web/package.json`, `web/index.html`, `web/src/*`: Vite React app.
- Create `docs/web-dashboard.md`: local run and deployment notes.

---

### Task 1: Add Backend Dependencies And Ignored Runtime Artifacts

**Files:**
- Create: `requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Create dependency file**

Create `requirements.txt` with:

```text
akshare
backtrader
fastapi
httpx
numpy
pandas
pydantic
pytest
uvicorn[standard]
```

- [ ] **Step 2: Extend ignored generated files**

Append these lines to `.gitignore`:

```gitignore
data/*.sqlite
data/*.sqlite-shm
data/*.sqlite-wal
data/results/
web/node_modules/
web/dist/
web/.vite/
.superpowers/
```

- [ ] **Step 3: Verify dependency metadata is readable**

Run:

```powershell
python -m pip install -r requirements.txt
```

Expected: dependencies install or report already satisfied.

- [ ] **Step 4: Commit**

```powershell
git add requirements.txt .gitignore
git commit -m "chore: add web dashboard dependencies"
```

---

### Task 2: Make Backtests Return Structured Results

**Files:**
- Create: `backtest/service.py`
- Modify: `strategies/swing_ma_boll.py`
- Test: `tests/test_backtest_service.py`

- [ ] **Step 1: Write failing tests for structured service results**

Create `tests/test_backtest_service.py`:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from backtest.run_backtest import generate_synthetic_data
from backtest.service import BacktestRequest, run_backtest_service


def test_run_backtest_service_returns_serializable_result(monkeypatch):
    df = generate_synthetic_data(start='20240101', end='20240630')

    def fake_loader(symbol, start, end):
        return df.copy()

    monkeypatch.setattr('backtest.service.load_market_data', fake_loader)
    request = BacktestRequest(
        symbol='000001',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=False,
    )

    result = run_backtest_service(request)

    payload = result.to_dict()
    assert payload['symbol'] == '000001'
    assert payload['start'] == '20240101'
    assert payload['end'] == '20240630'
    assert payload['initial_cash'] == 100000.0
    assert 'final_value' in payload
    assert 'total_return_pct' in payload
    assert isinstance(payload['equity_curve'], list)
    assert len(payload['equity_curve']) > 20
    assert payload['equity_curve'][0]['date'].isdigit()


def test_market_filter_scores_are_exposed(monkeypatch):
    df = generate_synthetic_data(start='20240101', end='20240630')

    def fake_loader(symbol, start, end):
        return df.copy()

    def fake_score(start, end, config):
        dates = pd.bdate_range(start=start, end=end)
        return pd.DataFrame({
            'date': dates,
            'trend_score': [0.5] * len(dates),
            'sentiment_score': [0.6] * len(dates),
            'volume_score': [0.7] * len(dates),
            'total_score': [0.6] * len(dates),
        })

    monkeypatch.setattr('backtest.service.load_market_data', fake_loader)
    monkeypatch.setattr('backtest.service.get_market_score', fake_score)

    request = BacktestRequest(
        symbol='000001',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=True,
    )

    result = run_backtest_service(request)

    assert result.market_score_summary['min'] == 0.6
    assert result.market_score_summary['max'] == 0.6
    assert len(result.market_scores) > 20
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest -q tests/test_backtest_service.py
```

Expected: FAIL because `backtest.service` does not exist.

- [ ] **Step 3: Implement `backtest/service.py`**

Create `backtest/service.py`:

```python
"""Structured backtest service used by CLI and web API."""

from dataclasses import asdict, dataclass, field
from typing import Any

import backtrader as bt
import pandas as pd

from backtest.data_loader import load_market_data, resolve_date_range
from market.market_analyzer import MarketConfig, get_market_score
from strategies.swing_ma_boll import SwingStrategy


@dataclass(frozen=True)
class BacktestRequest:
    symbol: str
    start: str
    end: str
    cash: float = 100000.0
    use_market_filter: bool = True
    risk_percent: float = 0.95
    fast_ma: int = 10
    slow_ma: int = 20

    def normalized(self) -> 'BacktestRequest':
        start, end = resolve_date_range(self.start, self.end)
        return BacktestRequest(
            symbol=str(self.symbol).zfill(6),
            start=start,
            end=end,
            cash=float(self.cash),
            use_market_filter=bool(self.use_market_filter),
            risk_percent=float(self.risk_percent),
            fast_ma=int(self.fast_ma),
            slow_ma=int(self.slow_ma),
        )


@dataclass
class BacktestResult:
    symbol: str
    start: str
    end: str
    initial_cash: float
    final_value: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_rate_pct: float
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    market_scores: list[dict[str, Any]] = field(default_factory=list)
    market_score_summary: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EquityCurveAnalyzer(bt.Analyzer):
    def start(self):
        self.rows = []

    def next(self):
        self.rows.append({
            'date': self.strategy.datas[0].datetime.date(0).strftime('%Y%m%d'),
            'value': float(self.strategy.broker.getvalue()),
            'cash': float(self.strategy.broker.getcash()),
        })

    def get_analysis(self):
        return self.rows


class TradeListAnalyzer(bt.Analyzer):
    def start(self):
        self.trades = []

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.trades.append({
            'date': self.strategy.datas[0].datetime.date(0).strftime('%Y%m%d'),
            'pnl': float(trade.pnl),
            'pnlcomm': float(trade.pnlcomm),
            'barlen': int(trade.barlen),
            'size': float(trade.size),
        })

    def get_analysis(self):
        return self.trades


def _market_score_payload(start: str, end: str, enabled: bool) -> tuple[dict[str, float] | None, list[dict[str, Any]], dict[str, float]]:
    if not enabled:
        return None, [], {}

    score_df = get_market_score(start, end, MarketConfig())
    score_dict = dict(zip(
        score_df['date'].dt.strftime('%Y%m%d'),
        score_df['total_score'],
    ))
    rows = []
    for _, row in score_df.iterrows():
        rows.append({
            'date': row['date'].strftime('%Y%m%d'),
            'trend_score': float(row['trend_score']),
            'sentiment_score': float(row['sentiment_score']),
            'volume_score': float(row['volume_score']),
            'total_score': float(row['total_score']),
        })
    summary = {
        'min': float(score_df['total_score'].min()),
        'max': float(score_df['total_score'].max()),
        'mean': float(score_df['total_score'].mean()),
    }
    return score_dict, rows, summary


def run_backtest_service(request: BacktestRequest) -> BacktestResult:
    req = request.normalized()
    score_dict, score_rows, score_summary = _market_score_payload(
        req.start, req.end, req.use_market_filter
    )

    df = load_market_data(req.symbol, req.start, req.end)
    data = bt.feeds.PandasData(dataname=df, datetime=0)

    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.addstrategy(
        SwingStrategy,
        fast_ma=req.fast_ma,
        slow_ma=req.slow_ma,
        risk_percent=req.risk_percent,
        market_score_dict=score_dict,
    )
    cerebro.broker.setcash(req.cash)
    cerebro.addanalyzer(EquityCurveAnalyzer, _name='equity')
    cerebro.addanalyzer(TradeListAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_stats')

    strategies = cerebro.run(runonce=False, stdstats=False)
    strategy = strategies[0]

    final_value = float(cerebro.broker.getvalue())
    total_return_pct = (final_value / req.cash - 1.0) * 100.0
    drawdown = strategy.analyzers.drawdown.get_analysis()
    trade_stats = strategy.analyzers.trade_stats.get_analysis()
    trades = strategy.analyzers.trades.get_analysis()
    total_closed = int(trade_stats.get('total', {}).get('closed', 0) or 0)
    won_total = int(trade_stats.get('won', {}).get('total', 0) or 0)
    win_rate_pct = (won_total / total_closed * 100.0) if total_closed else 0.0

    return BacktestResult(
        symbol=req.symbol,
        start=req.start,
        end=req.end,
        initial_cash=req.cash,
        final_value=final_value,
        total_return_pct=float(total_return_pct),
        max_drawdown_pct=float(drawdown.get('max', {}).get('drawdown', 0.0) or 0.0),
        trade_count=total_closed,
        win_rate_pct=float(win_rate_pct),
        equity_curve=strategy.analyzers.equity.get_analysis(),
        trades=trades,
        market_scores=score_rows,
        market_score_summary=score_summary,
    )
```

- [ ] **Step 4: Ensure sells close the full position**

Modify `strategies/swing_ma_boll.py` sell branch:

```python
        elif (self.ma_fast[0] < self.ma_slow[0] or
              self.data.close[0] < self.boll.lines.bot[0]):
            if self.signal != 0:
                self.close()
                self.signal = 0
```

- [ ] **Step 5: Run service tests**

Run:

```powershell
python -m pytest -q tests/test_backtest_service.py
```

Expected: PASS.

- [ ] **Step 6: Run existing quant tests**

Run:

```powershell
python -m pytest -q tests/test_market_analyzer.py tests/test_integration.py tests/test_indicators.py
```

Expected: PASS, with existing unknown `slow` marker warnings allowed.

- [ ] **Step 7: Commit**

```powershell
git add backtest/service.py strategies/swing_ma_boll.py tests/test_backtest_service.py
git commit -m "feat: add structured backtest service"
```

---

### Task 3: Add SQLite Schema And Job Repository

**Files:**
- Create: `server/__init__.py`
- Create: `server/db.py`
- Create: `server/jobs.py`
- Test: `tests/test_server_jobs.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_server_jobs.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest -q tests/test_server_jobs.py
```

Expected: FAIL because `server` modules do not exist.

- [ ] **Step 3: Create `server/__init__.py`**

Create an empty package marker:

```python
"""FastAPI backend package for the web dashboard."""
```

- [ ] **Step 4: Implement database schema**

Create `server/db.py`:

```python
import os
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'quantx.sqlite')


def connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_key TEXT NOT NULL,
            status TEXT NOT NULL,
            symbol TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            cash REAL NOT NULL,
            use_market_filter INTEGER NOT NULL,
            risk_percent REAL NOT NULL,
            fast_ma INTEGER NOT NULL,
            slow_ma INTEGER NOT NULL,
            code_version TEXT NOT NULL,
            cache_hit INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_run_key_status ON jobs(run_key, status);
        CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);

        CREATE TABLE IF NOT EXISTS job_results (
            job_id INTEGER PRIMARY KEY,
            final_value REAL NOT NULL,
            total_return_pct REAL NOT NULL,
            max_drawdown_pct REAL NOT NULL,
            trade_count INTEGER NOT NULL,
            win_rate_pct REAL NOT NULL,
            artifact_path TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()
    return conn
```

- [ ] **Step 5: Implement job repository**

Create `server/jobs.py`:

```python
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
            risk_percent, fast_ma, slow_ma, code_version, cache_hit
        ) VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            run_key, req.symbol, req.start, req.end, req.cash, int(req.use_market_filter),
            req.risk_percent, req.fast_ma, req.slow_ma, version,
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
    return BacktestRequest(
        symbol=job['symbol'],
        start=job['start_date'],
        end=job['end_date'],
        cash=float(job['cash']),
        use_market_filter=bool(job['use_market_filter']),
        risk_percent=float(job['risk_percent']),
        fast_ma=int(job['fast_ma']),
        slow_ma=int(job['slow_ma']),
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
```

- [ ] **Step 6: Run repository tests**

Run:

```powershell
python -m pytest -q tests/test_server_jobs.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/__init__.py server/db.py server/jobs.py tests/test_server_jobs.py
git commit -m "feat: add sqlite job repository"
```

---

### Task 4: Add Background Executor And Result Artifacts

**Files:**
- Create: `server/executor.py`
- Test: `tests/test_server_executor.py`

- [ ] **Step 1: Write failing executor tests**

Create `tests/test_server_executor.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest -q tests/test_server_executor.py
```

Expected: FAIL because `server.executor` does not exist.

- [ ] **Step 3: Implement executor**

Create `server/executor.py`:

```python
import json
import os
import threading

from backtest.service import run_backtest_service
from server.jobs import get_job, mark_job_completed, request_from_job, update_job_status

DEFAULT_ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'results')


def execute_job_once(conn, job_id: int, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> None:
    job = get_job(conn, job_id)
    if job is None:
        return
    os.makedirs(artifact_dir, exist_ok=True)
    update_job_status(conn, job_id, 'running')
    try:
        result = run_backtest_service(request_from_job(job))
        artifact_path = os.path.join(artifact_dir, f'{job_id}.json')
        with open(artifact_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        mark_job_completed(conn, job_id, result.to_dict(), artifact_path)
    except Exception as exc:
        update_job_status(conn, job_id, 'failed', str(exc))


def submit_background(conn, job_id: int, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> threading.Thread:
    thread = threading.Thread(
        target=execute_job_once,
        args=(conn, job_id, artifact_dir),
        daemon=True,
    )
    thread.start()
    return thread
```

- [ ] **Step 4: Run executor tests**

Run:

```powershell
python -m pytest -q tests/test_server_executor.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/executor.py tests/test_server_executor.py
git commit -m "feat: add background job executor"
```

---

### Task 5: Add FastAPI Routes

**Files:**
- Create: `server/models.py`
- Create: `server/api.py`
- Create: `server/main.py`
- Test: `tests/test_server_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_server_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest -q tests/test_server_api.py
```

Expected: FAIL because `server.api` does not exist.

- [ ] **Step 3: Implement API models**

Create `server/models.py`:

```python
from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    start: str
    end: str
    cash: float = 100000.0
    use_market_filter: bool = True
    risk_percent: float = 0.95
    fast_ma: int = 10
    slow_ma: int = 20
    force: bool = False


class JobResponse(BaseModel):
    id: int
    run_key: str
    status: str
    symbol: str
    start_date: str
    end_date: str
    cash: float
    use_market_filter: bool
    risk_percent: float
    fast_ma: int
    slow_ma: int
    code_version: str
    cache_hit: bool
    error: str | None = None
    created_at: str
    updated_at: str
```

- [ ] **Step 4: Implement FastAPI app factory**

Create `server/api.py`:

```python
import json

from fastapi import FastAPI, HTTPException

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

    return app
```

- [ ] **Step 5: Add app entrypoint**

Create `server/main.py`:

```python
from server.api import create_app

app = create_app()
```

- [ ] **Step 6: Run API tests**

Run:

```powershell
python -m pytest -q tests/test_server_api.py
```

Expected: PASS.

- [ ] **Step 7: Smoke test API startup**

Run:

```powershell
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Expected: server starts and prints a Uvicorn listening URL. Stop it with `Ctrl+C`.

- [ ] **Step 8: Commit**

```powershell
git add server/models.py server/api.py server/main.py tests/test_server_api.py
git commit -m "feat: add backtest task api"
```

---

### Task 6: Scaffold React/Vite Frontend

**Files:**
- Create: `web/package.json`
- Create: `web/index.html`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/api.ts`
- Create: `web/src/types.ts`
- Create: `web/src/styles.css`

- [ ] **Step 1: Create package manifest**

Create `web/package.json`:

```json
{
  "scripts": {
    "dev": "vite --host 127.0.0.1 --port 5173",
    "build": "vite build",
    "preview": "vite preview --host 127.0.0.1 --port 4173"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "typescript": "latest",
    "react": "latest",
    "react-dom": "latest",
    "recharts": "latest",
    "lucide-react": "latest"
  },
  "devDependencies": {}
}
```

- [ ] **Step 2: Create HTML entry**

Create `web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>QuantX Backtest Dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Create frontend types and API client**

Create `web/src/types.ts`:

```ts
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface Job {
  id: number;
  run_key: string;
  status: JobStatus;
  symbol: string;
  start_date: string;
  end_date: string;
  cash: number;
  use_market_filter: boolean;
  risk_percent: number;
  fast_ma: number;
  slow_ma: number;
  code_version: string;
  cache_hit: boolean;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface BacktestResult {
  symbol: string;
  start: string;
  end: string;
  initial_cash: number;
  final_value: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  trade_count: number;
  win_rate_pct: number;
  equity_curve: Array<{ date: string; value: number; cash: number }>;
  trades: Array<{ date: string; pnl: number; pnlcomm: number; barlen: number; size: number }>;
  market_scores: Array<{
    date: string;
    trend_score: number;
    sentiment_score: number;
    volume_score: number;
    total_score: number;
  }>;
  market_score_summary: Record<string, number>;
}
```

Create `web/src/api.ts`:

```ts
import type { BacktestResult, Job } from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function listJobs(): Promise<Job[]> {
  return request<Job[]>('/api/jobs');
}

export function createJob(payload: {
  symbol: string;
  start: string;
  end: string;
  cash: number;
  use_market_filter: boolean;
  risk_percent: number;
  fast_ma: number;
  slow_ma: number;
  force?: boolean;
}): Promise<Job> {
  return request<Job>('/api/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getJob(jobId: number): Promise<Job> {
  return request<Job>(`/api/jobs/${jobId}`);
}

export function getResult(jobId: number): Promise<BacktestResult> {
  return request<BacktestResult>(`/api/jobs/${jobId}/result`);
}
```

- [ ] **Step 4: Create root React app**

Create `web/src/main.tsx`:

```tsx
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';

createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Create `web/src/App.tsx`:

```tsx
export default function App() {
  return (
    <main className="app-shell">
      <section className="sidebar">
        <h1>QuantX</h1>
        <p>Backtest research workbench</p>
      </section>
      <section className="content-panel">
        <h2>Dashboard scaffold ready</h2>
        <p>Use the next tasks to connect jobs, charts, and result history.</p>
      </section>
    </main>
  );
}
```

Create `web/src/styles.css`:

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f4f6f8;
  color: #17202a;
}

.app-shell {
  display: grid;
  grid-template-columns: 360px 1fr;
  min-height: 100vh;
}

.sidebar {
  background: #ffffff;
  border-right: 1px solid #d9e1e8;
  padding: 24px;
}

.content-panel {
  padding: 24px;
}

@media (max-width: 860px) {
  .app-shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #d9e1e8;
  }
}
```

- [ ] **Step 5: Install and build frontend**

Run:

```powershell
Set-Location web
npm install
npm run build
Set-Location ..
```

Expected: Vite builds `web/dist`.

- [ ] **Step 6: Commit**

```powershell
git add web/package.json web/package-lock.json web/index.html web/src
git commit -m "feat: scaffold react dashboard"
```

---

### Task 7: Build Workbench UI With Async Job Polling

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: Replace scaffold with workbench component**

Replace `web/src/App.tsx` with:

```tsx
import { useEffect, useMemo, useState } from 'react';
import { Activity, Play, RefreshCcw } from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { createJob, getJob, getResult, listJobs } from './api';
import type { BacktestResult, Job } from './types';

const defaultForm = {
  symbol: '000001',
  start: '20230530',
  end: '20260530',
  cash: 100000,
  use_market_filter: true,
  risk_percent: 0.95,
  fast_ma: 10,
  slow_ma: 20,
};

function formatPct(value: number) {
  return `${value.toFixed(2)}%`;
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{status}</span>;
}

export default function App() {
  const [form, setForm] = useState(defaultForm);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refreshJobs() {
    const rows = await listJobs();
    setJobs(rows);
    if (!selectedJob && rows.length > 0) {
      setSelectedJob(rows[0]);
    }
  }

  useEffect(() => {
    refreshJobs().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!selectedJob) return;
    let cancelled = false;
    async function poll() {
      const latest = await getJob(selectedJob.id);
      if (cancelled) return;
      setSelectedJob(latest);
      setJobs((prev) => prev.map((job) => (job.id === latest.id ? latest : job)));
      if (latest.status === 'completed') {
        const payload = await getResult(latest.id);
        if (!cancelled) setResult(payload);
      }
      if (latest.status === 'failed') {
        setResult(null);
      }
    }
    poll().catch((err) => setError(err.message));
    const handle = window.setInterval(() => {
      poll().catch((err) => setError(err.message));
    }, selectedJob.status === 'queued' || selectedJob.status === 'running' ? 1500 : 6000);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, [selectedJob?.id]);

  const kpis = useMemo(() => {
    if (!result) return [];
    return [
      ['Return', formatPct(result.total_return_pct)],
      ['Max Drawdown', formatPct(result.max_drawdown_pct)],
      ['Win Rate', formatPct(result.win_rate_pct)],
      ['Trades', String(result.trade_count)],
      ['Final Value', result.final_value.toFixed(2)],
      ['Score Mean', result.market_score_summary.mean?.toFixed(2) ?? 'N/A'],
    ];
  }, [result]);

  async function submit(force = false) {
    setSubmitting(true);
    setError(null);
    try {
      const job = await createJob({ ...form, force });
      setSelectedJob(job);
      await refreshJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <Activity size={22} />
          <div>
            <h1>QuantX</h1>
            <p>Backtest research workbench</p>
          </div>
        </div>

        <form className="run-form" onSubmit={(event) => { event.preventDefault(); submit(false); }}>
          <label>Symbol<input value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} /></label>
          <label>Start<input value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} /></label>
          <label>End<input value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} /></label>
          <label>Cash<input type="number" value={form.cash} onChange={(e) => setForm({ ...form, cash: Number(e.target.value) })} /></label>
          <label className="check-row">
            <input type="checkbox" checked={form.use_market_filter} onChange={(e) => setForm({ ...form, use_market_filter: e.target.checked })} />
            Market filter
          </label>
          <button className="primary" type="submit" disabled={submitting}>
            <Play size={16} /> Start backtest
          </button>
          <button className="secondary" type="button" onClick={() => submit(true)} disabled={submitting || !selectedJob}>
            <RefreshCcw size={16} /> Force rerun
          </button>
        </form>

        <section className="history">
          <h2>History</h2>
          {jobs.map((job) => (
            <button key={job.id} className="history-item" onClick={() => setSelectedJob(job)}>
              <span>{job.symbol} {job.start_date}-{job.end_date}</span>
              <StatusBadge status={job.status} />
            </button>
          ))}
        </section>
      </aside>

      <section className="content-panel">
        {error && <div className="error">{error}</div>}
        {selectedJob && (
          <div className="result-header">
            <div>
              <h2>{selectedJob.symbol} Backtest</h2>
              <p>{selectedJob.start_date} to {selectedJob.end_date} · {selectedJob.cache_hit ? 'Cache hit' : 'Fresh task'}</p>
            </div>
            <StatusBadge status={selectedJob.status} />
          </div>
        )}

        {result ? (
          <>
            <div className="kpi-grid">
              {kpis.map(([label, value]) => (
                <div className="kpi" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>

            <section className="panel">
              <h3>Equity Curve</h3>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={result.equity_curve}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" minTickGap={32} />
                  <YAxis domain={['auto', 'auto']} />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#2563eb" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </section>

            <section className="panel">
              <h3>Market Scores</h3>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={result.market_scores}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" minTickGap={32} />
                  <YAxis domain={[0, 1]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="total_score" stroke="#0f766e" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="trend_score" stroke="#f59e0b" dot={false} />
                  <Line type="monotone" dataKey="sentiment_score" stroke="#7c3aed" dot={false} />
                  <Line type="monotone" dataKey="volume_score" stroke="#dc2626" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </section>

            <section className="panel">
              <h3>Trades</h3>
              <table>
                <thead><tr><th>Date</th><th>PnL</th><th>PnL Comm</th><th>Bars</th></tr></thead>
                <tbody>
                  {result.trades.map((trade, index) => (
                    <tr key={`${trade.date}-${index}`}>
                      <td>{trade.date}</td>
                      <td>{trade.pnl.toFixed(2)}</td>
                      <td>{trade.pnlcomm.toFixed(2)}</td>
                      <td>{trade.barlen}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        ) : (
          <div className="empty-state">Submit or select a completed job to view results.</div>
        )}
      </section>
    </main>
  );
}
```

- [ ] **Step 2: Replace CSS with responsive dashboard styling**

Replace `web/src/styles.css` with:

```css
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f4f6f8;
  color: #17202a;
}
button, input { font: inherit; }
.app-shell { display: grid; grid-template-columns: 380px 1fr; min-height: 100vh; }
.sidebar { background: #fff; border-right: 1px solid #d9e1e8; padding: 22px; overflow-y: auto; }
.content-panel { padding: 24px; min-width: 0; }
.brand-row { display: flex; gap: 12px; align-items: center; margin-bottom: 24px; }
.brand-row h1 { margin: 0; font-size: 22px; }
.brand-row p, .result-header p { margin: 4px 0 0; color: #627282; }
.run-form { display: grid; gap: 12px; }
.run-form label { display: grid; gap: 6px; color: #405060; font-size: 13px; }
.run-form input { border: 1px solid #cbd5df; border-radius: 6px; padding: 10px; background: #fff; }
.check-row { grid-template-columns: 18px 1fr; align-items: center; }
.primary, .secondary, .history-item { border: 0; border-radius: 6px; cursor: pointer; }
.primary, .secondary { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 11px; }
.primary { background: #2563eb; color: #fff; }
.secondary { background: #e8edf3; color: #1f2a37; }
.history { margin-top: 26px; }
.history h2 { font-size: 15px; margin: 0 0 10px; }
.history-item { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px; margin-bottom: 8px; background: #f4f6f8; text-align: left; }
.status { border-radius: 999px; padding: 4px 8px; font-size: 12px; background: #dbe4ee; color: #344256; }
.status-completed { background: #d1fae5; color: #065f46; }
.status-failed { background: #fee2e2; color: #991b1b; }
.status-running, .status-queued { background: #dbeafe; color: #1e40af; }
.result-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
.result-header h2 { margin: 0; }
.kpi-grid { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 12px; margin-bottom: 18px; }
.kpi, .panel, .empty-state, .error { background: #fff; border: 1px solid #d9e1e8; border-radius: 8px; padding: 16px; }
.kpi span { display: block; color: #627282; font-size: 12px; margin-bottom: 8px; }
.kpi strong { font-size: 22px; }
.panel { margin-bottom: 18px; }
.panel h3 { margin: 0 0 14px; }
.error { color: #991b1b; background: #fff1f2; margin-bottom: 16px; }
.empty-state { color: #627282; min-height: 220px; display: flex; align-items: center; justify-content: center; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid #e5ebf1; padding: 10px; text-align: left; }
th { color: #627282; font-size: 12px; }
@media (max-width: 980px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid #d9e1e8; }
  .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .content-panel { padding: 16px; }
}
```

- [ ] **Step 3: Build frontend**

Run:

```powershell
Set-Location web
npm run build
Set-Location ..
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add web/src/App.tsx web/src/styles.css
git commit -m "feat: add backtest workbench ui"
```

---

### Task 8: Add Market Filter Comparison Flow

**Files:**
- Modify: `server/api.py`
- Modify: `web/src/api.ts`
- Modify: `web/src/types.ts`
- Modify: `web/src/App.tsx`
- Test: `tests/test_server_api.py`

- [ ] **Step 1: Add failing API test for comparison task creation**

Append to `tests/test_server_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest -q tests/test_server_api.py::test_compare_market_filter_creates_counterpart_job
```

Expected: FAIL with 404 because the comparison endpoint does not exist.

- [ ] **Step 3: Add comparison endpoint**

In `server/api.py`, add this route inside `create_app()`:

```python
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
```

- [ ] **Step 4: Add frontend API type and call**

Append to `web/src/types.ts`:

```ts
export interface ComparisonResponse {
  source_job_id: number;
  comparison_job: Job;
}
```

Append to `web/src/api.ts`:

```ts
import type { ComparisonResponse } from './types';

export function createMarketFilterComparison(jobId: number): Promise<ComparisonResponse> {
  return request<ComparisonResponse>(`/api/jobs/${jobId}/compare-market-filter`, {
    method: 'POST',
  });
}
```

If TypeScript rejects duplicate type imports, merge the new `ComparisonResponse` import into the existing import statement:

```ts
import type { BacktestResult, ComparisonResponse, Job } from './types';
```

- [ ] **Step 5: Add compare button and comparison state to `App.tsx`**

In `web/src/App.tsx`, update imports:

```tsx
import { createJob, createMarketFilterComparison, getJob, getResult, listJobs } from './api';
```

Add state near the other `useState` calls:

```tsx
  const [comparisonJob, setComparisonJob] = useState<Job | null>(null);
  const [comparisonResult, setComparisonResult] = useState<BacktestResult | null>(null);
```

Add this function below `submit()`:

```tsx
  async function compareMarketFilter() {
    if (!selectedJob) return;
    setError(null);
    try {
      const response = await createMarketFilterComparison(selectedJob.id);
      setComparisonJob(response.comparison_job);
      setComparisonResult(null);
      await refreshJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }
```

Add a second polling effect for the comparison job:

```tsx
  useEffect(() => {
    if (!comparisonJob) return;
    let cancelled = false;
    async function pollComparison() {
      const latest = await getJob(comparisonJob.id);
      if (cancelled) return;
      setComparisonJob(latest);
      if (latest.status === 'completed') {
        const payload = await getResult(latest.id);
        if (!cancelled) setComparisonResult(payload);
      }
    }
    pollComparison().catch((err) => setError(err.message));
    const handle = window.setInterval(() => {
      pollComparison().catch((err) => setError(err.message));
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, [comparisonJob?.id]);
```

Add a button beside the force rerun button:

```tsx
          <button className="secondary" type="button" onClick={compareMarketFilter} disabled={!selectedJob}>
            Compare filter
          </button>
```

Add this panel below the KPI grid:

```tsx
            {comparisonJob && (
              <section className="panel">
                <h3>Market Filter Comparison</h3>
                {comparisonResult ? (
                  <div className="comparison-grid">
                    <div><span>Base return</span><strong>{formatPct(result.total_return_pct)}</strong></div>
                    <div><span>Compare return</span><strong>{formatPct(comparisonResult.total_return_pct)}</strong></div>
                    <div><span>Base drawdown</span><strong>{formatPct(result.max_drawdown_pct)}</strong></div>
                    <div><span>Compare drawdown</span><strong>{formatPct(comparisonResult.max_drawdown_pct)}</strong></div>
                    <div><span>Base trades</span><strong>{result.trade_count}</strong></div>
                    <div><span>Compare trades</span><strong>{comparisonResult.trade_count}</strong></div>
                  </div>
                ) : (
                  <p>Comparison job #{comparisonJob.id} is {comparisonJob.status}.</p>
                )}
              </section>
            )}
```

Append this CSS to `web/src/styles.css`:

```css
.comparison-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(120px, 1fr));
  gap: 12px;
}
.comparison-grid div {
  border: 1px solid #e5ebf1;
  border-radius: 6px;
  padding: 12px;
}
.comparison-grid span {
  display: block;
  color: #627282;
  font-size: 12px;
  margin-bottom: 6px;
}
.comparison-grid strong {
  font-size: 18px;
}
@media (max-width: 700px) {
  .comparison-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Run API and frontend checks**

Run:

```powershell
python -m pytest -q tests/test_server_api.py
Set-Location web
npm run build
Set-Location ..
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/api.py web/src/api.ts web/src/types.ts web/src/App.tsx web/src/styles.css tests/test_server_api.py
git commit -m "feat: add market filter comparison task"
```

---

### Task 9: Add CORS And Local Run Documentation

**Files:**
- Modify: `server/api.py`
- Create: `docs/web-dashboard.md`
- Modify: `README.md`

- [ ] **Step 1: Add CORS for local Vite dev server**

In `server/api.py`, add import:

```python
from fastapi.middleware.cors import CORSMiddleware
```

Inside `create_app()` after app creation:

```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173'],
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )
```

- [ ] **Step 2: Create dashboard docs**

Create `docs/web-dashboard.md`:

````markdown
# Web Backtest Dashboard

## Local Development

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the API:

```powershell
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Install frontend dependencies:

```powershell
Set-Location web
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Data Files

- SQLite task database: `data/quantx.sqlite`
- Result artifacts: `data/results/{job_id}.json`
- Market and stock CSV caches: `data/*.csv`

## Deployment Notes

The first version has no login. For server deployment, bind the API behind a reverse proxy or a private network. Use:

```powershell
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Build the frontend with:

```powershell
Set-Location web
npm run build
```
````

- [ ] **Step 3: Link docs from README**

Add this section to `README.md` after Quick Start:

```markdown
## Web 分析台

本地开发见 [docs/web-dashboard.md](docs/web-dashboard.md)。

后端使用 FastAPI，前端使用 React/Vite，历史任务和摘要结果保存在 SQLite 中。
```

- [ ] **Step 4: Run backend and frontend checks**

Run:

```powershell
python -m pytest -q tests/test_server_jobs.py tests/test_server_executor.py tests/test_server_api.py
Set-Location web
npm run build
Set-Location ..
```

Expected: all tests pass and frontend build succeeds.

- [ ] **Step 5: Commit**

```powershell
git add server/api.py docs/web-dashboard.md README.md
git commit -m "docs: add dashboard run instructions"
```

---

### Task 10: End-To-End Smoke Verification

**Files:**
- No source changes expected unless a smoke check reveals a bug.

- [ ] **Step 1: Start API**

Run:

```powershell
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Expected: API starts and remains running.

- [ ] **Step 2: In a second shell, submit a job**

Run:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/jobs -ContentType "application/json" -Body '{"symbol":"000001","start":"20230530","end":"20260530","cash":100000,"use_market_filter":true,"risk_percent":0.95,"fast_ma":10,"slow_ma":20}'
```

Expected: JSON response contains `id`, `status`, `run_key`, and `symbol`.

- [ ] **Step 3: Poll jobs**

Run:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/jobs
```

Expected: the submitted job appears and eventually reaches `completed` or `failed`. If it fails, inspect `error`.

- [ ] **Step 4: Build frontend**

Run:

```powershell
Set-Location web
npm run build
Set-Location ..
```

Expected: PASS.

- [ ] **Step 5: Run full available tests**

Run:

```powershell
python -m pytest -q tests/
```

Expected: PASS, with existing `slow` marker warnings allowed.

- [ ] **Step 6: Commit any smoke-test fixes**

If code changes were needed:

```powershell
git add server backtest strategies tests web docs README.md requirements.txt .gitignore
git commit -m "fix: complete dashboard smoke verification"
```

If no code changes were needed, do not create an empty commit.
