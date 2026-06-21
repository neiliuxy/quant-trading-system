# 风险调整指标 + 基准对比 — 设计文档

> 创建日期：2026-06-21
> 对应改进项：`docs/improvement-directions.md` 第 2 项「增加风险调整指标与基准对比」

---

## 背景与目标

改进项 #1（交易成本）已让回测净值可信。但 `BacktestResult` 当前只输出
`total_return_pct / max_drawdown_pct / win_rate_pct / trade_count`——**只有收益，没有风险调整**。
单看收益率无法判断策略是靠承担风险换来的，还是真有 alpha。

同时 `index_data`（上证指数 sh000001 OHLCV）已在 `run_backtest_service` 中加载，
但**仅用于前端画图，未参与任何收益计算**。买入持有基准就在手边却没用上。

本设计补齐两类指标：

1. **风险调整指标**：夏普比率（年化）、年化收益率、盈亏比。
2. **基准对比**：上证指数买入持有收益、策略超额收益（alpha）。

**非目标**：
- 不引入无风险利率可配置化（夏普用 backtrader 默认 riskfreerate=0，符合 YAGNI；A 股短周期波段下影响极小）。
- 不做基准的风险调整对比（如信息比率）；本期只做收益层面的超额对比。
- 不改 CLI 路径（`run_backtest.py` 只打印 Return，不构造 `BacktestResult`，无展示载体）。

---

## 实机核查结论（backtrader 1.9.78.123）

设计基于实跑合成数据的实测，非记忆：

| Analyzer | 配置 | 返回结构 | 取值 |
|----------|------|----------|------|
| `SharpeRatio` | `timeframe=Days, annualize=True` | `{'sharperatio': float \| None}` | 年化夏普 |
| `Returns` | 默认 | `{'rnorm100': float, 'rtot', 'ravg', 'rnorm'}` | `rnorm100` = 年化收益% |
| `TradeAnalyzer` | 已挂（`trade_stats`） | `won.pnl.average`、`lost.pnl.average` | 盈亏比分子分母 |

**关键坑（实测发现）**：`AnnualReturn` analyzer 在 `cerebro.run(stdstats=False)` 下会抛
`AttributeError: 'ItemCollection' object has no attribute 'broker'`——它依赖 broker observer。
service.py 正是 `stdstats=False`，**故不能用 `AnnualReturn`**，年化收益改用 `Returns.rnorm100`（不依赖 observer）。

**边界值**：无成交或零方差时 `SharpeRatio.sharperatio` 返回 `None`；`lost.total == 0`（无亏损交易）时盈亏比分母为 0。两者都需兜底。

---

## 指标定义与计算

### 1. 夏普比率（年化）
直接取 `SharpeRatio` analyzer（配 `timeframe=Days, annualize=True`）的 `sharperatio`。
`None` → 输出 `0.0`（前端可显示 N/A，但 JSON 字段保持 float 不破坏类型）。

### 2. 年化收益率（%）
取 `Returns` analyzer 的 `rnorm100`。

### 3. 盈亏比
`won.pnl.average / abs(lost.pnl.average)`。
- 复用**已挂的** `trade_stats`（`bt.analyzers.TradeAnalyzer`），不重复挂。
- 无亏损交易（`lost.total == 0` 或 `lost.pnl.average` 缺失/为 0）→ 盈亏比为 0.0（约定：分母为 0 时不计算，避免 inf 污染 JSON）。

### 4. 基准买入持有收益（%）
上证指数在回测区间的买入持有收益：`(last_close / first_close - 1) * 100`。
数据源 = `index_data`（已构造好的 list[dict]，含 `close`）。
`index_data` 为空（指数加载失败）→ 基准收益 0.0、超额收益 0.0（约定降级值）。

### 5. 超额收益 / alpha（%）
`strategy_total_return_pct - benchmark_return_pct`。简单收益差，非回归 alpha。

---

## 架构

### 新增模块 `backtest/metrics.py`

集中指标提取逻辑，纯函数、无 backtrader/网络依赖（入参是已 `get_analysis()` 的普通 dict 与 list），
可独立单测。职责单一，与 `costs.py` 同级并列。

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

> 注：`TradeAnalyzer` 的结果是 `AutoOrderedDict`，`.get(...)` 链对它与普通 dict 都成立（实测）。

### 接入点 `backtest/service.py`

`run_backtest_service` 内：

1. **加两个 analyzer**（紧跟现有 analyzer 注册块，约 line 240 后）：
   ```python
   cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe',
                       timeframe=bt.TimeFrame.Days, annualize=True)
   cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
   ```
   `trade_stats`（TradeAnalyzer）已存在，盈亏比复用它，不重复挂。

2. **算指标**（在已有 `win_rate_pct` 计算之后）：
   ```python
   from backtest.metrics import (...)  # 顶部 import
   sharpe = extract_sharpe(strategy.analyzers.sharpe.get_analysis())
   annual_return_pct = extract_annual_return_pct(strategy.analyzers.returns.get_analysis())
   profit_loss_ratio = compute_profit_loss_ratio(trade_stats)
   benchmark_return_pct = compute_benchmark_return_pct(index_data)
   excess_return_pct = compute_excess_return_pct(total_return_pct, benchmark_return_pct)
   ```

3. **`BacktestResult` 加 5 字段**（dataclass，带默认值，放在 `win_rate_pct` 之后、`equity_curve` 之前以保持"标量指标在前"的现有布局）：
   ```python
   sharpe: float = 0.0
   annual_return_pct: float = 0.0
   profit_loss_ratio: float = 0.0
   benchmark_return_pct: float = 0.0
   excess_return_pct: float = 0.0
   ```
   并在 `return BacktestResult(...)` 里传入。

### 序列化（零改动）

`BacktestResult.to_dict() = asdict()` → `server/executor.py` 的 `json.dump` → API `/result` 原样回传。
**新字段自动流到 artifact JSON 和前端 fetch，无需改任何序列化代码。**（已核查 executor.py:19-22）

### 缓存失效（零改动）

`run_key` 哈希含 `code_version`（git short hash），本次提交后旧缓存自动失效，新回测重算。与 #1 同理。

---

## 前端展示 `web/`

### `web/src/types.ts`
`BacktestResult` interface 在 `win_rate_pct` 后加 5 个 `number` 字段（与后端同名）。

### `web/src/App.tsx`
`kpis` 的 `secondary` chip 数组追加（现有 5 个 chip 之后）：
- 夏普比率：`result.sharpe.toFixed(2)`
- 年化收益：`formatPct(result.annual_return_pct)`
- 盈亏比：`result.profit_loss_ratio.toFixed(2)`
- 基准收益：`formatPct(result.benchmark_return_pct)`
- 超额收益：`formatPct(result.excess_return_pct)`

### i18n（`web/src/i18n/locales/{zh,en}.json`，扁平 key）
新增 5 个 key：

| key | zh | en |
|-----|-----|-----|
| `kpi.sharpe` | 夏普比率 | Sharpe Ratio |
| `kpi.annualReturn` | 年化收益 | Annual Return |
| `kpi.profitLossRatio` | 盈亏比 | Profit/Loss Ratio |
| `kpi.benchmarkReturn` | 基准收益 | Benchmark Return |
| `kpi.excessReturn` | 超额收益 | Excess Return |

---

## 测试

### `tests/test_metrics.py`（新建，纯函数单测，不依赖网络/backtrader）
1. `extract_sharpe`：正常值返回 float；`None` → 0.0；缺 key → 0.0。
2. `extract_annual_return_pct`：取 `rnorm100`；缺 key → 0.0。
3. `compute_profit_loss_ratio`：正常 won/lost 算比值；`lost.total==0`/avg 为 0 → 0.0。
4. `compute_benchmark_return_pct`：正常涨跌算百分比；空 list → 0.0；首值 0 → 0.0。
5. `compute_excess_return_pct`：差值正确（含负超额）。

### `tests/test_backtest_service.py`（扩展，复用 FakeHub）
6. 端到端：喂 stock + index 两个 feed，断言 `result` 的 5 个新字段存在且为 float；
   构造已知涨幅的 index feed，断言 `benchmark_return_pct` 符合预期、`excess_return_pct == total_return_pct - benchmark_return_pct`。

### 回归
- `python -m pytest -q tests/` 全绿。现有 service 测试断言是结构性的（`'key' in payload`、`final_value > 0`），加字段不破坏。
- 前端 `npm run build`（tsc）通过。

---

## 落地步骤

1. 新建 `backtest/metrics.py` + `tests/test_metrics.py`（TDD，5 个纯函数）→ 单测全绿。
2. `service.py` 挂 analyzer + 算指标 + 扩 `BacktestResult` → service 端到端测试验证新字段。
3. 前端 `types.ts` + `App.tsx` + i18n → `npm run build` 通过。
4. 全量回归 `python -m pytest -q tests/` → 无回归。
