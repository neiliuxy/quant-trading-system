# Citic Securities Special Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `citic_wave` strategy for `600030` that uses market trend, securities-sector trend, and two-market turnover filters, then run a reproducible search against the agreed performance targets.

**Architecture:** Extend strategy metadata so strategies can declare required auxiliary feeds, then add loaders for the securities ETF and aggregate market turnover series. Implement a dedicated `CiticWaveStrategy` using four Backtrader feeds in a fixed order, wire the loaders into both the service and CLI backtest entry points, and finish with a reproducible search script that writes a markdown report.

**Tech Stack:** Python 3, Backtrader, pandas, AkShare, pytest, git

---

## File Structure

- Create: `strategies/citic_wave.py`
  Responsibility: the new strategy class and its `StrategySpec`.
- Create: `tests/test_citic_wave_strategy.py`
  Responsibility: unit tests for market filter, breakout entry, pullback entry, and exits.
- Create: `tests/test_data_loader_strategy_feeds.py`
  Responsibility: loader normalization and cache tests for the securities ETF and turnover series.
- Create: `scripts/search_citic_wave.py`
  Responsibility: reproducible parameter search and report generation for `600030`.
- Modify: `strategies/base.py`
  Responsibility: extend `StrategySpec` so strategies can declare required auxiliary feed ids.
- Modify: `strategies/registry.py`
  Responsibility: register the new strategy.
- Modify: `backtest/data_loader.py`
  Responsibility: add cached loaders for the securities ETF and the two-market turnover series.
- Modify: `backtest/service.py`
  Responsibility: load auxiliary feed frames based on strategy metadata and add them to Cerebro in declared order.
- Modify: `backtest/run_backtest.py`
  Responsibility: use the same auxiliary-feed path as the service so CLI and service stay aligned.
- Modify: `tests/test_strategies.py`
  Responsibility: cover `required_data` metadata and registry exposure for the new strategy.
- Modify: `tests/test_backtest_service.py`
  Responsibility: verify multi-feed strategies receive all required data and still return a valid result payload.

### Task 1: Strategy Metadata for Auxiliary Feeds

**Files:**
- Modify: `strategies/base.py`
- Modify: `strategies/registry.py`
- Modify: `tests/test_strategies.py`

- [ ] **Step 1: Write the failing tests**

Add the following assertions to `tests/test_strategies.py`:

```python
from strategies.registry import get_strategy_spec, list_strategies


def test_registry_exposes_citic_wave_strategy():
    ids = [spec.id for spec in list_strategies()]
    assert 'citic_wave' in ids


def test_strategy_spec_defaults_required_data_to_empty_tuple():
    spec = get_strategy_spec('bollinger_reversal')
    assert spec.required_data == ()


def test_b1_strategy_declares_required_index_feed():
    spec = get_strategy_spec('b1_strategy')
    assert spec.required_data == ('shanghai_index',)


def test_citic_wave_strategy_declares_all_required_feeds():
    spec = get_strategy_spec('citic_wave')
    assert spec.required_data == (
        'shanghai_index',
        'security_etf',
        'market_turnover',
    )
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `python -m pytest -q tests/test_strategies.py`

Expected: FAIL because `StrategySpec` has no `required_data` field and `citic_wave` is not registered yet.

- [ ] **Step 3: Implement the metadata support**

Update `strategies/base.py` so `StrategySpec` can describe required feeds:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StrategySpec:
    id: str
    name: str
    description: str
    strategy_class: type
    params: tuple[StrategyParamSpec, ...]
    required_data: tuple[str, ...] = field(default_factory=tuple)

    @property
    def defaults(self) -> dict[str, Any]:
        return {p.name: p.default for p in self.params}
```

Update `strategies/b1_strategy.py` when you edit its spec later in the same change:

```python
B1_STRATEGY_SPEC = StrategySpec(
    id='b1_strategy',
    name='B1 Strategy',
    description='Trend-following with oversold pullback entry. Market timing via 120-day MA, entry via 7 conditions.',
    strategy_class=B1Strategy,
    params=(...),
    required_data=('shanghai_index',),
)
```

Do not change existing strategies that do not need auxiliary feeds; they should use the default empty tuple.

- [ ] **Step 4: Run the tests again**

Run: `python -m pytest -q tests/test_strategies.py`

Expected: still FAIL, but only because `citic_wave` is not registered yet. The `required_data` field should no longer be the failing point.

- [ ] **Step 5: Commit the metadata change**

Run:

```bash
git add strategies/base.py strategies/b1_strategy.py tests/test_strategies.py
git commit -m "refactor: add strategy feed requirements metadata"
```

### Task 2: Cached Loaders for the Securities ETF and Market Turnover

**Files:**
- Modify: `backtest/data_loader.py`
- Create: `tests/test_data_loader_strategy_feeds.py`

- [ ] **Step 1: Write the failing loader tests**

Create `tests/test_data_loader_strategy_feeds.py`:

```python
import pandas as pd

from backtest.data_loader import (
    INDEX_STANDARD_COLUMNS,
    load_market_turnover_data,
    load_security_etf_data,
)


def test_load_security_etf_data_normalizes_columns(monkeypatch):
    fake = pd.DataFrame({
        'date': pd.to_datetime(['2024-01-02', '2024-01-03']),
        'open': [1.0, 1.1],
        'high': [1.1, 1.2],
        'low': [0.9, 1.0],
        'close': [1.05, 1.15],
        'volume': [1000, 1200],
        'amount': [10000, 12000],
    })
    monkeypatch.setattr(
        'backtest.data_loader.ak.fund_etf_hist_sina',
        lambda symbol='sh512880': fake.copy(),
    )
    df = load_security_etf_data('20240101', '20240131')
    assert df.columns.tolist() == INDEX_STANDARD_COLUMNS
    assert len(df) == 2


def test_load_market_turnover_data_returns_price_like_frame(monkeypatch):
    monkeypatch.setattr(
        'backtest.data_loader._fetch_sse_turnover',
        lambda date: 3200.0,
    )
    monkeypatch.setattr(
        'backtest.data_loader._fetch_szse_turnover',
        lambda date: 4100.0,
    )
    df = load_market_turnover_data('20240102', '20240103')
    assert df.columns.tolist() == ['date', 'open', 'high', 'low', 'close', 'volume']
    assert df['close'].tolist() == [7300.0, 7300.0]
    assert (df['open'] == df['close']).all()
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `python -m pytest -q tests/test_data_loader_strategy_feeds.py`

Expected: FAIL because the new loader functions and helper fetchers do not exist.

- [ ] **Step 3: Implement the ETF and turnover loaders**

Add the following helpers to `backtest/data_loader.py`:

```python
def load_security_etf_data(start, end, symbol='sh512880'):
    start, end = resolve_date_range(start, end)
    os.makedirs(_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(_CACHE_DIR, f'{symbol}_security_etf_{start}_{end}.csv')
    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path)
        df['date'] = pd.to_datetime(df['date'])
        return df[INDEX_STANDARD_COLUMNS].copy()

    df = ak.fund_etf_hist_sina(symbol=symbol)
    df['date'] = pd.to_datetime(df['date'])
    mask = (df['date'] >= pd.to_datetime(start)) & (df['date'] <= pd.to_datetime(end))
    df = df.loc[mask, ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']].copy()
    df.to_csv(cache_path, index=False)
    return df


def _fetch_sse_turnover(date_text: str) -> float:
    df = ak.stock_sse_deal_daily(date=date_text)
    row = df.loc[df['单日情况'] == '成交金额', '股票']
    return float(row.iloc[0])


def _fetch_szse_turnover(date_text: str) -> float:
    df = ak.stock_szse_summary(date=date_text)
    row = df.loc[df['证券类别'] == '股票', '成交金额']
    return float(row.iloc[0]) / 100000000.0


def load_market_turnover_data(start, end):
    start, end = resolve_date_range(start, end)
    os.makedirs(_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(_CACHE_DIR, f'market_turnover_{start}_{end}.csv')
    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path)
        df['date'] = pd.to_datetime(df['date'])
        return df[STANDARD_COLUMNS].copy()

    rows = []
    for dt in pd.date_range(start=pd.to_datetime(start), end=pd.to_datetime(end), freq='B'):
        date_text = dt.strftime('%Y%m%d')
        total_turnover = _fetch_sse_turnover(date_text) + _fetch_szse_turnover(date_text)
        rows.append({
            'date': dt,
            'open': total_turnover,
            'high': total_turnover,
            'low': total_turnover,
            'close': total_turnover,
            'volume': 0.0,
        })
    df = pd.DataFrame(rows)
    df.to_csv(cache_path, index=False)
    return df
```

Keep these functions near the existing loader functions so cache behavior stays in one file.

- [ ] **Step 4: Run the new loader tests**

Run: `python -m pytest -q tests/test_data_loader_strategy_feeds.py`

Expected: PASS.

- [ ] **Step 5: Commit the loader support**

Run:

```bash
git add backtest/data_loader.py tests/test_data_loader_strategy_feeds.py
git commit -m "feat: add sector and turnover data loaders"
```

### Task 3: Implement the `citic_wave` Strategy

**Files:**
- Create: `strategies/citic_wave.py`
- Modify: `strategies/registry.py`
- Modify: `tests/test_strategies.py`
- Create: `tests/test_citic_wave_strategy.py`

- [ ] **Step 1: Write the failing strategy tests**

Create `tests/test_citic_wave_strategy.py`:

```python
import inspect

from strategies.citic_wave import CITIC_WAVE_STRATEGY_SPEC, CiticWaveStrategy


def test_citic_wave_spec_defaults():
    assert CITIC_WAVE_STRATEGY_SPEC.id == 'citic_wave'
    assert CITIC_WAVE_STRATEGY_SPEC.required_data == (
        'shanghai_index',
        'security_etf',
        'market_turnover',
    )
    assert CITIC_WAVE_STRATEGY_SPEC.defaults['market_ma_long'] == 120
    assert CITIC_WAVE_STRATEGY_SPEC.defaults['sector_ma'] == 60


def test_citic_wave_has_four_feed_contract():
    source = inspect.getsource(CiticWaveStrategy.__init__)
    assert 'self.data_market = self.datas[1]' in source
    assert 'self.data_sector = self.datas[2]' in source
    assert 'self.data_turnover = self.datas[3]' in source


def test_citic_wave_has_breakout_and_pullback_entries():
    source = inspect.getsource(CiticWaveStrategy.next)
    assert 'breakout_signal' in source
    assert 'pullback_signal' in source
    assert 'self.buy(size=size)' in source


def test_citic_wave_has_three_exit_modes():
    source = inspect.getsource(CiticWaveStrategy.next)
    assert 'stop_loss_price' in source
    assert 'self.data.close[0] < self.ma_exit[0]' in source
    assert 'self.bar_executed' in source
```

- [ ] **Step 2: Run the tests to verify failure**

Run: `python -m pytest -q tests/test_citic_wave_strategy.py tests/test_strategies.py`

Expected: FAIL because `strategies/citic_wave.py` does not exist and the registry does not expose the new strategy.

- [ ] **Step 3: Implement the new strategy**

Create `strategies/citic_wave.py`:

```python
import backtrader as bt

from strategies.base import StrategyParamSpec, StrategySpec


class CiticWaveStrategy(bt.Strategy):
    params = (
        ('market_ma_long', 120),
        ('sector_ma', 60),
        ('turnover_ma', 20),
        ('breakout_window', 40),
        ('pullback_lookback', 10),
        ('volume_ma', 20),
        ('stop_loss_pct', 0.06),
        ('atr_period', 14),
        ('atr_multiplier', 2.0),
        ('max_hold_days', 30),
        ('risk_percent', 0.95),
    )

    def __init__(self):
        self.data_stock = self.datas[0]
        self.data_market = self.datas[1]
        self.data_sector = self.datas[2]
        self.data_turnover = self.datas[3]

        self.market_ma = bt.ind.SMA(self.data_market.close, period=self.p.market_ma_long)
        self.sector_ma_line = bt.ind.SMA(self.data_sector.close, period=self.p.sector_ma)
        self.turnover_ma_line = bt.ind.SMA(self.data_turnover.close, period=self.p.turnover_ma)

        self.ma_fast = bt.ind.SMA(self.data_stock.close, period=10)
        self.ma_mid = bt.ind.SMA(self.data_stock.close, period=20)
        self.ma_slow = bt.ind.SMA(self.data_stock.close, period=60)
        self.ma_exit = bt.ind.SMA(self.data_stock.close, period=20)
        self.vol_ma = bt.ind.SMA(self.data_stock.volume, period=self.p.volume_ma)
        self.atr = bt.ind.ATR(self.data_stock, period=self.p.atr_period)
        self.highest_breakout = bt.ind.Highest(self.data_stock.high, period=self.p.breakout_window)
        self.lowest_pullback = bt.ind.Lowest(self.data_stock.low, period=self.p.pullback_lookback)

        self.entry_price = None
        self.bar_executed = None

    def _market_filter_passed(self):
        return (
            self.data_market.close[0] > self.market_ma[0]
            and self.data_sector.close[0] > self.sector_ma_line[0]
            and self.data_turnover.close[0] > self.turnover_ma_line[0]
        )

    def _position_size(self):
        cash_for_trade = self.broker.getcash() * self.p.risk_percent
        return int(cash_for_trade / self.data_stock.close[0])

    def next(self):
        if len(self.datas[0]) < max(self.p.market_ma_long, self.p.breakout_window, 60):
            return

        if self.position:
            stop_loss_price = max(
                self.entry_price * (1.0 - self.p.stop_loss_pct),
                self.entry_price - self.atr[0] * self.p.atr_multiplier,
            )
            held_bars = len(self) - self.bar_executed
            if self.data.close[0] <= stop_loss_price:
                self.close()
                return
            if self.data.close[0] < self.ma_exit[0] and self.ma_fast[0] < self.ma_mid[0]:
                self.close()
                return
            if held_bars >= self.p.max_hold_days:
                self.close()
                return
            return

        if not self._market_filter_passed():
            return

        breakout_signal = (
            self.data_stock.close[0] >= self.highest_breakout[-1]
            and self.data_stock.volume[0] > self.vol_ma[0]
            and self.data_stock.close[0] > self.ma_mid[0]
            and self.data_stock.close[0] > self.ma_slow[0]
        )
        pullback_signal = (
            self.data_stock.close[0] > self.ma_slow[0]
            and self.lowest_pullback[0] >= self.ma_slow[0]
            and self.data_stock.close[-1] <= self.ma_mid[-1]
            and self.data_stock.close[0] > self.ma_mid[0]
            and self.data_stock.volume[0] > self.vol_ma[0]
        )

        if breakout_signal or pullback_signal:
            size = self._position_size()
            if size > 0:
                self.buy(size=size)
                self.entry_price = self.data_stock.close[0]
                self.bar_executed = len(self)


CITIC_WAVE_STRATEGY_SPEC = StrategySpec(
    id='citic_wave',
    name='Citic Wave',
    description='Market-filtered breakout and pullback swing strategy for CITIC Securities.',
    strategy_class=CiticWaveStrategy,
    params=(
        StrategyParamSpec('market_ma_long', 'Market MA', 'int', 120),
        StrategyParamSpec('sector_ma', 'Sector MA', 'int', 60),
        StrategyParamSpec('turnover_ma', 'Turnover MA', 'int', 20),
        StrategyParamSpec('breakout_window', 'Breakout Window', 'int', 40),
        StrategyParamSpec('pullback_lookback', 'Pullback Window', 'int', 10),
        StrategyParamSpec('volume_ma', 'Volume MA', 'int', 20),
        StrategyParamSpec('stop_loss_pct', 'Stop Loss %', 'float', 0.06),
        StrategyParamSpec('atr_period', 'ATR Period', 'int', 14),
        StrategyParamSpec('atr_multiplier', 'ATR Multiple', 'float', 2.0),
        StrategyParamSpec('max_hold_days', 'Max Hold Days', 'int', 30),
    ),
    required_data=('shanghai_index', 'security_etf', 'market_turnover'),
)
```

Register it in `strategies/registry.py`:

```python
from strategies.citic_wave import CiticWaveStrategy, CITIC_WAVE_STRATEGY_SPEC

_STRATEGIES = {
    B1_STRATEGY_SPEC.id: B1_STRATEGY_SPEC,
    SWING_MA_BOLL_SPEC.id: SWING_MA_BOLL_SPEC,
    BOLLINGER_REVERSAL_SPEC.id: BOLLINGER_REVERSAL_SPEC,
    CITIC_WAVE_STRATEGY_SPEC.id: CITIC_WAVE_STRATEGY_SPEC,
}
```

- [ ] **Step 4: Run the strategy tests**

Run: `python -m pytest -q tests/test_citic_wave_strategy.py tests/test_strategies.py`

Expected: PASS.

- [ ] **Step 5: Commit the new strategy**

Run:

```bash
git add strategies/citic_wave.py strategies/registry.py tests/test_citic_wave_strategy.py tests/test_strategies.py
git commit -m "feat: add citic wave strategy"
```

### Task 4: Wire Auxiliary Feeds Into Service and CLI Backtests

**Files:**
- Modify: `backtest/service.py`
- Modify: `backtest/run_backtest.py`
- Modify: `tests/test_backtest_service.py`

- [ ] **Step 1: Write the failing backtest service test**

Add this to `tests/test_backtest_service.py`:

```python
def test_run_backtest_service_adds_required_feeds_for_citic_wave(monkeypatch):
    from backtest.run_backtest import generate_synthetic_data

    stock_df = generate_synthetic_data(start='20240101', end='20240630')
    aux_df = stock_df.copy()
    aux_df['amount'] = 1.0

    monkeypatch.setattr('backtest.service.load_market_data', lambda s, st, e: stock_df.copy())
    monkeypatch.setattr('backtest.service.load_shanghai_composite', lambda st, e: aux_df.copy())
    monkeypatch.setattr('backtest.service.load_security_etf_data', lambda st, e: aux_df.copy())
    monkeypatch.setattr('backtest.service.load_market_turnover_data', lambda st, e: stock_df.copy())

    request = BacktestRequest(
        symbol='600030',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=False,
        strategy_id='citic_wave',
    )
    result = run_backtest_service(request)

    assert result.symbol == '600030'
    assert result.final_value > 0
```

- [ ] **Step 2: Run the test to verify failure**

Run: `python -m pytest -q tests/test_backtest_service.py::test_run_backtest_service_adds_required_feeds_for_citic_wave -v`

Expected: FAIL because the service does not import or add the required auxiliary feeds.

- [ ] **Step 3: Implement multi-feed wiring**

Update the imports at the top of `backtest/service.py`:

```python
from backtest.data_loader import (
    load_market_data,
    load_market_turnover_data,
    load_security_etf_data,
    load_shanghai_composite,
    resolve_date_range,
)
```

Add a helper in `backtest/service.py`:

```python
def _load_required_feed_frames(required_data: tuple[str, ...], start: str, end: str) -> list[pd.DataFrame]:
    frames = []
    for feed_id in required_data:
        if feed_id == 'shanghai_index':
            frame = load_shanghai_composite(start, end)
        elif feed_id == 'security_etf':
            frame = load_security_etf_data(start, end)
        elif feed_id == 'market_turnover':
            frame = load_market_turnover_data(start, end)
        else:
            raise ValueError(f'Unknown required feed: {feed_id}')
        if frame is None or frame.empty:
            raise RuntimeError(f'Missing required feed: {feed_id}')
        frames.append(frame)
    return frames
```

Use it inside `run_backtest_service`:

```python
    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    for frame in _load_required_feed_frames(spec.required_data, req.start, req.end):
        cerebro.adddata(bt.feeds.PandasData(dataname=frame, datetime=0))
```

Mirror the same logic in `backtest/run_backtest.py` by adding a small helper imported from `backtest.service` instead of duplicating the branch logic.

- [ ] **Step 4: Run the backtest service tests**

Run: `python -m pytest -q tests/test_backtest_service.py -q`

Expected: PASS, including the new `citic_wave` multi-feed case and the existing service payload tests.

- [ ] **Step 5: Commit the service wiring**

Run:

```bash
git add backtest/service.py backtest/run_backtest.py tests/test_backtest_service.py
git commit -m "feat: wire auxiliary feeds into backtests"
```

### Task 5: Reproducible Parameter Search and Report

**Files:**
- Create: `scripts/search_citic_wave.py`
- Modify: `data/results/citic_securities_backtest_report.md`

- [ ] **Step 1: Write the search script**

Create `scripts/search_citic_wave.py`:

```python
import itertools
from pathlib import Path

from backtest.service import BacktestRequest, run_backtest_service


TRAIN_END = '20241231'
VALID_START = '20250101'
SYMBOL = '600030'
START = '20210531'
END = '20260529'


def run_once(start, end, **params):
    request = BacktestRequest(
        symbol=SYMBOL,
        start=start,
        end=end,
        cash=100000.0,
        use_market_filter=False,
        strategy_id='citic_wave',
        strategy_params=params,
    )
    return run_backtest_service(request)


def main():
    rows = []
    for breakout_window, stop_loss_pct, atr_multiplier, max_hold_days in itertools.product(
        [40, 60],
        [0.05, 0.06, 0.08],
        [1.5, 2.0, 2.5],
        [20, 30, 40],
    ):
        params = {
            'breakout_window': breakout_window,
            'stop_loss_pct': stop_loss_pct,
            'atr_multiplier': atr_multiplier,
            'max_hold_days': max_hold_days,
        }
        train = run_once(START, TRAIN_END, **params)
        valid = run_once(VALID_START, END, **params)
        full = run_once(START, END, **params)
        rows.append({
            'params': params,
            'train_return_pct': train.total_return_pct,
            'valid_return_pct': valid.total_return_pct,
            'full_return_pct': full.total_return_pct,
            'full_max_drawdown_pct': full.max_drawdown_pct,
        })

    rows.sort(key=lambda row: (row['valid_return_pct'], row['full_return_pct']), reverse=True)
    out = Path('data/results/citic_wave_search.txt')
    out.write_text('\n'.join(str(row) for row in rows[:20]), encoding='utf-8')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run the search script**

Run: `python scripts/search_citic_wave.py`

Expected: exit code `0` and a new file `data/results/citic_wave_search.txt`.

- [ ] **Step 3: Write the final markdown report**

Update `data/results/citic_securities_backtest_report.md` with the new best `citic_wave` result and compare it against the previous `swing_ma_boll` baseline using this structure:

```markdown
## 中信证券专用策略结果

- 策略：`citic_wave`
- 最优参数：`...`
- 全样本收益：`...`
- 验证期收益：`...`
- 全样本最大回撤：`...`
- 是否达到目标：`是/否`

## 与旧基线对比

- 旧基线：`swing_ma_boll`
- 旧基线全样本收益：`32.48%`
- 旧基线验证期收益：`5.34%`
- 旧基线全样本最大回撤：`27.44%`
```

- [ ] **Step 4: Run the focused regression tests**

Run:

```bash
python -m pytest -q tests/test_strategies.py tests/test_data_loader_strategy_feeds.py tests/test_citic_wave_strategy.py tests/test_backtest_service.py
```

Expected: PASS.

- [ ] **Step 5: Commit the script and updated report**

Run:

```bash
git add scripts/search_citic_wave.py data/results/citic_securities_backtest_report.md
git commit -m "feat: evaluate citic wave strategy"
```

## Self-Review

- Spec coverage:
  - New strategy design: covered by Task 3.
  - Extra market and sector data: covered by Task 2.
  - Backtest entry point wiring: covered by Task 4.
  - Reproducible report: covered by Task 5.
- Placeholder scan:
  - No unresolved placeholders or deferred implementation markers remain.
- Type consistency:
  - Strategy id is consistently `citic_wave`.
  - Auxiliary feed ids are consistently `shanghai_index`, `security_etf`, and `market_turnover`.
  - Loader names are consistently `load_security_etf_data` and `load_market_turnover_data`.
