# 风险调整指标 + 基准对比 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为回测结果补齐风险调整指标（年化夏普、年化收益、盈亏比）与基准对比（上证指数买入持有收益、策略超额收益），让回测能判断策略是否真有 alpha。

**Architecture:** 新建纯函数模块 `backtest/metrics.py`（入参为已 `get_analysis()` 的普通 dict/list，不碰 backtrader/网络，可独立单测）。`backtest/service.py` 挂 `SharpeRatio`/`Returns` 两个 analyzer，调用 metrics 模块算 5 个标量，扩展 `BacktestResult` dataclass 5 个字段。序列化（`asdict→json.dump→API`）与缓存失效全部自动，零改动。前端 `types.ts`/`App.tsx`/i18n 同步展示。

**Tech Stack:** Python 3, backtrader 1.9.78.123, pytest；React + TypeScript + Vite, i18next。

**对应设计文档:** `docs/superpowers/specs/2026-06-21-risk-metrics-benchmark-design.md`

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `backtest/metrics.py` | 5 个纯函数：提取夏普/年化、算盈亏比/基准/超额 | 新建 |
| `tests/test_metrics.py` | metrics 纯函数单测 | 新建 |
| `backtest/service.py` | 挂 analyzer + 算指标 + 扩 `BacktestResult` | 修改 |
| `tests/test_backtest_service.py` | 端到端验证新字段 + 基准计算 | 修改（追加） |
| `web/src/types.ts` | `BacktestResult` interface 加 5 字段 | 修改 |
| `web/src/App.tsx` | KPI secondary chip 追加 5 项 | 修改 |
| `web/src/i18n/locales/zh.json` | 5 个 kpi 中文 key | 修改 |
| `web/src/i18n/locales/en.json` | 5 个 kpi 英文 key | 修改 |

---

## 背景知识（实现者必读）

- **实机核查（backtrader 1.9.78.123，已实跑确认）**：
  - `SharpeRatio`（配 `timeframe=bt.TimeFrame.Days, annualize=True`）→ `get_analysis()` 返回 `{'sharperatio': float | None}`。无成交/零方差时为 `None`。
  - `Returns` → `{'rnorm100': float, 'rtot':, 'ravg':, 'rnorm':}`。`rnorm100` 即年化收益率（百分数）。
  - `TradeAnalyzer`（service.py 已挂，`_name='trade_stats'`）→ `won.pnl.average`、`lost.pnl.average`。无亏损交易时 `lost` 分支可能缺失或 average 为 0。
- **关键坑**：`AnnualReturn` analyzer 在 `cerebro.run(stdstats=False)` 下抛 `AttributeError: 'ItemCollection' object has no attribute 'broker'`（依赖 broker observer）。service.py 是 `stdstats=False`，**禁用 AnnualReturn**，年化收益走 `Returns.rnorm100`。
- **TradeAnalyzer 结果是 `AutoOrderedDict`**：链式 `.get('won', {}).get('pnl', {}).get('average', 0.0)` 对它和普通 dict 都成立（实测）。
- **序列化零改动**：`BacktestResult.to_dict()=asdict()`，`server/executor.py:19-22` 直接 `json.dump`，API `/result` 原样回传。新字段自动到前端。
- **测试数据**：`backtest.run_backtest.generate_synthetic_data(start, end)` 生成确定性合成 OHLCV（seed=42），日期 `'YYYYMMDD'`。
- **测试桩**：`tests/test_backtest_service.py` 已有 `FakeHub`（monkeypatch `backtest.service.DataHub`），`hub.feed('index_daily', df, symbol='sh000001')` 可喂基准数据。现有断言是结构性的，加字段不破坏。
- **前端 i18n**：`web/src/i18n/locales/{zh,en}.json` 是扁平 key（如 `"kpi.winRate": "胜率"`）。
- **前端 KPI**：`App.tsx` 的 `kpis.secondary` 是 `{label, value}` 数组；`formatPct(v)` = `${v.toFixed(2)}%`。

---

### Task 1: 创建指标模块 `backtest/metrics.py`（5 个纯函数 TDD）

**Files:**
- Create: `backtest/metrics.py`
- Test: `tests/test_metrics.py`

- [ ] **Step 1: 写失败测试 —— 夏普提取（正常 / None / 缺 key）**

创建 `tests/test_metrics.py`：

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from backtest.metrics import (
    extract_sharpe,
    extract_annual_return_pct,
    compute_profit_loss_ratio,
    compute_benchmark_return_pct,
    compute_excess_return_pct,
)


def test_extract_sharpe_normal():
    assert extract_sharpe({'sharperatio': 1.25}) == pytest.approx(1.25)


def test_extract_sharpe_none_returns_zero():
    assert extract_sharpe({'sharperatio': None}) == 0.0


def test_extract_sharpe_missing_key_returns_zero():
    assert extract_sharpe({}) == 0.0
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'backtest.metrics'`

- [ ] **Step 3: 写最小实现**

创建 `backtest/metrics.py`：

```python
"""风险调整指标 + 基准对比的提取与计算。

入参均为已经 get_analysis() 的普通 dict / list，本模块不碰 backtrader、不碰网络，
纯函数可独立单测。被 backtest/service.py 调用。
"""
from typing import Any


def extract_sharpe(sharpe_analysis: dict) -> float:
    """从 SharpeRatio analyzer 结果取年化夏普；None/缺失 → 0.0。"""
    value = sharpe_analysis.get('sharperatio')
    return float(value) if value is not None else 0.0


def extract_annual_return_pct(returns_analysis: dict) -> float:
    """从 Returns analyzer 取年化收益率（rnorm100，已是百分数）。"""
    return float(returns_analysis.get('rnorm100', 0.0) or 0.0)


def compute_profit_loss_ratio(trade_stats: dict) -> float:
    """盈亏比 = 平均盈利 / 平均亏损绝对值。无亏损交易时返回 0.0。"""
    won_avg = trade_stats.get('won', {}).get('pnl', {}).get('average', 0.0) or 0.0
    lost_avg = trade_stats.get('lost', {}).get('pnl', {}).get('average', 0.0) or 0.0
    if lost_avg == 0:
        return 0.0
    return float(won_avg / abs(lost_avg))


def compute_benchmark_return_pct(index_data: list[dict[str, Any]]) -> float:
    """上证指数买入持有收益%。数据为空或首值为 0 → 0.0。"""
    if not index_data:
        return 0.0
    first_close = index_data[0].get('close', 0.0)
    last_close = index_data[-1].get('close', 0.0)
    if not first_close:
        return 0.0
    return float((last_close / first_close - 1.0) * 100.0)


def compute_excess_return_pct(strategy_return_pct: float, benchmark_return_pct: float) -> float:
    """策略超额收益 = 策略收益 - 基准收益。"""
    return float(strategy_return_pct - benchmark_return_pct)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: 3 项 PASS

- [ ] **Step 5: 提交**

```bash
git add backtest/metrics.py tests/test_metrics.py
git commit -m "feat(backtest): add metrics module with sharpe extraction"
```

---

### Task 2: 年化收益 + 盈亏比测试

**Files:**
- Modify: `tests/test_metrics.py`

- [ ] **Step 1: 追加测试 —— 年化收益与盈亏比**

在 `tests/test_metrics.py` 末尾追加：

```python
def test_extract_annual_return_pct_normal():
    assert extract_annual_return_pct({'rnorm100': 21.7}) == pytest.approx(21.7)


def test_extract_annual_return_pct_missing_returns_zero():
    assert extract_annual_return_pct({}) == 0.0


def test_profit_loss_ratio_normal():
    stats = {
        'won': {'pnl': {'average': 16135.79}},
        'lost': {'pnl': {'average': -4496.12}},
    }
    assert compute_profit_loss_ratio(stats) == pytest.approx(16135.79 / 4496.12)


def test_profit_loss_ratio_no_losses_returns_zero():
    stats = {
        'won': {'pnl': {'average': 1000.0}},
        'lost': {'pnl': {'average': 0.0}},
    }
    assert compute_profit_loss_ratio(stats) == 0.0


def test_profit_loss_ratio_missing_lost_returns_zero():
    stats = {'won': {'pnl': {'average': 1000.0}}}
    assert compute_profit_loss_ratio(stats) == 0.0
```

- [ ] **Step 2: 运行测试，确认通过**

实现已在 Task 1 完成，这些测试验证设计正确性。

Run: `python -m pytest tests/test_metrics.py -v`
Expected: 8 项全部 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_metrics.py
git commit -m "test(backtest): cover annual return and profit-loss ratio"
```

---

### Task 3: 基准收益 + 超额收益测试

**Files:**
- Modify: `tests/test_metrics.py`

- [ ] **Step 1: 追加测试 —— 基准与超额收益**

在 `tests/test_metrics.py` 末尾追加：

```python
def test_benchmark_return_normal():
    index_data = [{'close': 3000.0}, {'close': 3300.0}]
    # (3300/3000 - 1) * 100 = 10.0
    assert compute_benchmark_return_pct(index_data) == pytest.approx(10.0)


def test_benchmark_return_empty_returns_zero():
    assert compute_benchmark_return_pct([]) == 0.0


def test_benchmark_return_zero_first_close_returns_zero():
    index_data = [{'close': 0.0}, {'close': 3300.0}]
    assert compute_benchmark_return_pct(index_data) == 0.0


def test_excess_return_positive():
    # 策略 25%，基准 10% → 超额 15%
    assert compute_excess_return_pct(25.0, 10.0) == pytest.approx(15.0)


def test_excess_return_negative():
    # 策略跑输基准
    assert compute_excess_return_pct(5.0, 10.0) == pytest.approx(-5.0)
```

- [ ] **Step 2: 运行测试，确认通过**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: 13 项全部 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_metrics.py
git commit -m "test(backtest): cover benchmark and excess return"
```

---

### Task 4: 接入 service.py —— 挂 analyzer + 扩 BacktestResult

**Files:**
- Modify: `backtest/service.py`

- [ ] **Step 1: 加 import**

在 `backtest/service.py` 顶部 import 区，`from backtest.costs import apply_ashare_costs` 之后加：

```python
from backtest.metrics import (
    compute_benchmark_return_pct,
    compute_excess_return_pct,
    compute_profit_loss_ratio,
    extract_annual_return_pct,
    extract_sharpe,
)
```

- [ ] **Step 2: 给 `BacktestResult` 加 5 字段**

定位 `BacktestResult` dataclass 中这一行（约 line 67）：

```python
    win_rate_pct: float
```

在其**后**插入 5 行（保持标量指标在 `equity_curve` 等 list 字段之前）：

```python
    win_rate_pct: float
    sharpe: float = 0.0
    annual_return_pct: float = 0.0
    profit_loss_ratio: float = 0.0
    benchmark_return_pct: float = 0.0
    excess_return_pct: float = 0.0
```

> 注：5 个新字段带默认值，原 `win_rate_pct` 无默认值。dataclass 要求"无默认值字段不能排在有默认值字段之后"——`win_rate_pct` 在前、新字段在后，合法。其后的 `equity_curve` 等本就有 `field(default_factory=...)`，顺序不变。

- [ ] **Step 3: 在 run_backtest_service 挂两个 analyzer**

定位 analyzer 注册块（约 line 236-240），在 `cerebro.addanalyzer(PriceDataAnalyzer, _name='price')` 之后追加：

```python
    cerebro.addanalyzer(PriceDataAnalyzer, _name='price')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe',
                        timeframe=bt.TimeFrame.Days, annualize=True)
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
```

- [ ] **Step 4: 算指标并传入 BacktestResult**

定位 `win_rate_pct` 计算之后（约 line 252）、`return BacktestResult(` 之前，插入：

```python
    win_rate_pct = (won_total / total_closed * 100.0) if total_closed else 0.0

    sharpe = extract_sharpe(strategy.analyzers.sharpe.get_analysis())
    annual_return_pct = extract_annual_return_pct(strategy.analyzers.returns.get_analysis())
    profit_loss_ratio = compute_profit_loss_ratio(trade_stats)
    benchmark_return_pct = compute_benchmark_return_pct(index_data)
    excess_return_pct = compute_excess_return_pct(total_return_pct, benchmark_return_pct)
```

在 `return BacktestResult(...)` 的 `win_rate_pct=float(win_rate_pct),` 之后插入 5 个参数：

```python
        win_rate_pct=float(win_rate_pct),
        sharpe=float(sharpe),
        annual_return_pct=float(annual_return_pct),
        profit_loss_ratio=float(profit_loss_ratio),
        benchmark_return_pct=float(benchmark_return_pct),
        excess_return_pct=float(excess_return_pct),
```

- [ ] **Step 5: 运行现有 service 测试，确认不回归**

Run: `python -m pytest tests/test_backtest_service.py -v`
Expected: 全部 PASS（结构性断言，加字段不破坏）

- [ ] **Step 6: 提交**

```bash
git add backtest/service.py
git commit -m "feat(backtest): wire risk metrics and benchmark into service result"
```

---

### Task 5: service 端到端测试 —— 验证新字段 + 基准计算

**Files:**
- Modify: `tests/test_backtest_service.py`

- [ ] **Step 1: 追加端到端测试**

在 `tests/test_backtest_service.py` 末尾追加（`FakeHub`、`generate_synthetic_data` 已在文件顶部 import）：

```python
def test_run_backtest_service_includes_risk_metrics(monkeypatch):
    stock_df = generate_synthetic_data(start='20200101', end='20221231')
    # 构造已知涨幅的指数 feed：首 close 3000，末 close 3300 → 基准 +10%
    index_df = generate_synthetic_data(start='20200101', end='20221231').copy()
    index_df['amount'] = 1e12
    index_df.loc[index_df.index[0], 'close'] = 3000.0
    index_df.loc[index_df.index[-1], 'close'] = 3300.0

    hub = FakeHub()
    hub.feed('stock_daily', stock_df)
    hub.feed('index_daily', index_df, symbol='sh000001')
    _patch_hub(monkeypatch, hub)

    request = BacktestRequest(
        symbol='000001',
        start='20200101',
        end='20221231',
        cash=100000.0,
        use_market_filter=False,
    )

    result = run_backtest_service(request)
    payload = result.to_dict()

    # 5 个新字段存在且为 float
    for key in ('sharpe', 'annual_return_pct', 'profit_loss_ratio',
                'benchmark_return_pct', 'excess_return_pct'):
        assert key in payload
        assert isinstance(payload[key], float)

    # 基准收益 = (3300/3000 - 1)*100 = 10%
    assert payload['benchmark_return_pct'] == pytest.approx(10.0)
    # 超额收益 = 策略收益 - 基准收益
    assert payload['excess_return_pct'] == pytest.approx(
        payload['total_return_pct'] - payload['benchmark_return_pct']
    )
```

文件顶部若无 `import pytest`，在 import 区加上 `import pytest`。

- [ ] **Step 2: 运行测试，确认通过**

Run: `python -m pytest tests/test_backtest_service.py::test_run_backtest_service_includes_risk_metrics -v`
Expected: PASS

> 若 `benchmark_return_pct` 不等于 10.0：检查 `index_data` 构造时 `df['close']` 首末值是否被策略数据覆盖——确认喂的是 `index_daily` 且 symbol='sh000001'，与 service.py 加载逻辑一致。

- [ ] **Step 3: 提交**

```bash
git add tests/test_backtest_service.py
git commit -m "test(backtest): verify risk metrics and benchmark in service result"
```

---

### Task 6: 前端 types + i18n

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/i18n/locales/zh.json`
- Modify: `web/src/i18n/locales/en.json`

- [ ] **Step 1: `types.ts` 加 5 字段**

定位 `web/src/types.ts` 的 `BacktestResult` interface 中：

```typescript
  win_rate_pct: number;
```

在其后插入：

```typescript
  win_rate_pct: number;
  sharpe: number;
  annual_return_pct: number;
  profit_loss_ratio: number;
  benchmark_return_pct: number;
  excess_return_pct: number;
```

- [ ] **Step 2: zh.json 加 5 个 key**

在 `web/src/i18n/locales/zh.json` 的 `"kpi.tradeCount": "交易次数",` 之后追加：

```json
  "kpi.sharpe": "夏普比率",
  "kpi.annualReturn": "年化收益",
  "kpi.profitLossRatio": "盈亏比",
  "kpi.benchmarkReturn": "基准收益",
  "kpi.excessReturn": "超额收益",
```

- [ ] **Step 3: en.json 加 5 个 key**

在 `web/src/i18n/locales/en.json` 的 `"kpi.tradeCount": "Trade Count",` 之后追加：

```json
  "kpi.sharpe": "Sharpe Ratio",
  "kpi.annualReturn": "Annual Return",
  "kpi.profitLossRatio": "Profit/Loss Ratio",
  "kpi.benchmarkReturn": "Benchmark Return",
  "kpi.excessReturn": "Excess Return",
```

> 注意 JSON 尾逗号：确保插入位置语法合法（后面还有其他 key 则保留逗号；若 kpi.tradeCount 恰是该对象最后一项需调整）。实现时按文件实际结构处理。

- [ ] **Step 4: 提交**

```bash
git add web/src/types.ts web/src/i18n/locales/zh.json web/src/i18n/locales/en.json
git commit -m "feat(web): add risk metric fields to types and i18n"
```

---

### Task 7: 前端 App.tsx KPI 展示

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: secondary chip 追加 5 项**

定位 `App.tsx` 的 `kpis` useMemo 中 `secondary` 数组（约 line 246-252），在现有最后一项 `{ label: t('kpi.initialCash'), ... }` 之后追加：

```typescript
    const secondary = [
      { label: t('kpi.winRate'), value: formatPct(result.win_rate_pct) },
      { label: t('kpi.maxDrawdown'), value: formatPct(result.max_drawdown_pct) },
      { label: t('kpi.tradeCount'), value: String(result.trade_count) },
      { label: t('kpi.sharpe'), value: result.sharpe.toFixed(2) },
      { label: t('kpi.annualReturn'), value: formatPct(result.annual_return_pct) },
      { label: t('kpi.profitLossRatio'), value: result.profit_loss_ratio.toFixed(2) },
      { label: t('kpi.benchmarkReturn'), value: formatPct(result.benchmark_return_pct) },
      { label: t('kpi.excessReturn'), value: formatPct(result.excess_return_pct) },
      { label: t('kpi.avgScore'), value: result.market_score_summary.mean?.toFixed(2) ?? 'N/A' },
      { label: t('kpi.initialCash'), value: result.initial_cash.toFixed(0) },
    ];
```

> 即在 `tradeCount` 之后、`avgScore` 之前插入 5 个新 chip，保持"交易统计→风险指标→基准→市场分→本金"的逻辑顺序。

- [ ] **Step 2: 前端构建检查**

Run: `cd web && npm run build`
Expected: tsc 无类型错误，构建成功。

> 若报 `Property 'sharpe' does not exist`：确认 Task 6 的 `types.ts` 已改并保存。

- [ ] **Step 3: 提交**

```bash
git add web/src/App.tsx
git commit -m "feat(web): display risk metrics and benchmark in KPI panel"
```

---

### Task 8: 全量回归

**Files:** 无（仅运行）

- [ ] **Step 1: 跑全部 Python 测试**

Run: `python -m pytest -q tests/`
Expected: 全绿（新增 13 个 metrics 测试 + 1 个 service 测试，原有不回归）。

- [ ] **Step 2: 前端构建确认**

Run: `cd web && npm run build`
Expected: 成功。

> 若 `test_backtest_service.py` 出现失败：检查是否有硬编码收益断言（设计核查未发现）。若有，按含新字段的结果更新，并在 commit message 说明。

- [ ] **Step 3: 提交（仅当有断言更新时）**

若无改动则跳过。

---

## Self-Review 记录

- **Spec 覆盖**：5 个指标（夏普/年化/盈亏比/基准/超额）→ Task 1-3 纯函数 + Task 4 接入；前端展示 → Task 6-7；测试 → Task 1-3（单测）+ Task 5（端到端）；全量回归 → Task 8。无遗漏。
- **占位符**：无 TBD/TODO，每个代码步骤含完整代码。
- **类型一致性**：`sharpe`/`annual_return_pct`/`profit_loss_ratio`/`benchmark_return_pct`/`excess_return_pct` 五个名字在 metrics.py、service.py、types.ts、App.tsx、i18n key 全程一致。函数名 `extract_sharpe`/`extract_annual_return_pct`/`compute_profit_loss_ratio`/`compute_benchmark_return_pct`/`compute_excess_return_pct` 在 plan 各处一致。
- **API 准确性**：`SharpeRatio(timeframe=Days, annualize=True)→sharperatio`、`Returns→rnorm100`、`TradeAnalyzer→won/lost.pnl.average`、`AnnualReturn 在 stdstats=False 下崩溃故弃用` —— 全部实机核查（backtrader 1.9.78.123）。
