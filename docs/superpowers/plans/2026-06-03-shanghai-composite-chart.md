# 上证指数 K 线 + 技术指标板块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在回测结果页面新增两个 panel：上证指数 K 线 + MA + BOLL（每个独立 toggle），以及技术指标子图（MACD/KDJ/交易量/交易额下拉切换）。

**Architecture:** 后端在 `run_backtest_service` 里独立加载上证指数 OHLCV+amount（不经 Cerebro），挂到 `BacktestResult.index_data` 字段。前端用 `useMemo` 算 MA/MACD/KDJ/BOLL 全部指标，ComposedChart 渲染两个 panel。指标公式用 Python 实现作为参考测试 + TypeScript port 到生产代码。

**Tech Stack:** Python 3 + pytest、FastAPI、Recharts、React + Vite + TypeScript。

---

## File Structure

| 文件 | 责任 |
|---|---|
| `backtest/data_loader.py` | 扩展 `load_shanghai_composite`：加 `amount` 列、引入 `INDEX_STANDARD_COLUMNS`、改缓存 schema 校验 |
| `backtest/chart_indicators.py` | **新增**：纯函数 `calc_ma` / `calc_boll` / `calc_macd` / `calc_kdj`（数学参考实现 + pytest 目标） |
| `backtest/service.py` | `run_backtest_service` 加载 `index_df` 并写入 `BacktestResult.index_data`；`BacktestResult` 加 `index_data` 字段 |
| `web/src/indicators.ts` | **新增**：TypeScript 端口（生产代码） |
| `web/src/types.ts` | `BacktestResult` 接口加 `index_data` |
| `web/src/App.tsx` | 新增 2 个 panel、状态、useMemo、复用 `CandleShape` |
| `tests/test_chart_indicators.py` | **新增**：4 个指标的纯函数单测（注意：与 `test_indicators.py` 不同，那个是市场评分） |
| `tests/test_backtest_service.py` | 加一个测试：`run_backtest_service` 返回结果含 `index_data` |

`backtest/chart_indicators.py` 不是生产路径（前端用 TS 算指标），是「数学规约 + 锁死预期值」的角色。改 `chart_indicators.py` 时必须同步改 `web/src/indicators.ts`。

---

## Task 1: 扩展 data_loader.py 让上证指数数据带 amount 列

**Files:**
- Modify: `backtest/data_loader.py`
- Test: `tests/test_data_loader_index.py` （新增）

- [ ] **Step 1: 写失败测试 —— INDEX_STANDARD_COLUMNS 包含 amount**

在 `tests/test_data_loader_index.py` 写入：

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.data_loader import INDEX_STANDARD_COLUMNS, _AKSHARE_COLUMN_MAP


def test_index_standard_columns_includes_amount():
    assert 'amount' in INDEX_STANDARD_COLUMNS
    assert 'date' in INDEX_STANDARD_COLUMNS
    assert 'open' in INDEX_STANDARD_COLUMNS
    assert 'close' in INDEX_STANDARD_COLUMNS
    assert 'volume' in INDEX_STANDARD_COLUMNS
    assert len(INDEX_STANDARD_COLUMNS) == 7


def test_akshare_amount_mapping_exists():
    assert _AKSHARE_COLUMN_MAP['成交额'] == 'amount'
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_data_loader_index.py -v`
Expected: FAIL with `ImportError: cannot import name 'INDEX_STANDARD_COLUMNS'`

- [ ] **Step 3: 实现：在 data_loader.py 加常量和映射**

编辑 `backtest/data_loader.py`：

1. 在 `STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume']` 下方新增：
   ```python
   INDEX_STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
   ```
2. 在 `_AKSHARE_COLUMN_MAP` 字典里加一行：
   ```python
   '成交额': 'amount',
   ```
3. 在 `load_shanghai_composite` 里，把
   ```python
   if set(df.columns) != set(STANDARD_COLUMNS):
       continue
   ```
   改为：
   ```python
   if set(df.columns) != set(INDEX_STANDARD_COLUMNS):
       continue
   ```
4. 在同一函数的 df 切片之前（df.to_csv 之前），`STANDARD_COLUMNS` 替换为 `INDEX_STANDARD_COLUMNS`：
   ```python
   df = df[list(_AKSHARE_COLUMN_MAP.keys())]
   df.columns = INDEX_STANDARD_COLUMNS
   ```
   （注意：此时 `STANDARD_COLUMNS` 和 `INDEX_STANDARD_COLUMNS` 长度不同——前 6 列相同，但 INDEX 多 amount。AkShare 返回的列按 `_AKSHARE_COLUMN_MAP` 顺序重新命名后，新列名按 `INDEX_STANDARD_COLUMNS` 顺序排。）

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_data_loader_index.py -v`
Expected: PASS（2 tests passed）

- [ ] **Step 5: 运行所有测试，确认未破坏现有功能**

Run: `python -m pytest -q tests/`
Expected: All tests pass. (特别注意 `test_backtest_service.py` —— 如果它 mock 了 `load_market_data` 但真调用了 `load_shanghai_composite`，会失败。本次不应影响，因为 test_backtest_service.py 当前没有 mock sh000001。)

- [ ] **Step 6: 提交**

```bash
git add backtest/data_loader.py tests/test_data_loader_index.py
git commit -m "feat(backtest): include amount column in shanghai composite data"
```

---

## Task 2: 实现 Python 端指标公式（参考实现）

**Files:**
- Create: `backtest/chart_indicators.py`
- Create: `tests/test_chart_indicators.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_chart_indicators.py` 写入：

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import pytest

from backtest.chart_indicators import calc_ma, calc_boll, calc_macd, calc_kdj


# ── calc_ma ──────────────────────────────────────────────

class TestCalcMa:
    def test_period_5_first_four_null(self):
        closes = [10, 11, 12, 13, 14, 15]
        result = calc_ma(closes, 5)
        assert result[:4] == [None, None, None, None]
        assert result[4] == pytest.approx(12.0)
        assert result[5] == pytest.approx(13.0)

    def test_period_1_returns_closes(self):
        closes = [10, 11, 12]
        result = calc_ma(closes, 1)
        assert result == closes

    def test_short_series_returns_all_none(self):
        assert calc_ma([1, 2], 5) == [None, None]

    def test_empty_series(self):
        assert calc_ma([], 5) == []


# ── calc_boll ─────────────────────────────────────────────

class TestCalcBoll:
    def test_first_19_null(self):
        closes = [float(i) for i in range(25)]
        upper, mid, lower = calc_boll(closes, period=20, num_std=2.0)
        for i in range(19):
            assert upper[i] is None
            assert mid[i] is None
            assert lower[i] is None

    def test_mid_equals_ma20(self):
        closes = [float(i) for i in range(25)]
        upper, mid, lower = calc_boll(closes, period=20, num_std=2.0)
        assert mid[19] == pytest.approx(sum(closes[:20]) / 20)
        assert mid[20] == pytest.approx(sum(closes[1:21]) / 20)

    def test_upper_above_mid_above_lower(self):
        closes = [10, 12, 11, 13, 15, 14, 16, 18, 17, 19, 21, 20, 22, 24, 23, 25, 27, 26, 28, 30, 29]
        upper, mid, lower = calc_boll(closes, period=20, num_std=2.0)
        for i in range(20, len(closes)):
            assert upper[i] > mid[i] > lower[i]

    def test_constant_series_upper_equals_mid_equals_lower(self):
        closes = [100.0] * 25
        upper, mid, lower = calc_boll(closes, period=20, num_std=2.0)
        for i in range(20, len(closes)):
            assert upper[i] == pytest.approx(100.0)
            assert lower[i] == pytest.approx(100.0)


# ── calc_macd ─────────────────────────────────────────────

class TestCalcMacd:
    def test_first_34_null(self):
        closes = [float(i) for i in range(40)]
        dif, dea, macd = calc_macd(closes, fast=12, slow=26, signal=9)
        # DIF null until index 25, DEA null until DEA seed ready, MACD null if either null
        for i in range(25):
            assert dif[i] is None
        for i in range(33):  # 25 + 8 (signal - 1)
            assert dea[i] is None
        for i in range(34):
            assert macd[i] is None

    def test_dif_at_index_25_equals_zero(self):
        # 线性递增序列的 EMA12 与 EMA26 在 i=25 之后才第一次都有值
        closes = [float(i) for i in range(40)]
        dif, dea, macd = calc_macd(closes, fast=12, slow=26, signal=9)
        # 在 i=25，DIF = EMA12[25] - EMA26[25]
        # EMA12[11] 用 SMA 作为种子
        assert dif[25] is not None

    def test_macd_bar_is_dif_minus_dea_times_2(self):
        closes = [100 + i * 0.5 for i in range(60)]
        dif, dea, macd = calc_macd(closes, fast=12, slow=26, signal=9)
        for i in range(34, 60):
            if dif[i] is not None and dea[i] is not None:
                assert macd[i] == pytest.approx((dif[i] - dea[i]) * 2, abs=1e-9)


# ── calc_kdj ─────────────────────────────────────────────

class TestCalcKdj:
    def test_first_8_null(self):
        highs = [float(i) for i in range(20)]
        lows = [float(i) - 1 for i in range(20)]
        closes = [float(i) - 0.5 for i in range(20)]
        k, d, j = calc_kdj(highs, lows, closes, n=9, k_period=3, d_period=3)
        for i in range(8):
            assert k[i] is None
            assert d[i] is None
            assert j[i] is None

    def test_k_starts_at_50_when_no_prev(self):
        highs = [11.0] * 9
        lows = [9.0] * 9
        closes = [10.0] * 9
        k, d, j = calc_kdj(highs, lows, closes, n=9, k_period=3, d_period=3)
        # RSV = (close - low) / (high - low) = (10-9)/(11-9) = 0.5
        # K = 2/3 * 50 + 1/3 * 50 = 50 (default prev = 50)
        assert k[8] == pytest.approx(50.0)

    def test_j_equals_3k_minus_2d(self):
        highs = [float(i) for i in range(20)]
        lows = [float(i) - 2 for i in range(20)]
        closes = [float(i) - 1 for i in range(20)]
        k, d, j = calc_kdj(highs, lows, closes, n=9, k_period=3, d_period=3)
        for i in range(8, 20):
            if k[i] is not None and d[i] is not None:
                assert j[i] == pytest.approx(3 * k[i] - 2 * d[i])
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_chart_indicators.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backtest.chart_indicators'`

- [ ] **Step 3: 实现指标公式**

创建 `backtest/chart_indicators.py`：

```python
"""K 线图技术指标纯函数（参考实现）。

本模块是「数学规约」，生产环境用 web/src/indicators.ts 的 TypeScript 端口。
公式必须保持一致 —— 改这里要同步改 TS 文件。
"""

from __future__ import annotations

from typing import Sequence


def calc_ma(closes: Sequence[float], period: int) -> list[float | None]:
    """简单移动平均。不足 period 时返回 None。"""
    if period <= 0:
        raise ValueError(f'period must be positive, got {period}')
    if not closes:
        return []
    result: list[float | None] = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            s = sum(closes[i - period + 1 : i + 1])
            result.append(s / period)
    return result


def _ema(values: Sequence[float], period: int) -> list[float | None]:
    """EMA。前 period-1 个返回 None，第 period 个用 SMA 作为种子。"""
    if period <= 0:
        raise ValueError(f'period must be positive, got {period}')
    if not values:
        return []
    k = 2.0 / (period + 1)
    result: list[float | None] = []
    prev_sma: float | None = None
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
            continue
        if prev_sma is None:
            s = sum(values[i - period + 1 : i + 1])
            prev_sma = s / period
        else:
            prev_sma = values[i] * k + prev_sma * (1 - k)
        result.append(prev_sma)
    return result


def calc_boll(
    closes: Sequence[float], period: int = 20, num_std: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """布林带：返回 (上轨, 中轨, 下轨)。中轨=MA。"""
    if period <= 0:
        raise ValueError(f'period must be positive, got {period}')
    if not closes:
        return [], [], []
    mid = calc_ma(closes, period)
    upper: list[float | None] = []
    lower: list[float | None] = []
    for i in range(len(closes)):
        if i < period - 1 or mid[i] is None:
            upper.append(None)
            lower.append(None)
            continue
        window = closes[i - period + 1 : i + 1]
        mean = mid[i]
        var = sum((x - mean) ** 2 for x in window) / period
        std = var ** 0.5
        upper.append(mean + num_std * std)
        lower.append(mean - num_std * std)
    return upper, mid, lower


def calc_macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """MACD：DIF=EMA12-EMA26, DEA=DIF的9日EMA, MACD柱=(DIF-DEA)*2。"""
    if not closes:
        return [], [], []
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif: list[float | None] = [
        (ef - es) if ef is not None and es is not None else None
        for ef, es in zip(ema_fast, ema_slow)
    ]
    # DEA 是 DIF 的 EMA，但只在 DIF 有值时计算（无值的位置用 0 占位让 EMA 走，但最终输出 null）
    dif_for_ema = [d if d is not None else 0.0 for d in dif]
    dea_raw = _ema(dif_for_ema, signal)
    dea: list[float | None] = [
        dea_raw[i] if dif[i] is not None and i >= slow - 1 + signal - 1 else None
        for i in range(len(closes))
    ]
    macd: list[float | None] = [
        (d - e) * 2 if d is not None and e is not None else None
        for d, e in zip(dif, dea)
    ]
    return dif, dea, macd


def calc_kdj(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    n: int = 9,
    k_period: int = 3,
    d_period: int = 3,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """KDJ。默认 K/D 周期=3（即 K_t = 2/3 * K_{t-1} + 1/3 * RSV_t）。"""
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError('highs, lows, closes must have equal length')
    if not closes:
        return [], [], []
    rsv: list[float | None] = []
    for i in range(len(closes)):
        if i < n - 1:
            rsv.append(None)
            continue
        hh = max(highs[i - n + 1 : i + 1])
        ll = min(lows[i - n + 1 : i + 1])
        rng = hh - ll
        rsv.append((closes[i] - ll) / rng * 100 if rng != 0 else 50.0)
    k_alpha = 1.0 / k_period
    d_alpha = 1.0 / d_period
    k: list[float | None] = []
    d: list[float | None] = []
    prev_k = 50.0
    prev_d = 50.0
    for i in range(len(closes)):
        if rsv[i] is None:
            k.append(None)
            d.append(None)
            continue
        prev_k = prev_k * (1 - k_alpha) + rsv[i] * k_alpha
        prev_d = prev_d * (1 - d_alpha) + prev_k * d_alpha
        k.append(prev_k)
        d.append(prev_d)
    j: list[float | None] = [
        (3 * kk - 2 * dd) if kk is not None and dd is not None else None
        for kk, dd in zip(k, d)
    ]
    return k, d, j
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_chart_indicators.py -v`
Expected: All tests pass (16 tests)

- [ ] **Step 5: 提交**

```bash
git add backtest/chart_indicators.py tests/test_chart_indicators.py
git commit -m "feat(backtest): add chart indicator formulas (MA/BOLL/MACD/KDJ)"
```

---

## Task 3: BacktestResult 加 index_data 字段并在 service 里加载

**Files:**
- Modify: `backtest/service.py`
- Test: `tests/test_backtest_service.py`（加一个新测试）

- [ ] **Step 1: 写失败测试**

在 `tests/test_backtest_service.py` 末尾追加：

```python
def test_index_data_is_populated_when_loader_returns_df(monkeypatch):
    """load_shanghai_composite 返回有效 DataFrame 时，result.index_data 应有 OHLCV+amount。"""
    from backtest.run_backtest import generate_synthetic_data
    from datetime import datetime
    import pandas as pd

    stock_df = generate_synthetic_data(start='20240101', end='20240630')

    dates = pd.date_range('20240101', periods=len(stock_df), freq='B')
    index_df = pd.DataFrame({
        'date': dates,
        'open': [3000.0] * len(stock_df),
        'high': [3050.0] * len(stock_df),
        'low':  [2980.0] * len(stock_df),
        'close':[3020.0] * len(stock_df),
        'volume': [1e9] * len(stock_df),
        'amount': [3e12] * len(stock_df),
    })

    monkeypatch.setattr('backtest.service.load_market_data', lambda s, st, e: stock_df.copy())
    monkeypatch.setattr('backtest.service.load_shanghai_composite', lambda st, e: index_df.copy())

    request = BacktestRequest(
        symbol='000001', start='20240101', end='20240630',
        cash=100000.0, use_market_filter=False,
    )
    result = run_backtest_service(request)

    assert result.index_data, 'index_data should be populated'
    assert len(result.index_data) == len(stock_df)
    first = result.index_data[0]
    assert set(first.keys()) == {'date', 'open', 'high', 'low', 'close', 'volume', 'amount'}
    assert first['date'].isdigit() and len(first['date']) == 8
    assert first['amount'] == 3e12


def test_index_data_empty_when_loader_returns_none(monkeypatch):
    """load_shanghai_composite 返回 None 时，index_data 为空 list，不抛错。"""
    from backtest.run_backtest import generate_synthetic_data
    stock_df = generate_synthetic_data(start='20240101', end='20240630')
    monkeypatch.setattr('backtest.service.load_market_data', lambda s, st, e: stock_df.copy())
    monkeypatch.setattr('backtest.service.load_shanghai_composite', lambda st, e: None)

    request = BacktestRequest(
        symbol='000001', start='20240101', end='20240630',
        cash=100000.0, use_market_filter=False,
    )
    result = run_backtest_service(request)

    assert result.index_data == []
    assert result.final_value > 0  # 回测本身成功
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_backtest_service.py::test_index_data_is_populated_when_loader_returns_df tests/test_backtest_service.py::test_index_data_empty_when_loader_returns_none -v`
Expected: FAIL with `AttributeError: 'BacktestResult' object has no attribute 'index_data'`

- [ ] **Step 3: 修改 service.py —— 加 import、字段、加载逻辑**

编辑 `backtest/service.py`：

1. 修改 import：
   ```python
   from backtest.data_loader import load_market_data, load_shanghai_composite, resolve_date_range
   ```

2. 在 `BacktestResult` dataclass 里加字段（紧跟 `price_data` 之后）：
   ```python
   price_data: list[dict[str, Any]] = field(default_factory=list)
   index_data: list[dict[str, Any]] = field(default_factory=list)  # 上证指数 OHLCV+amount
   ```

3. 在 `run_backtest_service` 里，`df = load_market_data(...)` 之后立即加入（注意：放在 `_market_score_payload` 调用之后、`cerebro = bt.Cerebro()` 之前）：
   ```python
   # 加载上证指数数据（不经过 Cerebro，独立缓存）
   index_data: list[dict[str, Any]] = []
   index_df = load_shanghai_composite(req.start, req.end)
   if index_df is not None and not index_df.empty:
       for _, row in index_df.iterrows():
           index_data.append({
               'date': row['date'].strftime('%Y%m%d'),
               'open': float(row['open']),
               'high': float(row['high']),
               'low': float(row['low']),
               'close': float(row['close']),
               'volume': float(row['volume']),
               'amount': float(row['amount']),
           })
   ```

4. 在 `return BacktestResult(...)` 里追加 `index_data=index_data`：
   ```python
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
       price_data=strategy.analyzers.price.get_analysis(),
       index_data=index_data,
   )
   ```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_backtest_service.py -v`
Expected: All tests pass (5 tests: 3 existing + 2 new)

- [ ] **Step 5: 运行所有测试，确认无回归**

Run: `python -m pytest -q tests/`
Expected: All tests pass

- [ ] **Step 6: 提交**

```bash
git add backtest/service.py tests/test_backtest_service.py
git commit -m "feat(backtest): populate index_data in BacktestResult"
```

---

## Task 4: TypeScript 端口指标公式

**Files:**
- Create: `web/src/indicators.ts`

- [ ] **Step 1: 创建 web/src/indicators.ts（参考 Python 公式，逐字对齐）**

写入：

```typescript
/**
 * K 线图技术指标公式（生产代码）。
 *
 * 与 backtest/chart_indicators.py 一一对应。
 * 改这边要同步改 Python 端的公式与测试。
 */

export function calcMA(closes: number[], period: number): (number | null)[] {
  if (period <= 0) throw new Error(`period must be positive, got ${period}`);
  if (closes.length === 0) return [];
  const result: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += closes[j];
    result.push(sum / period);
  }
  return result;
}

function ema(values: number[], period: number): (number | null)[] {
  if (period <= 0) throw new Error(`period must be positive, got ${period}`);
  if (values.length === 0) return [];
  const k = 2 / (period + 1);
  const result: (number | null)[] = [];
  let prevSma: number | null = null;
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    if (prevSma === null) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += values[j];
      prevSma = sum / period;
    } else {
      prevSma = values[i] * k + prevSma * (1 - k);
    }
    result.push(prevSma);
  }
  return result;
}

export function calcBoll(
  closes: number[],
  period = 20,
  numStd = 2.0
): { upper: (number | null)[]; mid: (number | null)[]; lower: (number | null)[] } {
  if (period <= 0) throw new Error(`period must be positive, got ${period}`);
  if (closes.length === 0) return { upper: [], mid: [], lower: [] };
  const mid = calcMA(closes, period);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1 || mid[i] === null) {
      upper.push(null);
      lower.push(null);
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += closes[j];
    const mean = sum / period;
    let varSum = 0;
    for (let j = i - period + 1; j <= i; j++) varSum += (closes[j] - mean) ** 2;
    const std = Math.sqrt(varSum / period);
    upper.push(mean + numStd * std);
    lower.push(mean - numStd * std);
  }
  return { upper, mid, lower };
}

export function calcMacd(
  closes: number[],
  fast = 12,
  slow = 26,
  signal = 9
): { dif: (number | null)[]; dea: (number | null)[]; macd: (number | null)[] } {
  if (closes.length === 0) return { dif: [], dea: [], macd: [] };
  const emaFast = ema(closes, fast);
  const emaSlow = ema(closes, slow);
  const dif: (number | null)[] = emaFast.map((v, i) =>
    v !== null && emaSlow[i] !== null ? v - (emaSlow[i] as number) : null
  );
  const difForEma = dif.map((d) => d ?? 0);
  const deaRaw = ema(difForEma, signal);
  const dea: (number | null)[] = dif.map((d, i) =>
    d !== null && i >= slow - 1 + signal - 1 ? deaRaw[i] : null
  );
  const macd: (number | null)[] = dif.map((d, i) =>
    d !== null && dea[i] !== null ? (d - (dea[i] as number)) * 2 : null
  );
  return { dif, dea, macd };
}

export function calcKdj(
  highs: number[],
  lows: number[],
  closes: number[],
  n = 9,
  kPeriod = 3,
  dPeriod = 3
): { k: (number | null)[]; d: (number | null)[]; j: (number | null)[] } {
  if (highs.length !== lows.length || highs.length !== closes.length) {
    throw new Error('highs, lows, closes must have equal length');
  }
  if (closes.length === 0) return { k: [], d: [], j: [] };
  const rsv: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) {
      rsv.push(null);
      continue;
    }
    let hh = highs[i];
    let ll = lows[i];
    for (let j = i - n + 1; j <= i; j++) {
      if (highs[j] > hh) hh = highs[j];
      if (lows[j] < ll) ll = lows[j];
    }
    const rng = hh - ll;
    rsv.push(rng !== 0 ? ((closes[i] - ll) / rng) * 100 : 50);
  }
  const kAlpha = 1 / kPeriod;
  const dAlpha = 1 / dPeriod;
  const k: (number | null)[] = [];
  const d: (number | null)[] = [];
  let prevK = 50;
  let prevD = 50;
  for (let i = 0; i < closes.length; i++) {
    if (rsv[i] === null) {
      k.push(null);
      d.push(null);
      continue;
    }
    prevK = prevK * (1 - kAlpha) + (rsv[i] as number) * kAlpha;
    prevD = prevD * (1 - dAlpha) + prevK * dAlpha;
    k.push(prevK);
    d.push(prevD);
  }
  const j: (number | null)[] = k.map((kk, i) =>
    kk !== null && d[i] !== null ? 3 * kk - 2 * (d[i] as number) : null
  );
  return { k, d, j };
}
```

- [ ] **Step 2: 类型检查通过**

Run: `cd web && npx tsc --noEmit`
Expected: 无错误（空 errors 列表）。如果 tsc 报缺配置，运行 `npx tsc --init` 生成基础 tsconfig.json，或检查现有 `tsconfig.json` 是否存在。

- [ ] **Step 3: 提交**

```bash
git add web/src/indicators.ts
git commit -m "feat(web): add TypeScript chart indicator formulas"
```

---

## Task 5: TypeScript 类型加 index_data

**Files:**
- Modify: `web/src/types.ts`

- [ ] **Step 1: 在 BacktestResult 接口加 index_data 字段**

编辑 `web/src/types.ts`，找到 `BacktestResult` 接口，在 `price_data` 之后追加：

```typescript
  index_data: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    amount: number;
  }>;
```

（注意前面的缩进要和 `price_data` 一致。）

- [ ] **Step 2: 类型检查通过**

Run: `cd web && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add web/src/types.ts
git commit -m "feat(web): add index_data to BacktestResult type"
```

---

## Task 6: 添加 Panel 3 —— 上证指数 K 线 + MA + BOLL

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 加 import 和新状态**

编辑 `web/src/App.tsx`：

1. 在顶部 import 区追加：
   ```typescript
   import { calcMA, calcBoll } from './indicators';
   ```

2. 在 `MaVisibility` interface 之后追加：
   ```typescript
   interface IndexMaVisibility {
     ma5: boolean;
     ma10: boolean;
     ma20: boolean;
     ma60: boolean;
     boll: boolean;
   }
   ```

3. 在 `const [maVisibility, setMaVisibility] = useState<MaVisibility>({...})` 之后追加：
   ```typescript
   const [indexMaVisibility, setIndexMaVisibility] = useState<IndexMaVisibility>({
     ma5: true,
     ma10: true,
     ma20: true,
     ma60: true,
     boll: false,
   });
   const toggleIndexMa = (key: keyof IndexMaVisibility) => {
     setIndexMaVisibility((prev) => ({ ...prev, [key]: !prev[key] }));
   };
   ```

- [ ] **Step 2: 加 useMemo 计算 indexDataWithMA 和 filteredIndexData**

在 `filteredPriceData` useMemo 之后追加：

```typescript
const indexDataWithMA = useMemo(() => {
  if (!result?.index_data?.length) return [];
  const closes = result.index_data.map((d) => d.close);
  const ma5 = calcMA(closes, 5);
  const ma10 = calcMA(closes, 10);
  const ma20 = calcMA(closes, 20);
  const ma60 = calcMA(closes, 60);
  const boll = calcBoll(closes, 20, 2.0);
  return result.index_data.map((d, i) => ({
    ...d,
    ma5: ma5[i],
    ma10: ma10[i],
    ma20: ma20[i],
    ma60: ma60[i],
    boll_upper: boll.upper[i],
    boll_mid: boll.mid[i],
    boll_lower: boll.lower[i],
  }));
}, [result]);

const filteredIndexData = useMemo(() => {
  if (!indexDataWithMA.length) return [];
  let data = indexDataWithMA;
  if (chartDateRange?.start && chartDateRange?.end) {
    data = data.filter((d) => d.date >= chartDateRange.start && d.date <= chartDateRange.end);
  }
  return data;
}, [indexDataWithMA, chartDateRange]);
```

- [ ] **Step 3: 在 JSX 里添加 Panel 3**

在现有「股票 K 线 + MA」panel（`<section className="panel">` 包含 K 线那段，定位 `result?.price_data?.length > 0 && (` 这行）**之后**插入：

```tsx
{result?.index_data && result.index_data.length > 0 && (
  <section className="panel">
    <div className="chart-header">
      <h3>上证指数 K 线 + MA + BOLL</h3>
    </div>

    <div className="line-toggles">
      {(['ma5', 'ma10', 'ma20', 'ma60', 'boll'] as const).map((key) => (
        <button
          key={key}
          className={`toggle-btn ${indexMaVisibility[key] ? 'active' : ''}`}
          onClick={() => toggleIndexMa(key)}
        >
          {indexMaVisibility[key] ? <Eye size={14} /> : <EyeOff size={14} />}
          {key === 'boll' ? 'BOLL' : key.toUpperCase()}
        </button>
      ))}
    </div>

    <div className="chart-date-range">
      <label>显示时间范围
        <div className="date-range-inputs">
          <input
            type="text"
            placeholder="YYYYMMDD"
            value={chartDateRange?.start || selectedJob?.start_date || ''}
            onChange={(e) => {
              const start = formatDateFromInput(e.target.value);
              setChartDateRange((prev) => ({
                start,
                end: prev?.end || formatDateFromInput(selectedJob?.end_date || ''),
              }));
            }}
          />
          <span>至</span>
          <input
            type="text"
            placeholder="YYYYMMDD"
            value={chartDateRange?.end || selectedJob?.end_date || ''}
            onChange={(e) => {
              const end = formatDateFromInput(e.target.value);
              setChartDateRange((prev) => ({
                start: prev?.start || formatDateFromInput(selectedJob?.start_date || ''),
                end,
              }));
            }}
          />
          <button
            className="reset-date-btn"
            onClick={() => setChartDateRange(null)}
            title="Reset to full range"
          >
            重置
          </button>
        </div>
      </label>
    </div>

    <div className="chart-container">
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={filteredIndexData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" minTickGap={32} />
          <YAxis domain={['auto', 'auto']} />
          <Tooltip
            formatter={(value: any, name: string) => {
              if (typeof value === 'number') return [value.toFixed(2), name];
              return [value, name];
            }}
            labelFormatter={(label: string) => {
              const point = filteredIndexData.find((d) => d.date === label);
              if (!point) return label;
              return `${label} | O:${point.open.toFixed(2)} H:${point.high.toFixed(2)} L:${point.low.toFixed(2)} C:${point.close.toFixed(2)}`;
            }}
          />
          <Legend />
          <Bar dataKey="close" shape={CandleShape} isAnimationActive={false} legendType="none" />
          {indexMaVisibility.ma5 && (
            <Line type="monotone" dataKey="ma5" stroke="#ef4444" dot={false} strokeWidth={1.5} name="MA5" isAnimationActive={false} connectNulls={false} />
          )}
          {indexMaVisibility.ma10 && (
            <Line type="monotone" dataKey="ma10" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="MA10" isAnimationActive={false} connectNulls={false} />
          )}
          {indexMaVisibility.ma20 && (
            <Line type="monotone" dataKey="ma20" stroke="#2563eb" dot={false} strokeWidth={1.5} name="MA20" isAnimationActive={false} connectNulls={false} />
          )}
          {indexMaVisibility.ma60 && (
            <Line type="monotone" dataKey="ma60" stroke="#7c3aed" dot={false} strokeWidth={1.5} name="MA60" isAnimationActive={false} connectNulls={false} />
          )}
          {indexMaVisibility.boll && (
            <>
              <Line type="monotone" dataKey="boll_upper" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL上轨" isAnimationActive={false} connectNulls={false} />
              <Line type="monotone" dataKey="boll_mid" stroke="#eab308" dot={false} strokeWidth={1.2} name="BOLL中轨" isAnimationActive={false} connectNulls={false} />
              <Line type="monotone" dataKey="boll_lower" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL下轨" isAnimationActive={false} connectNulls={false} />
            </>
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  </section>
)}
```

- [ ] **Step 4: 类型检查 + 手动验证**

1. Run: `cd web && npx tsc --noEmit`
   Expected: 无错误

2. 手动验证（启动前后端）：
   - `python server/main.py`（终端 1）
   - `cd web && npm run dev`（终端 2）
   - 浏览器打开 http://localhost:5173，跑一个回测，确认上证指数 K 线 panel 出现，蜡烛正确，5 个 toggle 正常切换

- [ ] **Step 5: 提交**

```bash
git add web/src/App.tsx
git commit -m "feat(web): add Shanghai Composite K-line chart panel with MA and BOLL"
```

---

## Task 7: 添加 Panel 4 —— 上证指数技术指标（下拉切换）

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 加 import 和状态**

1. 顶部 import 区追加：
   ```typescript
   import { calcMA, calcBoll, calcMacd, calcKdj } from './indicators';
   ```

2. 在 `selectedIndicator` 状态之前（紧跟 `toggleIndexMa` 之后）追加：
   ```typescript
   type IndicatorKey = 'macd' | 'kdj' | 'volume' | 'amount';
   const [selectedIndicator, setSelectedIndicator] = useState<IndicatorKey>('macd');
   ```

- [ ] **Step 2: 加 useMemo 计算各指标**

在 `filteredIndexData` useMemo 之后追加：

```typescript
const indexIndicatorData = useMemo(() => {
  if (!indexDataWithMA.length) return [];
  const highs = indexDataWithMA.map((d) => d.high);
  const lows = indexDataWithMA.map((d) => d.low);
  const closes = indexDataWithMA.map((d) => d.close);

  if (selectedIndicator === 'macd') {
    const { dif, dea, macd } = calcMacd(closes);
    return indexDataWithMA.map((d, i) => ({
      date: d.date,
      isUp: d.close >= d.open,
      dif: dif[i],
      dea: dea[i],
      macd: macd[i],
    }));
  }
  if (selectedIndicator === 'kdj') {
    const { k, d, j } = calcKdj(highs, lows, closes);
    return indexDataWithMA.map((p, i) => ({
      date: p.date,
      k: k[i],
      d: d[i],
      j: j[i],
    }));
  }
  if (selectedIndicator === 'volume') {
    return indexDataWithMA.map((d) => ({
      date: d.date,
      isUp: d.close >= d.open,
      value: d.volume,
    }));
  }
  // amount
  return indexDataWithMA.map((d) => ({
    date: d.date,
    isUp: d.close >= d.open,
    value: d.amount / 1e8,  // 转亿元
  }));
}, [indexDataWithMA, selectedIndicator]);

const filteredIndicatorData = useMemo(() => {
  if (!indexIndicatorData.length) return [];
  if (chartDateRange?.start && chartDateRange?.end) {
    return indexIndicatorData.filter(
      (d) => d.date >= chartDateRange.start && d.date <= chartDateRange.end
    );
  }
  return indexIndicatorData;
}, [indexIndicatorData, chartDateRange]);
```

- [ ] **Step 3: 添加 Panel 4 JSX**

先在 import 区追加 `Cell` 和 `ReferenceLine`：

```typescript
import { Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
```

紧接 Panel 3 的 `</section>` 之后插入（必须在 `result.index_data.length > 0` 判断块内）：

```tsx
<section className="panel">
  <div className="chart-header">
    <h3>上证指数 技术指标</h3>
    <select
      value={selectedIndicator}
      onChange={(e) => setSelectedIndicator(e.target.value as IndicatorKey)}
      style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #cbd5df', background: '#fff' }}
    >
      <option value="macd">MACD</option>
      <option value="kdj">KDJ</option>
      <option value="volume">交易量</option>
      <option value="amount">交易额（亿元）</option>
    </select>
  </div>

  <div className="chart-container">
    <ResponsiveContainer width="100%" height={200}>
      <ComposedChart data={filteredIndicatorData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" minTickGap={32} />
        <YAxis domain={['auto', 'auto']} />
        <Tooltip />
        {selectedIndicator === 'macd' && (
          <>
            <Bar dataKey="macd" isAnimationActive={false} name="MACD">
              {filteredIndicatorData.map((entry, i) => (
                <Cell key={`m-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
              ))}
            </Bar>
            <Line type="monotone" dataKey="dif" stroke="#facc15" dot={false} strokeWidth={1.4} name="DIF" isAnimationActive={false} connectNulls={false} />
            <Line type="monotone" dataKey="dea" stroke="#f97316" dot={false} strokeWidth={1.4} name="DEA" isAnimationActive={false} connectNulls={false} />
          </>
        )}
        {selectedIndicator === 'kdj' && (
          <>
            <Line type="monotone" dataKey="k" stroke="#f3f4f6" dot={false} strokeWidth={1.4} name="K" isAnimationActive={false} connectNulls={false} />
            <Line type="monotone" dataKey="d" stroke="#facc15" dot={false} strokeWidth={1.4} name="D" isAnimationActive={false} connectNulls={false} />
            <Line type="monotone" dataKey="j" stroke="#a855f7" dot={false} strokeWidth={1.4} name="J" isAnimationActive={false} connectNulls={false} />
            <ReferenceLine y={80} stroke="#9ca3af" strokeDasharray="2 2" />
            <ReferenceLine y={20} stroke="#9ca3af" strokeDasharray="2 2" />
          </>
        )}
        {selectedIndicator === 'volume' && (
          <Bar dataKey="value" isAnimationActive={false} name="交易量">
            {filteredIndicatorData.map((entry, i) => (
              <Cell key={`v-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
            ))}
          </Bar>
        )}
        {selectedIndicator === 'amount' && (
          <Bar dataKey="value" isAnimationActive={false} name="交易额">
            {filteredIndicatorData.map((entry, i) => (
              <Cell key={`a-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
            ))}
          </Bar>
        )}
      </ComposedChart>
    </ResponsiveContainer>
  </div>
</section>
```

并在 import 区追加 `Cell` 和 `ReferenceLine`：

```typescript
import { Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
```

- [ ] **Step 4: 类型检查 + 手动验证**

1. Run: `cd web && npx tsc --noEmit`
   Expected: 无错误

2. 手动验证：浏览器跑一次回测，切换 4 个下拉选项，确认：
   - MACD：DIF/DEA 黄橙两条线 + 红绿柱
   - KDJ：K/D/J 三条线 + 80/20 虚线
   - 交易量：红绿柱（按当日涨跌着色）
   - 交易额：红绿柱，Y 轴单位亿元

- [ ] **Step 5: 提交**

```bash
git add web/src/App.tsx
git commit -m "feat(web): add Shanghai Composite technical indicator panel with dropdown"
```

---

## Task 8: 加空状态 + 收尾验证

**Files:**
- Modify: `web/src/App.tsx`
- (no test for empty state — manual verify)

- [ ] **Step 1: 改 Panel 3/4 的外层判断条件**

找到 `result?.index_data && result.index_data.length > 0 && (` 包裹 Panel 3+4 的那个外层 `&&`，改为：

```tsx
{result && (
  result.index_data.length > 0 ? (
    <>
      {/* Panel 3 + Panel 4 JSX */}
    </>
  ) : (
    <section className="panel">
      <h3>上证指数</h3>
      <p style={{ color: '#627282' }}>
        上证指数数据加载失败（网络或数据源问题），请重试回测。
      </p>
      <button
        className="secondary"
        type="button"
        onClick={() => selectedJob && submit(true)}
        disabled={submitting || !selectedJob}
      >
        <RefreshCcw size={16} /> 重新运行
      </button>
    </section>
  )
)}
```

注意：实际放置时，把 Panel 3 和 Panel 4 的整段 JSX 包到 `result.index_data.length > 0 ? (<>...</>) : (<>...</>)` 三元里。具体哪个外层 JSX 包裹需要看实际代码。

- [ ] **Step 2: 手动验证空状态**

1. 启动后端，临时把 `load_shanghai_composite` 改成永远返回 `None`（用 `monkeypatch` 在测试里、或临时改源码）。
2. 跑一次回测。
3. 确认页面显示「上证指数数据加载失败」+ 重新运行按钮，**股票 K 线 + MA panel 仍然正常**。

恢复代码。

- [ ] **Step 3: 最终全量验证**

1. Run: `python -m pytest -q tests/`
   Expected: All tests pass
2. Run: `cd web && npx tsc --noEmit`
   Expected: 无错误
3. Run: `cd web && npm run build`
   Expected: Build succeeds
4. 浏览器跑一次真实回测（用真数据 000001），完整走一遍：
   - 4 个 panel 都正确显示
   - MA5/10/20/60/BOLL 5 个 toggle 正常
   - 4 个指标下拉切换正常
   - 改日期范围 4 个图同步

- [ ] **Step 4: 提交**

```bash
git add web/src/App.tsx
git commit -m "feat(web): add empty state for missing Shanghai Composite data"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - 上证指数 K 线 panel ✅ Task 6
  - MA5/10/20/60 toggle ✅ Task 6
  - BOLL toggle ✅ Task 6
  - MACD/KDJ/Volume/Amount dropdown ✅ Task 7
  - amount 列 ✅ Task 1
  - index_data 字段 + 后端加载 ✅ Task 3
  - 前端类型 ✅ Task 5
  - 指标公式（前端）✅ Task 4
  - 指标公式（Python 参考 + 测试）✅ Task 2
  - 空状态 ✅ Task 8
  - 颜色规范、画法、tooltip、复用 ✅ Task 6/7
  - 日期范围跟随 chartDateRange ✅ Task 6/7
  - 缓存 schema 校验（保守：跳过不删） ✅ Task 1

- [x] **No placeholders:** All steps have explicit code.

- [x] **Type consistency:**
  - Python `index_data` field is `list[dict[str, Any]]` in both `BacktestResult` and `to_dict()` (dataclass asdict covers it)
  - TS `index_data: Array<{date, open, high, low, close, volume, amount}>` matches Python's per-row keys
  - `calc_ma` / `calcMA` / `calc_boll` / `calcBoll` / `calc_macd` / `calcMacd` / `calc_kdj` / `calcKdj` are consistent across Python and TS
  - State names: `indexMaVisibility`, `selectedIndicator`, `IndicatorKey` consistent in App.tsx
  - ComposedChart, Bar, Line, Cell, ReferenceLine all from recharts, already imported elsewhere in App.tsx
