# Multi-Strategy Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the web app choose among multiple backtest strategies, with each strategy implemented as a module that declares its own parameters.

**Architecture:** Introduce a small strategy contract and registry in `strategies/`, then thread `strategy_id` and `strategy_params` through the backtest request, job cache key, SQLite storage, FastAPI endpoints, and React form. Keep existing MA + Bollinger behavior intact behind the registry, and add a new Bollinger reversal strategy as the second implementation.

**Tech Stack:** Python 3, Backtrader, FastAPI, SQLite, React, Vite, TypeScript, pytest.

---

## File Structure

### New files

- `strategies/__init__.py` - package export surface
- `strategies/base.py` - shared strategy spec and parameter metadata types
- `strategies/registry.py` - strategy registration and lookup helpers
- `strategies/bollinger_reversal.py` - new mean-reversion strategy module
- `tests/test_strategies.py` - registry and strategy metadata tests
- `web/src/StrategyParamsForm.tsx` - renders strategy-specific parameters in the sidebar form

### Modified files

- `strategies/swing_ma_boll.py` - expose the existing trend strategy through the new contract
- `backtest/service.py` - accept `strategy_id` and `strategy_params`, resolve the selected strategy, pass merged params to Backtrader
- `server/models.py` - add strategy fields to job create request and response models
- `server/jobs.py` - include strategy fields in run key, job persistence, and job reconstruction
- `server/db.py` - add lightweight schema migration for the new job columns
- `server/api.py` - add `GET /api/strategies` and thread strategy fields through job creation and reruns
- `web/src/types.ts` - add strategy catalog types and job/result fields
- `web/src/api.ts` - request and return strategy metadata
- `web/src/App.tsx` - strategy dropdown, dynamic params, and display of the chosen strategy
- `tests/test_backtest_service.py` - strategy execution and run-result coverage
- `tests/test_server_api.py` - strategy endpoint and job payload coverage
- `tests/test_server_jobs.py` - run-key and persistence coverage
- `tests/test_server_executor.py` - end-to-end job execution with strategy fields

---

### Task 1: Define the strategy contract and registry

**Files:**
- Create: `strategies/__init__.py`
- Create: `strategies/base.py`
- Create: `strategies/registry.py`
- Create: `strategies/bollinger_reversal.py`
- Modify: `strategies/swing_ma_boll.py`
- Create: `tests/test_strategies.py`

- [ ] **Step 1: Write the failing test**

```python
from strategies.registry import list_strategies, get_strategy_spec


def test_registry_exposes_both_strategies():
    ids = [spec.id for spec in list_strategies()]
    assert ids == ['swing_ma_boll', 'bollinger_reversal']


def test_strategy_spec_includes_params():
    spec = get_strategy_spec('bollinger_reversal')
    assert spec.name == 'Bollinger Reversal'
    assert [p.name for p in spec.params] == ['boll_period', 'boll_devfactor']
    assert spec.defaults == {'boll_period': 20, 'boll_devfactor': 2.0}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_strategies.py -v`

Expected: fail because the registry and strategy spec types do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# strategies/base.py
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StrategyParamSpec:
    name: str
    label: str
    type: str
    default: Any


@dataclass(frozen=True)
class StrategySpec:
    id: str
    name: str
    description: str
    strategy_class: type
    params: tuple[StrategyParamSpec, ...]

    @property
    def defaults(self) -> dict[str, Any]:
        return {p.name: p.default for p in self.params}
```

```python
# strategies/registry.py
from strategies.bollinger_reversal import BollingerReversalStrategy, BOLLINGER_REVERSAL_SPEC
from strategies.swing_ma_boll import SwingStrategy, SWING_MA_BOLL_SPEC

_STRATEGIES = {
    SWING_MA_BOLL_SPEC.id: SWING_MA_BOLL_SPEC,
    BOLLINGER_REVERSAL_SPEC.id: BOLLINGER_REVERSAL_SPEC,
}


def list_strategies():
    return list(_STRATEGIES.values())


def get_strategy_spec(strategy_id: str):
    return _STRATEGIES[strategy_id]
```

```python
# strategies/bollinger_reversal.py
import backtrader as bt
from strategies.base import StrategyParamSpec, StrategySpec


class BollingerReversalStrategy(bt.Strategy):
    params = (
        ('boll_period', 20),
        ('boll_devfactor', 2.0),
    )

    def __init__(self):
        self.boll = bt.ind.BollingerBands(
            period=self.p.boll_period,
            devfactor=self.p.boll_devfactor,
        )
        self.was_below_lower = False

    def next(self):
        close = self.data.close[0]
        if close < self.boll.lines.bot[0]:
            self.was_below_lower = True
            return
        if self.position and (close >= self.boll.lines.mid[0] or close >= self.boll.lines.top[0]):
            self.close()
            return
        if self.was_below_lower and close > self.boll.lines.bot[0] and not self.position:
            self.buy()
            self.was_below_lower = False


BOLLINGER_REVERSAL_SPEC = StrategySpec(
    id='bollinger_reversal',
    name='Bollinger Reversal',
    description='Mean-reversion strategy that buys after price reclaims the lower band.',
    strategy_class=BollingerReversalStrategy,
    params=(
        StrategyParamSpec('boll_period', 'Bollinger Period', 'int', 20),
        StrategyParamSpec('boll_devfactor', 'Deviation Factor', 'float', 2.0),
    ),
)
```

```python
# strategies/swing_ma_boll.py
class SwingStrategy(bt.Strategy):
    params = (
        ('fast_ma', 10),
        ('slow_ma', 20),
        ('risk_percent', 0.95),
        ('market_score_dict', None),
        ('boll_period', 20),
        ('boll_devfactor', 2.0),
    )

    def __init__(self):
        self.ma_fast = bt.ind.SMA(period=self.p.fast_ma)
        self.ma_slow = bt.ind.SMA(period=self.p.slow_ma)
        self.boll = bt.ind.BollingerBands(period=self.p.boll_period, devfactor=self.p.boll_devfactor)
        self.signal = 0

SWING_MA_BOLL_SPEC = StrategySpec(
    id='swing_ma_boll',
    name='Swing MA + Bollinger',
    description='Trend-following moving-average strategy with Bollinger confirmation.',
    strategy_class=SwingStrategy,
    params=(
        StrategyParamSpec('fast_ma', 'Fast MA', 'int', 10),
        StrategyParamSpec('slow_ma', 'Slow MA', 'int', 20),
        StrategyParamSpec('boll_period', 'Bollinger Period', 'int', 20),
        StrategyParamSpec('boll_devfactor', 'Deviation Factor', 'float', 2.0),
    ),
)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_strategies.py -v`

Expected: pass, and the registry returns both strategies in stable order.

- [ ] **Step 5: Commit**

```bash
git add strategies/__init__.py strategies/base.py strategies/registry.py strategies/bollinger_reversal.py strategies/swing_ma_boll.py tests/test_strategies.py
git commit -m "feat: add strategy registry"
```

### Task 2: Thread strategy selection through backtest execution and cache keys

**Files:**
- Modify: `backtest/service.py`
- Modify: `server/jobs.py`
- Modify: `server/db.py`
- Modify: `tests/test_backtest_service.py`
- Modify: `tests/test_server_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
from backtest.service import BacktestRequest
from server.jobs import run_key_for_request


def test_run_key_changes_when_only_strategy_changes():
    req_a = BacktestRequest(symbol='000001', start='20240101', end='20240630', strategy_id='swing_ma_boll')
    req_b = BacktestRequest(symbol='000001', start='20240101', end='20240630', strategy_id='bollinger_reversal')
    assert run_key_for_request(req_a, code_version='abc123') != run_key_for_request(req_b, code_version='abc123')
```

```python
def test_run_backtest_service_accepts_strategy_params(monkeypatch):
    df = generate_synthetic_data(start='20240101', end='20240630')
    monkeypatch.setattr('backtest.service.load_market_data', lambda symbol, start, end: df.copy())
    request = BacktestRequest(
        symbol='000001',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=False,
        strategy_id='bollinger_reversal',
        strategy_params={'boll_period': 20, 'boll_devfactor': 2.0},
    )
    result = run_backtest_service(request)
    assert result.symbol == '000001'
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest tests/test_backtest_service.py tests/test_server_jobs.py -v
```

Expected: fail because `BacktestRequest` does not yet accept strategy fields and `run_key_for_request` does not include them.

- [ ] **Step 3: Write the minimal implementation**

```python
# backtest/service.py
from strategies.registry import get_strategy_spec


@dataclass(frozen=True)
class BacktestRequest:
    symbol: str
    start: str
    end: str
    cash: float = 100000.0
    use_market_filter: bool = True
    risk_percent: float = 0.95
    strategy_id: str = 'swing_ma_boll'
    strategy_params: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> 'BacktestRequest':
        start, end = resolve_date_range(self.start, self.end)
        spec = get_strategy_spec(self.strategy_id)
        unknown = set(self.strategy_params) - {param.name for param in spec.params}
        if unknown:
            raise ValueError(f"Unknown strategy params for {self.strategy_id}: {sorted(unknown)}")
        merged_params = dict(spec.defaults)
        merged_params.update(self.strategy_params)
        return BacktestRequest(
            symbol=str(self.symbol).zfill(6),
            start=start,
            end=end,
            cash=float(self.cash),
            use_market_filter=bool(self.use_market_filter),
            risk_percent=float(self.risk_percent),
            strategy_id=self.strategy_id,
            strategy_params=merged_params,
        )
```

```python
# backtest/service.py
def run_backtest_service(request: BacktestRequest) -> BacktestResult:
    req = request.normalized()
    spec = get_strategy_spec(req.strategy_id)
    score_dict, score_rows, score_summary = _market_score_payload(
        req.start, req.end, req.use_market_filter
    )
    strategy_kwargs = dict(req.strategy_params)
    strategy_kwargs['risk_percent'] = req.risk_percent
    strategy_kwargs['market_score_dict'] = score_dict
    cerebro.addstrategy(spec.strategy_class, **strategy_kwargs)
```

```python
# server/jobs.py
def run_key_for_request(request: BacktestRequest, code_version: str | None = None) -> str:
    req = request.normalized()
    payload = {
        'request': asdict(req),
        'market_config_hash': MarketConfig().hash(),
        'code_version': code_version or current_code_version(),
    }
```

```python
# server/db.py
def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(CREATE_TABLES_SQL)
    _migrate_jobs_schema(conn)
    conn.commit()
    return conn
```

```python
def _migrate_jobs_schema(conn: sqlite3.Connection) -> None:
    columns = {row['name'] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    if 'strategy_id' not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN strategy_id TEXT NOT NULL DEFAULT 'swing_ma_boll'")
    if 'strategy_params_json' not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN strategy_params_json TEXT NOT NULL DEFAULT '{}' ")
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
pytest tests/test_backtest_service.py tests/test_server_jobs.py -v
```

Expected: pass, and the run key changes when the strategy id or strategy params change.

- [ ] **Step 5: Commit**

```bash
git add backtest/service.py server/jobs.py server/db.py tests/test_backtest_service.py tests/test_server_jobs.py
git commit -m "feat: thread strategy selection through backtest"
```

### Task 3: Expose strategy metadata and persist it in the API

**Files:**
- Modify: `server/models.py`
- Modify: `server/api.py`
- Modify: `server/jobs.py`
- Modify: `tests/test_server_api.py`

- [ ] **Step 1: Write the failing test**

```python
def test_strategies_endpoint_lists_registered_strategies(tmp_path):
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)
    response = client.get('/api/strategies')
    assert response.status_code == 200
    body = response.json()
    assert [item['id'] for item in body] == ['swing_ma_boll', 'bollinger_reversal']
```

```python
def test_create_job_persists_strategy_fields(tmp_path, monkeypatch):
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
        'strategy_id': 'bollinger_reversal',
        'strategy_params': {'boll_period': 20, 'boll_devfactor': 2.0},
    })
    assert response.status_code == 200
    assert response.json()['strategy_id'] == 'bollinger_reversal'
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_server_api.py -v`

Expected: fail because the request model and API response do not yet include strategy fields.

- [ ] **Step 3: Write the minimal implementation**

```python
# server/models.py
class JobCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    start: str
    end: str
    cash: float = 100000.0
    use_market_filter: bool = True
    risk_percent: float = 0.95
    strategy_id: str = 'swing_ma_boll'
    strategy_params: dict[str, object] = Field(default_factory=dict)
    force: bool = False
```

```python
# server/api.py
@app.get('/api/strategies')
def strategies():
    return [
        {
            'id': spec.id,
            'name': spec.name,
            'description': spec.description,
            'params': [
                {'name': p.name, 'label': p.label, 'type': p.type, 'default': p.default}
                for p in spec.params
            ],
        }
        for spec in list_strategies()
    ]
```

```python
# server/api.py
req = BacktestRequest(
    symbol=payload.symbol,
    start=payload.start,
    end=payload.end,
    cash=payload.cash,
    use_market_filter=payload.use_market_filter,
    risk_percent=payload.risk_percent,
    strategy_id=payload.strategy_id,
    strategy_params=payload.strategy_params,
)
```

```python
# server/jobs.py
def create_or_reuse_job(conn, request: BacktestRequest, code_version: str | None = None, force: bool = False) -> dict[str, Any]:
    sql = """
    INSERT INTO jobs (
        run_key, status, symbol, start_date, end_date, cash, use_market_filter,
        risk_percent, fast_ma, slow_ma, strategy_id, strategy_params_json, code_version, cache_hit
    ) VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """
    params = (
        run_key, req.symbol, req.start, req.end, req.cash, int(req.use_market_filter),
        req.risk_percent,
        int(req.strategy_params.get('fast_ma', 10)),
        int(req.strategy_params.get('slow_ma', 20)),
        req.strategy_id,
        json.dumps(req.strategy_params, sort_keys=True, separators=(',', ':')),
        version,
    )
```

```python
# server/jobs.py
def request_from_job(job: dict[str, Any]) -> BacktestRequest:
    return BacktestRequest(
        symbol=job['symbol'],
        start=job['start_date'],
        end=job['end_date'],
        cash=float(job['cash']),
        use_market_filter=bool(job['use_market_filter']),
        risk_percent=float(job['risk_percent']),
        strategy_id=job['strategy_id'],
        strategy_params=json.loads(job['strategy_params_json'] or '{}'),
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_server_api.py -v`

Expected: pass, and the response body contains `strategy_id` and `strategy_params`.

- [ ] **Step 5: Commit**

```bash
git add server/models.py server/api.py server/jobs.py tests/test_server_api.py
git commit -m "feat: expose strategy metadata in api"
```

### Task 4: Add strategy selection and dynamic params to the web UI

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/api.ts`
- Modify: `web/src/App.tsx`
- Create: `web/src/StrategyParamsForm.tsx`

- [ ] **Step 1: Write the failing test**

Use the existing frontend build as the first verification gate.

Run: `cd web && npm run build`

Expected: TypeScript compile failure because `createJob` and `Job` do not yet know about strategy fields.

- [ ] **Step 2: Write the minimal implementation**

```ts
// web/src/types.ts
export interface StrategyParamSpec {
  name: string;
  label: string;
  type: 'int' | 'float' | 'string' | 'bool';
  default: number | string | boolean;
}

export interface StrategySpec {
  id: string;
  name: string;
  description: string;
  params: StrategyParamSpec[];
}
```

```ts
// web/src/api.ts
export function listStrategies(): Promise<StrategySpec[]> {
  return request<StrategySpec[]>('/api/strategies');
}

export function createJob(payload: {
  symbol: string;
  start: string;
  end: string;
  cash: number;
  use_market_filter: boolean;
  risk_percent: number;
  strategy_id: string;
  strategy_params: Record<string, unknown>;
  force?: boolean;
}): Promise<Job> {
  return request<Job>('/api/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
```

```tsx
// web/src/StrategyParamsForm.tsx
type Props = {
  spec: StrategySpec;
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
};
```

```tsx
// web/src/App.tsx
const [strategies, setStrategies] = useState<StrategySpec[]>([]);
const [selectedStrategyId, setSelectedStrategyId] = useState('swing_ma_boll');
const selectedStrategy = strategies.find((item) => item.id === selectedStrategyId) ?? strategies[0];
```

The form behavior must be:

1. load strategies on startup
2. select `swing_ma_boll` by default
3. when the user changes strategy, reset `strategy_params` to that strategy's defaults
4. submit `strategy_id` and `strategy_params` together with the common fields

The job history and result header should display the strategy name if present.

- [ ] **Step 3: Run the build to verify it passes**

Run: `cd web && npm run build`

Expected: build succeeds and the strategy dropdown renders with strategy-specific inputs.

- [ ] **Step 4: Commit**

```bash
git add web/src/types.ts web/src/api.ts web/src/App.tsx web/src/StrategyParamsForm.tsx
git commit -m "feat: add strategy selector to web ui"
```

### Task 5: Verify the full path end to end

**Files:**
- All files touched above
- No new code expected unless a test exposes a mismatch

- [ ] **Step 1: Run the focused backend tests**

Run:

```bash
pytest tests/test_strategies.py tests/test_backtest_service.py tests/test_server_jobs.py tests/test_server_api.py tests/test_server_executor.py -v
```

Expected: all pass.

- [ ] **Step 2: Run the backtest entry point**

Run:

```bash
python backtest/run_backtest.py
```

Expected: the command completes and produces a backtest result using either fetched market data or the existing synthetic fallback path.

- [ ] **Step 3: Run the frontend build again**

Run:

```bash
cd web
npm run build
```

Expected: pass.

- [ ] **Step 4: Review the sqlite schema on a fresh local database**

Run:

```bash
@'
from server.db import init_db
conn = init_db('data/quantx.sqlite')
print([row['name'] for row in conn.execute('PRAGMA table_info(jobs)').fetchall()])
'@ | python -
```

Expected: the `jobs` table includes `strategy_id` and `strategy_params_json`.

---

## Spec Coverage Check

- Strategy abstraction and registry: Task 1
- New Bollinger reversal strategy: Task 1
- Strategy-specific params: Tasks 1 and 4
- API strategy dropdown data: Task 3
- Job payload and persistence: Tasks 2 and 3
- Cache key separation: Task 2
- Lightweight DB migration: Task 2
- Web dropdown and dynamic param rendering: Task 4
- Tests and verification: Tasks 1 through 5

## Execution Notes

- Keep the existing trend strategy behavior unchanged except for plumbing it through the registry.
- Do not add a generic visual form builder; render only the parameter types needed by the first two strategies.
- Keep unknown strategy parameters rejected rather than silently ignored.
- Commit after each task so the branch stays easy to inspect and revert if needed.
