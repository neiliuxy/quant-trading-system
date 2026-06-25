# Walk-Forward Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在系统内引入 Walk-Forward Optimization —— 把历史切成多个滚动窗口,每段在样本内按 Sharpe 寻优参数,再到紧邻的样本外验证,前端展示裁决卡 + 逐窗柱状图 + 逐窗明细表,帮助用户判断策略是否过拟合、参数是否稳健。

**Architecture:** WFO 是一个纯编排层 (`backtest/walkforward.py`),通过 `trading_calendar` 注入交易日历、循环调用现有的 `run_backtest_service` 执行每窗寻优与 OOS 验证。复用 `/api/jobs` 的后台线程 + artifact 模式落盘。零修改单次回测核心代码。

**Tech Stack:** Python 3, dataclasses, hashlib, FastAPI, SQLite, React + Vite, Recharts, TypeScript.

**Spec:** `docs/superpowers/specs/2026-06-24-walk-forward-optimization-design.md` (commit `fb730c5`)

---

## File Structure

```
backtest/
  walkforward.py             ← 新建:WFO 引擎(数据结构 + run_walkforward)
  data_loader.py             ← 修改:加 default_trading_calendar 公开函数
server/
  db.py                      ← 修改:init_db 加 wfo_runs 表
  jobs.py                    ← 修改:加 5 个 wfo helper
  api.py                     ← 修改:加 3 个端点
  wfo_executor.py            ← 新建:后台执行器
web/src/
  types.ts                   ← 修改:加 WFO 类型
  App.tsx                    ← 修改:加 WFO 配置表单 + 结果页三块布局
  i18n/locales/
    zh.json                  ← 修改:加 21 个 i18n key
    en.json                  ← 修改:加 21 个 i18n key
tests/
  test_walkforward.py        ← 新建:17 个引擎纯逻辑测试
  test_server_wfo.py         ← 新建:6 个 API 测试
  test_db.py                 ← 修改:加新表 schema 测试
```

**依赖关系:** Task 1-6 引擎纯逻辑(自给自足)→ Task 7 data_loader(无依赖)→ Task 8 db schema(无依赖)→ Task 9 jobs helper(依赖 Task 8)→ Task 10 executor(依赖 Task 9, 7, 1-6)→ Task 11 API(依赖 Task 10)→ Task 12-13 前端(依赖 Task 11)→ Task 14 全量回归。

---

## Task 1: 引擎骨架 —— 数据结构 + 入口 + ValueError 校验

**Files:**
- Create: `tests/test_walkforward.py`
- Create: `backtest/walkforward.py`

- [ ] **Step 1: 写失败的测试 —— 数据结构与 ValueError 校验**

```python
# tests/test_walkforward.py
"""WFO 引擎纯逻辑测试。注入 fake run / fake trading_calendar,不依赖 backtrader/DataHub。"""
from dataclasses import asdict

import pytest

from backtest.service import BacktestRequest, BacktestResult
from backtest.walkforward import (
    MAX_GRID_RUNS,
    WfoConfig,
    WfoResult,
    run_walkforward,
)
from strategies.base import StrategyParamSpec, StrategySpec
from strategies.swing_ma_boll import SwingStrategy, SWING_MA_BOLL_SPEC


# ---------- 测试夹具 ----------

def _fake_run(req: BacktestRequest) -> BacktestResult:
    """最简单的 fake:每个请求返回 sharpe=1.0 的固定结果。"""
    return BacktestResult(
        symbol=req.symbol,
        start=req.start,
        end=req.end,
        initial_cash=req.cash,
        final_value=req.cash * 1.05,
        total_return_pct=5.0,
        max_drawdown_pct=1.0,
        trade_count=1,
        win_rate_pct=100.0,
        sharpe=1.0,
    )


def _trading_days_252(start_yyyymmdd: str = '20200101', count: int = 252) -> list[str]:
    """生成 [start_yyyymmdd, ...] 连续 count 个交易日的 YYYYMMDD 字符串(每天 +1)。"""
    from datetime import date, timedelta
    start = date(int(start_yyyymmdd[:4]), int(start_yyyymmdd[4:6]), int(start_yyyymmdd[6:8]))
    return [(start + timedelta(days=i)).strftime('%Y%m%d') for i in range(count)]


def _basic_config(**overrides) -> WfoConfig:
    defaults = dict(
        symbol='000001',
        start='20200101',
        end='20220101',
        cash=100000.0,
        use_market_filter=False,
        strategy_id='swing_ma_boll',
        param_grid={'fast_ma': [10.0, 20.0]},   # 2 取值 → 2 组合
        train_days=120,
        test_days=60,
        step_days=60,
    )
    defaults.update(overrides)
    return WfoConfig(**defaults)


# ---------- ValueError 校验 ----------

def test_rejects_grid_exceeds_max():
    """网格超 MAX_GRID_RUNS 上限直接拒绝,根本不调 run。"""
    called = []

    def must_not_run(req):
        called.append(req)
        return _fake_run(req)

    # 252 个交易日, train_days=120, test_days=60 → 多个窗口;网格 100×100 → 超限
    cfg = _basic_config(
        end='20210101',
        param_grid={'fast_ma': [float(i) for i in range(100)], 'slow_ma': [float(j) for j in range(100)]},
        train_days=120, test_days=60, step_days=60,
    )
    calendar = _trading_days_252('20200101', 252)
    with pytest.raises(ValueError, match='参数网格过大'):
        run_walkforward(cfg, run=must_not_run, trading_calendar=lambda s, st, e: calendar)
    assert called == []


def test_rejects_interval_too_short():
    """交易日总数 < train + test 直接拒绝。"""
    cfg = _basic_config(
        end='20200301',
        train_days=120, test_days=60, step_days=60,
    )
    calendar = _trading_days_252('20200101', 100)   # 不足 180
    with pytest.raises(ValueError, match='少于 train\+test'):
        run_walkforward(cfg, run=_fake_run, trading_calendar=lambda s, st, e: calendar)


def test_rejects_empty_trading_calendar():
    """trading_calendar 返回空列表直接拒绝。"""
    cfg = _basic_config()
    with pytest.raises(ValueError, match='无可用交易日'):
        run_walkforward(cfg, run=_fake_run, trading_calendar=lambda s, st, e: [])


def test_rejects_unknown_param_name():
    """param_grid 的 key 不在 StrategySpec.params → 拒绝,不被 normalized 静默过滤。"""
    cfg = _basic_config(param_grid={'nonexistent_param': [1.0, 2.0]})
    calendar = _trading_days_252('20200101', 300)
    with pytest.raises(ValueError, match='未知参数'):
        run_walkforward(cfg, run=_fake_run, trading_calendar=lambda s, st, e: calendar)


# ---------- 数据结构 ----------

def test_wfo_result_to_dict_has_result_type_and_serializable():
    """WfoResult.to_dict 含 result_type='wfo' 且可被 json.dumps 序列化(没有不可序列化的类型)。"""
    import json
    cfg = _basic_config()
    res = WfoResult(
        config=cfg,
        folds=(),
        summary=_empty_summary(),   # Task 1 骨架版返回的 summary;Task 5 起被 _build_summary 取代
    )
    d = res.to_dict()
    assert d['result_type'] == 'wfo'
    # 关键字段都在
    assert d['config']['symbol'] == '000001'
    # 必须能被 json.dumps
    json.dumps(d, default=str)
```

需要在 `test_walkforward.py` 顶部加临时 `_empty_summary()` —— Task 5 落地后会被删除:

```python
def _empty_summary():
    from backtest.walkforward import WfoSummary
    return WfoSummary(
        fold_count=0, failed_folds=0,
        mean_is_sharpe=0.0, mean_oos_sharpe=0.0,
        efficiency=None, oos_win_folds=0,
        param_stability={},
    )
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `python -m pytest tests/test_walkforward.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backtest.walkforward'`

- [ ] **Step 3: 实现引擎骨架 —— 数据结构与最小入口**

```python
# backtest/walkforward.py
"""WFO 引擎。纯编排,不依赖 backtrader/网络/Web/DataHub。

通过注入 run(单次回测接口)和 trading_calendar(交易日历)实现可测性。
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal, Mapping

from backtest.service import BacktestRequest, BacktestResult
from strategies.registry import get_strategy_spec

MAX_GRID_RUNS = 300
# 初期限流:保护 UX(5 折窗口 × 60 组合 = 300 次样本内回测已接近个人机器分钟级上限)。
# 超此值视为提示缩小网格或缩短区间。常量一行可调,非配置项。

# 类型别名
RunFn = Callable[[BacktestRequest], BacktestResult]
TradingCalendar = Callable[[str, str, str], list[str]]
OnFoldComplete = Callable[[int, int], None]


# ---------- 数据结构 ----------

@dataclass(frozen=True)
class WfoConfig:
    symbol: str
    start: str
    end: str
    cash: float = 100000.0
    use_market_filter: bool = True
    strategy_id: str = 'swing_ma_boll'
    param_grid: Mapping[str, list[float]] = field(default_factory=dict)
    train_days: int = 504
    test_days: int = 126
    step_days: int = 126


@dataclass(frozen=True)
class FoldResult:
    fold_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    best_params: dict[str, Any]
    is_sharpe: float
    is_return_pct: float
    oos_sharpe: float
    oos_return_pct: float
    oos_drawdown_pct: float
    oos_trade_count: int
    no_signal: bool = False
    failed: bool = False


@dataclass(frozen=True)
class ParamStability:
    value: float
    count: int
    mean: float
    std: float
    occurrences: dict[str, int]


@dataclass(frozen=True)
class WfoSummary:
    fold_count: int
    failed_folds: int
    mean_is_sharpe: float
    mean_oos_sharpe: float
    efficiency: float | None
    oos_win_folds: int
    param_stability: dict[str, ParamStability]


@dataclass(frozen=True)
class WfoResult:
    config: WfoConfig
    folds: tuple[FoldResult, ...]
    summary: WfoSummary
    result_type: Literal['wfo'] = 'wfo'

    def to_dict(self) -> dict[str, Any]:
        return {
            'result_type': 'wfo',
            'config': asdict(self.config),
            'folds': [asdict(f) for f in self.folds],
            'summary': {
                **asdict(self.summary),
                'param_stability': {
                    k: asdict(v) for k, v in self.summary.param_stability.items()
                },
            },
        }


# ---------- 入口(骨架) ----------

def run_walkforward(
    config: WfoConfig,
    run: RunFn,
    trading_calendar: TradingCalendar,
    on_fold_complete: OnFoldComplete | None = None,
) -> WfoResult:
    """执行 WFO 分析。骨架版仅做校验,切窗与聚合在后续 Task 接入。"""
    # 1. 校验策略存在 + param_grid 的 key 在策略声明内,且 type 为数值
    spec = get_strategy_spec(config.strategy_id)
    allowed_numeric = {
        p.name for p in spec.params if p.type in ('int', 'float')
    }
    for key in config.param_grid:
        if key not in allowed_numeric:
            raise ValueError(
                f"未知参数 {key},策略 {config.strategy_id} 支持的数值参数为 {sorted(allowed_numeric)}"
            )

    # 2. 校验网格每个参数至少 2 个取值
    for key, values in config.param_grid.items():
        if len(values) < 2:
            raise ValueError(f"参数 {key} 至少需要 2 个取值,实际 {len(values)}")

    # 3. 校验窗口长度
    if config.train_days < 1 or config.test_days < 1 or config.step_days < 1:
        raise ValueError('train_days / test_days / step_days 必须 >= 1')

    # 4. 取交易日历
    trading_days = trading_calendar(config.symbol, config.start, config.end)
    if not trading_days:
        raise ValueError('区间内无可用交易日')

    # 5. 校验区间能装下至少一个 train+test
    if len(trading_days) < config.train_days + config.test_days:
        raise ValueError(
            f"区间仅含 {len(trading_days)} 个交易日,少于 train+test={config.train_days + config.test_days}"
        )

    # 6. 切窗(骨架:先算 fold_count 校验网格上限,实际切窗在 Task 2)
    fold_count = max(0, (len(trading_days) - config.train_days - config.test_days) // config.step_days + 1)
    grid_size = 1
    for v in config.param_grid.values():
        grid_size *= len(v)
    total_runs = fold_count * grid_size
    if total_runs > MAX_GRID_RUNS:
        raise ValueError(
            f"参数网格过大:{total_runs} 次样本内回测 > {MAX_GRID_RUNS} 上限。请缩小网格或缩短区间。"
        )

    # 骨架版不跑实际分析,返回空结果(后续 Task 替换)
    return WfoResult(
        config=config,
        folds=(),
        summary=WfoSummary(
            fold_count=fold_count,
            failed_folds=0,
            mean_is_sharpe=0.0,
            mean_oos_sharpe=0.0,
            efficiency=None,
            oos_win_folds=0,
            param_stability={},
        ),
    )
```

- [ ] **Step 4: 跑测试,确认 ValueError 校验与 to_dict 序列化通过**

Run: `python -m pytest tests/test_walkforward.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add backtest/walkforward.py tests/test_walkforward.py
git commit -m "feat(backtest): WFO engine skeleton - config/result dataclasses + validation"
```

---

## Task 2: 切窗算法 —— 紧密衔接 + 边界处理

**Files:**
- Modify: `tests/test_walkforward.py`
- Modify: `backtest/walkforward.py`

- [ ] **Step 1: 加测试 —— 切窗正确性、紧密衔接、边界**

在 `tests/test_walkforward.py` 末尾追加:

```python
# ---------- 切窗 ----------

def test_window_splitting_tight_continuation():
    """每个窗口的 test_start = train_end 后第一个交易日(紧密衔接)。"""
    cfg = _basic_config(train_days=5, test_days=3, step_days=3)
    calendar = _trading_days_252('20200101', 20)
    # 用一个 fake run 让我们能看到 fold_results
    fold_results_box = []

    def capture_run(req):
        fold_results_box.append(req)
        return _fake_run(req)

    # 通过完整跑一遍拿到 folds 列表(当前骨架不跑切窗,需要先实现切窗;
    # 本测试先在引擎里加一个 _compute_windows 辅助函数,Task 2 Step 3 实现后这个测试会通过)
    from backtest.walkforward import _compute_windows
    windows = _compute_windows(calendar, cfg.train_days, cfg.test_days, cfg.step_days)

    # 20 个交易日, train=5, test=3, step=3
    # 窗口 1: [0..4] train, [5..7] test
    # 窗口 2: [3..7] train, [8..10] test
    # 窗口 3: [6..10] train, [11..13] test
    # 窗口 4: [9..13] train, [14..16] test
    # 窗口 5: [12..16] train, [17..19] test  (test_end=19, 不超 20)
    assert len(windows) == 5, f'期望 5 个窗口,实际 {len(windows)}'

    # 验证每个窗口的 test_start == train_end 的后一个交易日(紧密衔接)
    for ts, te, vs, ve in windows:
        ts_idx = calendar.index(ts)
        te_idx = calendar.index(te)
        vs_idx = calendar.index(vs)
        assert vs_idx == te_idx + 1, (
            f'窗口 test_start={vs} 应紧接 train_end={te},但 calendar 索引 vs={vs_idx} != te+1={te_idx + 1}'
        )

    # 验证第一个窗口
    assert windows[0] == ('20200106', '20200110', '20200111', '20200113')
    # 验证最后一个窗口不超 calendar 末尾
    assert calendar.index(windows[-1][3]) < len(calendar)


def test_window_splitting_skips_when_test_overflows():
    """最后几个窗口若 test_end 超出 calendar 末尾,直接舍去,不补短窗。"""
    cfg = _basic_config(train_days=5, test_days=3, step_days=3)
    calendar = _trading_days_252('20200101', 17)   # 17 个交易日
    from backtest.walkforward import _compute_windows
    windows = _compute_windows(calendar, cfg.train_days, cfg.test_days, cfg.step_days)
    # 17 个交易日, train=5, test=3, step=3
    # 窗口 1: [0..4] + [5..7]
    # 窗口 2: [3..7] + [8..10]
    # 窗口 3: [6..10] + [11..13]
    # 窗口 4: [9..13] + [14..16]
    # 窗口 5: [12..16] + [17..19]  → test_end=calendar[19] 不存在,舍去
    assert len(windows) == 4
    assert windows[-1] == ('20200110', '20200114', '20200115', '20200117')
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `python -m pytest tests/test_walkforward.py::test_window_splitting_tight_continuation tests/test_walkforward.py::test_window_splitting_skips_when_test_overflows -v`
Expected: FAIL with `ImportError: cannot import name '_compute_windows'`

- [ ] **Step 3: 在 `backtest/walkforward.py` 加 `_compute_windows` 私有函数**

```python
def _compute_windows(
    trading_days: list[str],
    train_days: int,
    test_days: int,
    step_days: int,
) -> list[tuple[str, str, str, str]]:
    """基于已排序的交易日列表切滚动窗口,紧密衔接。

    返回 [(train_start, train_end, test_start, test_end), ...],
    条件:train_end + test_end 不超过 trading_days 末尾。
    """
    windows = []
    n = len(trading_days)
    i = 0
    while i + train_days + test_days <= n:
        ts = trading_days[i]
        te = trading_days[i + train_days - 1]
        vs = trading_days[i + train_days]
        ve = trading_days[i + train_days + test_days - 1]
        windows.append((ts, te, vs, ve))
        i += step_days
    return windows
```

- [ ] **Step 4: 跑测试,确认切窗通过**

Run: `python -m pytest tests/test_walkforward.py -v`
Expected: 7 passed

- [ ] **Step 5: 提交**

```bash
git add backtest/walkforward.py tests/test_walkforward.py
git commit -m "feat(backtest): WFO window splitting with tight continuation"
```

---

## Task 3: 参数值类型转换 + 网格笛卡尔积

**Files:**
- Modify: `tests/test_walkforward.py`
- Modify: `backtest/walkforward.py`

- [ ] **Step 1: 加测试 —— int 类型参数候选值转 int、笛卡尔积**

```python
# ---------- 参数值类型转换 + 网格笛卡尔积 ----------

def test_param_value_int_conversion():
    """int 类型参数(StrategySpec.params 中 type='int')的 float 候选值 → 转 int。"""
    from backtest.walkforward import _typed_param_grid
    spec = get_strategy_spec('swing_ma_boll')
    # fast_ma 在 SWING_MA_BOLL_SPEC 中是 int
    typed = _typed_param_grid(spec, {'fast_ma': [10.0, 20.0, 30.0]})
    assert typed == {'fast_ma': [10, 20, 30]}, f'int 参数应转 int,实际 {typed}'


def test_param_value_float_preserved():
    """float 类型参数候选值保持 float。"""
    from backtest.walkforward import _typed_param_grid
    # 找 swing_ma_boll 的一个 float 参数(若有);否则用 citic_wave 的 atr_multiplier
    from strategies.registry import get_strategy_spec
    spec = get_strategy_spec('swing_ma_boll')
    # swing_ma_boll 可能全 int,这里不强求;用一个 stub spec 测试逻辑
    from strategies.base import StrategyParamSpec, StrategySpec
    from strategies.swing_ma_boll import SwingStrategy
    stub_spec = StrategySpec(
        id='stub', name='Stub', description='', strategy_class=SwingStrategy,
        params=(
            StrategyParamSpec('foo', 'Foo', 'float', 1.0),
            StrategyParamSpec('bar', 'Bar', 'int', 10),
        ),
    )
    typed = _typed_param_grid(stub_spec, {'foo': [1.5, 2.5], 'bar': [10.0, 20.0]})
    assert typed == {'foo': [1.5, 2.5], 'bar': [10, 20]}, f'foo 应保留 float、bar 应转 int,实际 {typed}'


def test_cartesian_grid_size():
    """笛卡尔积产出所有组合。"""
    from backtest.walkforward import _cartesian
    combos = list(_cartesian({'a': [1, 2], 'b': [10, 20, 30]}))
    assert len(combos) == 6
    # 每个 combo 是 dict
    assert {'a': 1, 'b': 10} in combos
    assert {'a': 2, 'b': 30} in combos
    # 全部组合覆盖
    expected = {
        frozenset(d.items()) for d in [
            {'a': 1, 'b': 10}, {'a': 1, 'b': 20}, {'a': 1, 'b': 30},
            {'a': 2, 'b': 10}, {'a': 2, 'b': 20}, {'a': 2, 'b': 30},
        ]
    }
    actual = {frozenset(d.items()) for d in combos}
    assert actual == expected
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `python -m pytest tests/test_walkforward.py::test_param_value_int_conversion tests/test_walkforward.py::test_param_value_float_preserved tests/test_walkforward.py::test_cartesian_grid_size -v`
Expected: FAIL with `ImportError: cannot import name '_typed_param_grid'`

- [ ] **Step 3: 在 `backtest/walkforward.py` 加 `_typed_param_grid` 和 `_cartesian`**

```python
from itertools import product as _iter_product


def _typed_param_grid(spec, grid: Mapping[str, list[float]]) -> dict[str, list]:
    """按 spec.params 的 type 字段把候选值转 int 或保持 float。"""
    type_by_name = {p.name: p.type for p in spec.params}
    typed = {}
    for name, values in grid.items():
        t = type_by_name.get(name)
        if t == 'int':
            typed[name] = [int(v) for v in values]
        elif t == 'float':
            typed[name] = [float(v) for v in values]
        else:
            # 非数值参数在校验阶段已被拒绝,这里兜底保持原值
            typed[name] = list(values)
    return typed


def _cartesian(grid: Mapping[str, list]) -> list[dict]:
    """生成网格的笛卡尔积,每个 combo 是一个 dict(name -> value)。"""
    if not grid:
        return [{}]
    keys = list(grid.keys())
    values_lists = [grid[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in _iter_product(*values_lists)]
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `python -m pytest tests/test_walkforward.py -v`
Expected: 10 passed

- [ ] **Step 5: 提交**

```bash
git add backtest/walkforward.py tests/test_walkforward.py
git commit -m "feat(backtest): WFO typed param grid + cartesian product"
```

---

## Task 4: 每窗寻优 + OOS 验证 + 失败/no_signal 处理

**Files:**
- Modify: `tests/test_walkforward.py`
- Modify: `backtest/walkforward.py`

- [ ] **Step 1: 加测试 —— 选最优、OOS 用最优参数、零成交 no_signal、异常 failed**

```python
# ---------- 每窗寻优 + OOS ----------

def _varying_sharpe_run(target_by_combo: dict[tuple, float]):
    """fake run:根据 (sort_key of combo) 返回不同 sharpe 用于验证选优逻辑。"""
    def run(req: BacktestRequest) -> BacktestResult:
        combo_key = tuple(sorted(req.strategy_params.items()))
        sharpe = target_by_combo.get(combo_key, 0.5)
        return BacktestResult(
            symbol=req.symbol, start=req.start, end=req.end,
            initial_cash=req.cash, final_value=req.cash * (1 + sharpe / 100),
            total_return_pct=sharpe, max_drawdown_pct=1.0,
            trade_count=1, win_rate_pct=100.0, sharpe=sharpe,
        )
    return run


def test_picks_highest_sharpe_in_fold():
    """每窗按样本内 sharpe 选最优组合。"""
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 20.0]},
    )
    calendar = _trading_days_252('20200101', 20)
    # combo ('fast_ma', 10) → sharpe 0.5; combo ('fast_ma', 20) → sharpe 2.0
    run = _varying_sharpe_run({
        (('fast_ma', 10),): 0.5,
        (('fast_ma', 20),): 2.0,
    })
    result = run_walkforward(cfg, run=run, trading_calendar=lambda s, st, e: calendar)
    assert result.summary.fold_count >= 1
    first_fold = result.folds[0]
    assert first_fold.best_params == {'fast_ma': 20}, f'应选 fast_ma=20,实际 {first_fold.best_params}'
    assert first_fold.is_sharpe == 2.0


def test_oos_uses_best_params():
    """OOS 调用的 request.strategy_params 应是当窗的 best_params。"""
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 20.0]},
    )
    calendar = _trading_days_252('20200101', 20)
    oos_calls = []

    def tracking_run(req: BacktestRequest) -> BacktestResult:
        # 区分 IS vs OOS:看 start/end
        if req.start == cfg.start or len(req.start) == 8 and req.end < '20201201':
            pass  # IS
        oos_calls.append(req)
        return _fake_run(req)

    run = _varying_sharpe_run({
        (('fast_ma', 10),): 0.5,
        (('fast_ma', 20),): 2.0,
    })
    result = run_walkforward(cfg, run=run, trading_calendar=lambda s, st, e: calendar)
    # 每个 fold 至少有 1 次 OOS 调用,且 OOS 调用的 strategy_params 是 best_params
    assert len(oos_calls) >= result.summary.fold_count
    for fold, oos_req in zip(result.folds[: len(oos_calls)], oos_calls[: result.summary.fold_count]):
        assert oos_req.strategy_params['fast_ma'] == fold.best_params['fast_ma']


def test_no_signal_when_all_combos_zero_trades():
    """全部组合零成交 → fold.no_signal=True,OOS 用默认参数跑(不放弃整窗)。"""
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 20.0]},
    )
    calendar = _trading_days_252('20200101', 20)

    def zero_trade_run(req: BacktestRequest) -> BacktestResult:
        return BacktestResult(
            symbol=req.symbol, start=req.start, end=req.end,
            initial_cash=req.cash, final_value=req.cash,
            total_return_pct=0.0, max_drawdown_pct=0.0,
            trade_count=0, win_rate_pct=0.0, sharpe=None,   # Sharpe=None
        )

    result = run_walkforward(cfg, run=zero_trade_run, trading_calendar=lambda s, st, e: calendar)
    assert result.folds, '应至少有 1 个窗口'
    for fold in result.folds:
        assert fold.no_signal is True, f'零成交窗应标记 no_signal,fold {fold.fold_index} 没有'
        assert fold.best_params == {}, 'no_signal 窗 best_params 应为空'
        assert fold.failed is False, 'no_signal 不是 failed'


def test_failed_fold_on_exception():
    """某次回测异常 → fold.failed=True,该窗不进均值/胜窗。"""
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 20.0]},
    )
    calendar = _trading_days_252('20200101', 20)

    def boom_run(req: BacktestRequest) -> BacktestResult:
        raise RuntimeError('simulated error')

    result = run_walkforward(cfg, run=boom_run, trading_calendar=lambda s, st, e: calendar)
    assert result.summary.failed_folds == result.summary.fold_count
    assert all(f.failed for f in result.folds)
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `python -m pytest tests/test_walkforward.py::test_picks_highest_sharpe_in_fold tests/test_walkforward.py::test_oos_uses_best_params tests/test_walkforward.py::test_no_signal_when_all_combos_zero_trades tests/test_walkforward.py::test_failed_fold_on_exception -v`
Expected: FAIL with `AssertionError` 或 fold 为空(因为骨架版不跑实际分析)

- [ ] **Step 3: 在 `backtest/walkforward.py` 替换 `run_walkforward` 骨架为完整实现**

把 `backtest/walkforward.py` 中现有的 `run_walkforward` 函数体替换为:

```python
def run_walkforward(
    config: WfoConfig,
    run: RunFn,
    trading_calendar: TradingCalendar,
    on_fold_complete: OnFoldComplete | None = None,
) -> WfoResult:
    """执行 WFO 分析。"""
    # 1. 校验(同 Task 1 骨架)
    spec = get_strategy_spec(config.strategy_id)
    allowed_numeric = {p.name for p in spec.params if p.type in ('int', 'float')}
    for key in config.param_grid:
        if key not in allowed_numeric:
            raise ValueError(
                f"未知参数 {key},策略 {config.strategy_id} 支持的数值参数为 {sorted(allowed_numeric)}"
            )
    for key, values in config.param_grid.items():
        if len(values) < 2:
            raise ValueError(f"参数 {key} 至少需要 2 个取值,实际 {len(values)}")
    if config.train_days < 1 or config.test_days < 1 or config.step_days < 1:
        raise ValueError('train_days / test_days / step_days 必须 >= 1')

    trading_days = trading_calendar(config.symbol, config.start, config.end)
    if not trading_days:
        raise ValueError('区间内无可用交易日')
    if len(trading_days) < config.train_days + config.test_days:
        raise ValueError(
            f"区间仅含 {len(trading_days)} 个交易日,少于 train+test={config.train_days + config.test_days}"
        )

    # 2. 切窗
    windows = _compute_windows(
        trading_days, config.train_days, config.test_days, config.step_days,
    )
    total_folds = len(windows)

    # 3. 参数值类型转换 + 笛卡尔积
    typed_grid = _typed_param_grid(spec, config.param_grid)
    combos = _cartesian(typed_grid)
    base_params = spec.defaults

    # 4. 网格上限校验(在切窗后用真实 fold_count 算)
    total_runs = total_folds * len(combos)
    if total_runs > MAX_GRID_RUNS:
        raise ValueError(
            f"参数网格过大:{total_runs} 次样本内回测 > {MAX_GRID_RUNS} 上限。请缩小网格或缩短区间。"
        )

    # 5. 每窗寻优 + OOS
    fold_results: list[FoldResult] = []
    for fold_idx, (ts, te, vs, ve) in enumerate(windows):
        try:
            best_combo: dict | None = None
            best_sharpe = float('-inf')
            for combo in combos:
                req = BacktestRequest(
                    symbol=config.symbol, start=ts, end=te,
                    cash=config.cash, use_market_filter=config.use_market_filter,
                    strategy_id=config.strategy_id,
                    strategy_params={**base_params, **combo},
                )
                result = run(req)
                sharpe = result.sharpe if result.sharpe is not None else float('-inf')
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_combo = combo

            if best_sharpe == float('-inf') or best_combo is None:
                # 全部组合零成交 → no_signal,OOS 用默认参数
                oos_req = BacktestRequest(
                    symbol=config.symbol, start=vs, end=ve,
                    cash=config.cash, use_market_filter=config.use_market_filter,
                    strategy_id=config.strategy_id,
                    strategy_params=dict(base_params),
                )
                oos_result = run(oos_req)
                fold_results.append(FoldResult(
                    fold_index=fold_idx, train_start=ts, train_end=te,
                    test_start=vs, test_end=ve,
                    best_params={}, is_sharpe=0.0, is_return_pct=0.0,
                    oos_sharpe=oos_result.sharpe or 0.0,
                    oos_return_pct=oos_result.total_return_pct,
                    oos_drawdown_pct=oos_result.max_drawdown_pct,
                    oos_trade_count=oos_result.trade_count,
                    no_signal=True,
                ))
            else:
                oos_req = BacktestRequest(
                    symbol=config.symbol, start=vs, end=ve,
                    cash=config.cash, use_market_filter=config.use_market_filter,
                    strategy_id=config.strategy_id,
                    strategy_params={**base_params, **best_combo},
                )
                oos_result = run(oos_req)
                fold_results.append(FoldResult(
                    fold_index=fold_idx, train_start=ts, train_end=te,
                    test_start=vs, test_end=ve,
                    best_params=best_combo,
                    is_sharpe=best_sharpe,
                    is_return_pct=0.0,
                    oos_sharpe=oos_result.sharpe or 0.0,
                    oos_return_pct=oos_result.total_return_pct,
                    oos_drawdown_pct=oos_result.max_drawdown_pct,
                    oos_trade_count=oos_result.trade_count,
                ))
        except Exception:
            fold_results.append(FoldResult(
                fold_index=fold_idx, train_start=ts, train_end=te,
                test_start=vs, test_end=ve,
                best_params={}, is_sharpe=0.0, is_return_pct=0.0,
                oos_sharpe=0.0, oos_return_pct=0.0,
                oos_drawdown_pct=0.0, oos_trade_count=0,
                failed=True,
            ))
        if on_fold_complete is not None:
            on_fold_complete(fold_idx + 1, total_folds)

    # 6. 汇总(Task 5 实现,这里给空骨架)
    summary = _build_summary(fold_results)
    return WfoResult(config=config, folds=tuple(fold_results), summary=summary)
```

并在文件顶部加辅助:

```python
from statistics import mean as _mean, pstdev as _pstdev
from collections import Counter as _Counter


def _build_summary(fold_results: list[FoldResult]) -> 'WfoSummary':
    """聚合 summary。Task 1-4 期间的骨架版本(只算 fold_count/failed_folds),Task 5 完整实现替换。"""
    return WfoSummary(
        fold_count=len(fold_results),
        failed_folds=sum(1 for f in fold_results if f.failed),
        mean_is_sharpe=0.0,
        mean_oos_sharpe=0.0,
        efficiency=None,
        oos_win_folds=0,
        param_stability={},
    )
```

- [ ] **Step 4: 跑测试,确认选优/OOS/no_signal/failed 通过**

Run: `python -m pytest tests/test_walkforward.py -v`
Expected: 14 passed

- [ ] **Step 5: 提交**

```bash
git add backtest/walkforward.py tests/test_walkforward.py
git commit -m "feat(backtest): WFO per-fold optimization + OOS + no_signal/failed handling"
```

---

## Task 5: 汇总 summary —— valid_is/valid_oos 拆集合 + param_stability + efficiency 回退

**Files:**
- Modify: `tests/test_walkforward.py`
- Modify: `backtest/walkforward.py`

- [ ] **Step 1: 加测试 —— summary 计算、no_signal 拆集合、efficiency 回退、occurrences JSON 合法**

```python
# ---------- 汇总 summary ----------

def test_summary_valid_is_oos_split():
    """no_signal 窗不进 mean_is_sharpe/param_stability,但进 mean_oos_sharpe/oos_win_folds。"""
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 20.0]},
    )
    calendar = _trading_days_252('20200101', 20)

    # 设计 fake:根据请求的 end 日期区分 IS/OOS;IS 时按 train_start 区分前两个 fold(正常)与第三个 fold(零成交)
    def controlled_run(req: BacktestRequest) -> BacktestResult:
        train_starts = ['20200101', '20200104', '20200107']
        is_train = req.end in ('20200105', '20200107', '20200110')
        if is_train:
            train_start = req.start
            if train_start in train_starts[:2]:
                # 前两个 fold:正常
                return BacktestResult(
                    symbol=req.symbol, start=req.start, end=req.end,
                    initial_cash=req.cash, final_value=req.cash * 1.05,
                    total_return_pct=5.0, max_drawdown_pct=1.0,
                    trade_count=1, win_rate_pct=100.0, sharpe=1.5,
                )
            else:
                # 第三个 fold:零成交
                return BacktestResult(
                    symbol=req.symbol, start=req.start, end=req.end,
                    initial_cash=req.cash, final_value=req.cash,
                    total_return_pct=0.0, max_drawdown_pct=0.0,
                    trade_count=0, win_rate_pct=0.0, sharpe=None,
                )
        # OOS:都返回 sharpe=0.8(供 mean_oos_sharpe 计算)
        return BacktestResult(
            symbol=req.symbol, start=req.start, end=req.end,
            initial_cash=req.cash, final_value=req.cash * 1.04,
            total_return_pct=4.0, max_drawdown_pct=1.0,
            trade_count=1, win_rate_pct=100.0, sharpe=0.8,
        )

    result = run_walkforward(cfg, run=controlled_run, trading_calendar=lambda s, st, e: calendar)
    # 至少 3 个 fold
    assert result.summary.fold_count >= 3
    no_signal_folds = [f for f in result.folds if f.no_signal]
    normal_folds = [f for f in result.folds if not f.no_signal and not f.failed]
    assert no_signal_folds, '应至少有 1 个 no_signal fold'
    assert normal_folds, '应至少有 1 个正常 fold'

    # mean_is_sharpe 只算 normal_folds
    expected_is_mean = sum(f.is_sharpe for f in normal_folds) / len(normal_folds)
    assert abs(result.summary.mean_is_sharpe - expected_is_mean) < 1e-9

    # mean_oos_sharpe 包含 normal + no_signal(都有 OOS)
    expected_oos_mean = sum(f.oos_sharpe for f in result.folds if not f.failed) / sum(1 for f in result.folds if not f.failed)
    assert abs(result.summary.mean_oos_sharpe - expected_oos_mean) < 1e-9

    # oos_win_folds 同上范围
    expected_oos_wins = sum(1 for f in result.folds if not f.failed and f.oos_sharpe > 0)
    assert result.summary.oos_win_folds == expected_oos_wins


def test_efficiency_none_when_is_nonpositive():
    """mean_is_sharpe <= 0 → efficiency=None。"""
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 20.0]},
    )
    calendar = _trading_days_252('20200101', 20)

    def losing_run(req: BacktestRequest) -> BacktestResult:
        return BacktestResult(
            symbol=req.symbol, start=req.start, end=req.end,
            initial_cash=req.cash, final_value=req.cash * 0.95,
            total_return_pct=-5.0, max_drawdown_pct=10.0,
            trade_count=1, win_rate_pct=0.0, sharpe=-0.5,
        )

    result = run_walkforward(cfg, run=losing_run, trading_calendar=lambda s, st, e: calendar)
    assert result.summary.mean_is_sharpe <= 0
    assert result.summary.efficiency is None


def test_occurrences_keys_are_strings_for_json():
    """occurrences 的键必须是 str(float) 以保证 json.dumps 不抛。"""
    import json
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 15.0, 20.0]},   # 全 float
    )
    calendar = _trading_days_252('20200101', 30)

    def run(req: BacktestRequest) -> BacktestResult:
        # 让 fast_ma=20 总是最优
        sharpe = 3.0 if req.strategy_params.get('fast_ma') == 20 else 1.0
        return BacktestResult(
            symbol=req.symbol, start=req.start, end=req.end,
            initial_cash=req.cash, final_value=req.cash * 1.05,
            total_return_pct=5.0, max_drawdown_pct=1.0,
            trade_count=1, win_rate_pct=100.0, sharpe=sharpe,
        )

    result = run_walkforward(cfg, run=run, trading_calendar=lambda s, st, e: calendar)
    ps = result.summary.param_stability.get('fast_ma')
    assert ps is not None
    # 所有键必须是 str
    for k in ps.occurrences:
        assert isinstance(k, str), f'occurrences key 必须是 str,实际 {type(k).__name__}={k!r}'
    # json.dumps 不抛
    json.dumps(asdict(result))
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `python -m pytest tests/test_walkforward.py::test_summary_valid_is_oos_split tests/test_walkforward.py::test_efficiency_none_when_is_nonpositive tests/test_walkforward.py::test_occurrences_keys_are_strings_for_json -v`
Expected: FAIL —— Task 4 阶段 `_build_summary` 仅算 fold_count/failed_folds,会断言失败

- [ ] **Step 3: 替换 `backtest/walkforward.py` 中的 `_build_summary` 为完整实现**

```python
def _build_summary(fold_results: list[FoldResult]) -> WfoSummary:
    """按 valid_is / valid_oos 拆集合汇总 summary。"""
    fold_count = len(fold_results)
    failed_folds = sum(1 for f in fold_results if f.failed)

    valid_is = [f for f in fold_results if not f.failed and not f.no_signal]
    valid_oos = [f for f in fold_results if not f.failed]

    mean_is_sharpe = _mean([f.is_sharpe for f in valid_is]) if valid_is else 0.0
    mean_oos_sharpe = _mean([f.oos_sharpe for f in valid_oos]) if valid_oos else 0.0
    efficiency = (mean_oos_sharpe / mean_is_sharpe) if mean_is_sharpe > 0 else None
    oos_win_folds = sum(1 for f in valid_oos if f.oos_sharpe > 0)

    # param_stability:仅取 valid_is 的 best_params(name 维度)
    param_stability: dict[str, ParamStability] = {}
    if valid_is:
        all_param_names = set()
        for f in valid_is:
            all_param_names.update(f.best_params.keys())
        for name in sorted(all_param_names):
            values = [f.best_params[name] for f in valid_is if name in f.best_params]
            if not values:
                continue
            values_counter = _Counter(values)
            occurrences = {str(v): c for v, c in values_counter.items()}
            mode_value, mode_count = max(
                occurrences.items(), key=lambda kv: (kv[1], -list(occurrences).index(kv[0])),
            )
            # ties:max 会按 key 顺序取第一个出现的,这里 occurrences 是 dict,Python 3.7+ 保持插入顺序
            param_stability[name] = ParamStability(
                value=float(mode_value),
                count=mode_count,
                mean=_mean(values),
                std=_pstdev(values) if len(values) >= 2 else 0.0,
                occurrences=occurrences,
            )

    return WfoSummary(
        fold_count=fold_count,
        failed_folds=failed_folds,
        mean_is_sharpe=mean_is_sharpe,
        mean_oos_sharpe=mean_oos_sharpe,
        efficiency=efficiency,
        oos_win_folds=oos_win_folds,
        param_stability=param_stability,
    )
```

**注意:** `max(occurrences.items(), key=lambda kv: ...)` 的 ties 行为用插入顺序保证。Python 3.7+ dict 保序,`Counter(values)` 输出按计数递减、再按首次出现顺序 —— 已能直接 `max(occurrences.items(), key=lambda kv: kv[1])` 拿首次出现的众数。把上面 lambda 简化为:

```python
mode_value, mode_count = max(occurrences.items(), key=lambda kv: kv[1])
```

- [ ] **Step 4: 跑测试,确认全部通过**

Run: `python -m pytest tests/test_walkforward.py -v`
Expected: 17 passed

- [ ] **Step 5: 提交**

```bash
git add backtest/walkforward.py tests/test_walkforward.py
git commit -m "feat(backtest): WFO summary with valid_is/oos split, param_stability, efficiency fallback"
```

---

## Task 6: 进度回调 + to_dict 序列化 + 清理测试夹具

**Files:**
- Modify: `tests/test_walkforward.py`
- Modify: `backtest/walkforward.py`

- [ ] **Step 1: 加测试 —— 进度回调 + to_dict 完整结构**

```python
# ---------- 进度回调 + 序列化 ----------

def test_on_fold_complete_receives_predicted_total():
    """on_fold_complete(current, total) 的 total 必须是预计算的 total_folds。"""
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 20.0]},
    )
    calendar = _trading_days_252('20200101', 20)
    progress = []

    def tracking(req: BacktestRequest) -> BacktestResult:
        return _fake_run(req)

    result = run_walkforward(
        cfg, run=tracking, trading_calendar=lambda s, st, e: calendar,
        on_fold_complete=lambda c, t: progress.append((c, t)),
    )
    assert progress, '进度回调应至少被调用一次'
    # 所有回调的 total 必须相同且 == fold_count
    totals = [t for _, t in progress]
    assert len(set(totals)) == 1, f'total 应一致,实际 {totals}'
    assert totals[0] == result.summary.fold_count
    # current 必须是 1..fold_count 严格递增
    currents = [c for c, _ in progress]
    assert currents == list(range(1, result.summary.fold_count + 1))


def test_to_dict_full_structure_jsonable():
    """完整 WfoResult.to_dict 含 result_type='wfo'、可 json.dumps。"""
    import json
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 20.0]},
    )
    calendar = _trading_days_252('20200101', 20)
    result = run_walkforward(cfg, run=_fake_run, trading_calendar=lambda s, st, e: calendar)
    d = result.to_dict()
    assert d['result_type'] == 'wfo'
    assert d['config']['symbol'] == '000001'
    assert d['config']['strategy_id'] == 'swing_ma_boll'
    assert isinstance(d['folds'], list)
    assert 'param_stability' in d['summary']
    # 完整 JSON 序列化
    s = json.dumps(d)
    assert 'wfo' in s
```

- [ ] **Step 2: 跑测试,确认全部通过(Task 6 实际上不需新代码,确认现有覆盖)**

Run: `python -m pytest tests/test_walkforward.py -v`
Expected: 19 passed

- [ ] **Step 3: 删除 Task 1 留下的占位 `_empty_summary`(已被实际 summary 取代,无引用)**

确认 `tests/test_walkforward.py` 顶部没有残留:

```bash
grep -n "_empty_summary" tests/test_walkforward.py || echo "OK no残留"
```

如果有,从 `tests/test_walkforward.py` 顶部删除 `_empty_summary` 函数定义。

- [ ] **Step 4: 跑测试 + 全量回归**

Run: `python -m pytest tests/test_walkforward.py -v`
Expected: 19 passed

Run: `python -m pytest -q tests/`
Expected: 所有已有测试 + 19 个新测试全绿,无回归

- [ ] **Step 5: 提交**

```bash
git add backtest/walkforward.py tests/test_walkforward.py
git commit -m "feat(backtest): WFO progress callback + to_dict verification, remove placeholder"
```

---

## Task 7: data_loader.default_trading_calendar 公开函数

**Files:**
- Modify: `backtest/data_loader.py`
- Create: `tests/test_data_loader_calendar.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_data_loader_calendar.py
"""default_trading_calendar 测试 —— 走 DataHub(已有 FakeHub 模式参考 test_backtest_service.py)。"""
import os
import pytest

from backtest.data_loader import default_trading_calendar


def test_returns_sorted_dates_from_fake_hub(monkeypatch):
    """注入 fake datahub,验证返回的日期列表按 YYYYMMDD 升序。"""

    class FakeFrame:
        def __init__(self, dates):
            import pandas as pd
            self._df = pd.DataFrame({'date': pd.to_datetime(dates)})

        @property
        def empty(self):
            return self._df.empty

        def __getitem__(self, key):
            return self._df[key]

        @property
        def columns(self):
            return self._df.columns

    class FakeHub:
        def __init__(self, dates):
            self._frame = FakeFrame(dates)

        def get_dataset(self, request):
            class Result:
                pass
            r = Result()
            r.frame = self._frame
            return r

    # 用 datahub.service.DataHub 作为注入点:monkeypatch 替换构造函数
    import datahub.service
    monkeypatch.setattr(
        datahub.service, 'DataHub',
        lambda **kwargs: FakeHub(['2020-01-02', '2020-01-01', '2020-01-03']),
    )

    dates = default_trading_calendar('000001', '20200101', '20200131')
    assert dates == ['20200101', '20200102', '20200103'], f'应排序后输出,实际 {dates}'


def test_returns_empty_when_no_data(monkeypatch):
    class FakeFrame:
        empty = True
        def __getitem__(self, key): return None

    class FakeHub:
        def get_dataset(self, request):
            class Result: pass
            r = Result()
            r.frame = FakeFrame()
            return r

    import datahub.service
    monkeypatch.setattr(datahub.service, 'DataHub', lambda **kwargs: FakeHub())

    assert default_trading_calendar('000001', '20200101', '20200131') == []
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `python -m pytest tests/test_data_loader_calendar.py -v`
Expected: FAIL with `ImportError: cannot import name 'default_trading_calendar'`

- [ ] **Step 3: 在 `backtest/data_loader.py` 末尾追加 `default_trading_calendar`**

读 `backtest/data_loader.py` 末尾确认导入区,然后追加:

```python
# backtest/data_loader.py 末尾追加

def default_trading_calendar(symbol: str, start: str, end: str) -> list[str]:
    """WFO 引擎 trading_calendar 的默认实现:走 DataHub 取 stock_daily 日期索引。

    返回 [start, end] 区间内按交易日排序的 YYYYMMDD 字符串列表;数据为空返回空列表。
    """
    import os
    from datahub.service import DataHub
    from datahub.models import DatasetRequest
    from server.db import init_db, DEFAULT_DB_PATH

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hub = DataHub(root_dir=project_root, conn=init_db(DEFAULT_DB_PATH))
    df = hub.get_dataset(DatasetRequest(
        dataset_type='stock_daily', symbol=symbol, start=start, end=end,
    )).frame
    if df is None or df.empty:
        return []
    return sorted(df['date'].dt.strftime('%Y%m%d').tolist())
```

注意:测试 monkeypatch 的是 `datahub.service.DataHub`,所以 `default_trading_calendar` 必须从 `datahub.service` import 这个类(不要 `from datahub.service import DataHub` 后再 `DataHub(...)`,那样 monkeypatch 不到)。

- [ ] **Step 4: 跑测试,确认通过**

Run: `python -m pytest tests/test_data_loader_calendar.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add backtest/data_loader.py tests/test_data_loader_calendar.py
git commit -m "feat(backtest): default_trading_calendar public function in data_loader"
```

---

## Task 8: db wfo_runs 表 schema

**Files:**
- Modify: `server/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: 读 `server/db.py` 找 `init_db`**

读现有 `init_db`,找到 schema 创建的位置(通常用 `CREATE TABLE IF NOT EXISTS`)。注意现有 schema 末尾的位置。

- [ ] **Step 2: 在 `tests/test_db.py` 末尾追加 schema 测试**

```python
# tests/test_db.py 末尾追加

def test_wfo_runs_table_created():
    """init_db 应创建 wfo_runs 表,含全部字段和索引。"""
    import os
    import tempfile
    from server.db import init_db

    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        db_path = tmp.name
    try:
        conn = init_db(db_path)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='wfo_runs'"
        ).fetchall()
        assert rows, 'wfo_runs 表应被创建'

        cols = conn.execute('PRAGMA table_info(wfo_runs)').fetchall()
        col_names = {c[1] for c in cols}
        expected = {
            'id', 'run_key', 'status', 'symbol', 'start_date', 'end_date',
            'strategy_id', 'config_json', 'artifact_path',
            'current_fold', 'total_folds', 'error',
            'created_at', 'updated_at',
        }
        assert expected <= col_names, f'wfo_runs 缺字段:{expected - col_names}'

        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='wfo_runs'"
        ).fetchall()
        index_names = {r[0] for r in indexes}
        assert 'idx_wfo_runs_run_key' in index_names
    finally:
        os.unlink(db_path)
```

- [ ] **Step 3: 跑测试,确认失败**

Run: `python -m pytest tests/test_db.py::test_wfo_runs_table_created -v`
Expected: FAIL with assertion `'wfo_runs 表应被创建'`

- [ ] **Step 4: 在 `server/db.py` 的 `init_db` 末尾加 wfo_runs 建表 SQL**

```sql
CREATE TABLE IF NOT EXISTS wfo_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_key TEXT NOT NULL,
    status TEXT NOT NULL,
    symbol TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    config_json TEXT NOT NULL,
    artifact_path TEXT,
    current_fold INTEGER DEFAULT 0,
    total_folds INTEGER DEFAULT 0,
    error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wfo_runs_run_key ON wfo_runs(run_key);
```

- [ ] **Step 5: 跑测试,确认通过**

Run: `python -m pytest tests/test_db.py -v`
Expected: 全部通过(含新增)

- [ ] **Step 6: 提交**

```bash
git add server/db.py tests/test_db.py
git commit -m "feat(server): wfo_runs table schema"
```

---

## Task 9: server/jobs.py 5 个 wfo helper

**Files:**
- Modify: `server/jobs.py`
- Create: `tests/test_server_wfo_jobs.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_server_wfo_jobs.py
"""server/jobs.py 的 wfo helper 测试。"""
import json
import os
import tempfile

import pytest

from server.db import init_db
from server.jobs import (
    create_wfo_run, get_wfo_run, update_wfo_run_status,
    update_wfo_run_progress, mark_wfo_run_completed,
)


@pytest.fixture
def db_conn():
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        db_path = tmp.name
    conn = init_db(db_path)
    yield conn
    conn.close()
    os.unlink(db_path)


def _sample_config_json():
    return json.dumps({
        'symbol': '000001', 'start': '20200101', 'end': '20210101',
        'cash': 100000.0, 'use_market_filter': False,
        'strategy_id': 'swing_ma_boll',
        'param_grid': {'fast_ma': [10.0, 20.0]},
        'train_days': 120, 'test_days': 60, 'step_days': 60,
    })


def test_create_wfo_run_returns_queued_row(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    assert row['status'] == 'queued'
    assert row['symbol'] == '000001'
    assert row['strategy_id'] == 'swing_ma_boll'
    assert row['run_key']


def test_get_wfo_run_returns_row(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched is not None
    assert fetched['id'] == row['id']


def test_update_wfo_run_status(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    update_wfo_run_status(db_conn, row['id'], 'running')
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'running'
    update_wfo_run_status(db_conn, row['id'], 'failed', 'some error')
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'failed'
    assert fetched['error'] == 'some error'


def test_update_wfo_run_progress(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    update_wfo_run_progress(db_conn, row['id'], 2, 5)
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['current_fold'] == 2
    assert fetched['total_folds'] == 5


def test_mark_wfo_run_completed(db_conn):
    row = create_wfo_run(db_conn, _sample_config_json(), 'swing_ma_boll', '000001',
                          '20200101', '20210101')
    artifact_path = '/tmp/wfo_test_artifact.json'
    mark_wfo_run_completed(db_conn, row['id'], artifact_path)
    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'completed'
    assert fetched['artifact_path'] == artifact_path
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `python -m pytest tests/test_server_wfo_jobs.py -v`
Expected: FAIL with `ImportError: cannot import name 'create_wfo_run'`

- [ ] **Step 3: 在 `server/jobs.py` 末尾追加 5 个 helper**

```python
# server/jobs.py 末尾追加

import hashlib
import json as _json_wfo


def _wfo_run_key(config_json: str, code_version: str | None = None) -> str:
    payload = {
        'config': _json_wfo.loads(config_json),
        'code_version': code_version or current_code_version(),
    }
    encoded = _json_wfo.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


def create_wfo_run(conn, config_json: str, strategy_id: str, symbol: str,
                   start_date: str, end_date: str) -> dict[str, Any]:
    run_key = _wfo_run_key(config_json)
    cur = conn.execute(
        """
        INSERT INTO wfo_runs (
            run_key, status, symbol, start_date, end_date,
            strategy_id, config_json
        ) VALUES (?, 'queued', ?, ?, ?, ?, ?)
        """,
        (run_key, symbol, start_date, end_date, strategy_id, config_json),
    )
    conn.commit()
    return get_wfo_run(conn, cur.lastrowid)


def get_wfo_run(conn, wfo_id: int) -> dict[str, Any] | None:
    row = conn.execute('SELECT * FROM wfo_runs WHERE id = ?', (wfo_id,)).fetchone()
    return dict(row) if row is not None else None


def update_wfo_run_status(conn, wfo_id: int, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE wfo_runs SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, error, wfo_id),
    )
    conn.commit()


def update_wfo_run_progress(conn, wfo_id: int, current_fold: int, total_folds: int) -> None:
    conn.execute(
        "UPDATE wfo_runs SET current_fold = ?, total_folds = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (current_fold, total_folds, wfo_id),
    )
    conn.commit()


def mark_wfo_run_completed(conn, wfo_id: int, artifact_path: str) -> None:
    conn.execute(
        "UPDATE wfo_runs SET status = 'completed', artifact_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (artifact_path, wfo_id),
    )
    conn.commit()
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `python -m pytest tests/test_server_wfo_jobs.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add server/jobs.py tests/test_server_wfo_jobs.py
git commit -m "feat(server): 5 wfo helpers in jobs.py"
```

---

## Task 10: server/wfo_executor.py

**Files:**
- Create: `server/wfo_executor.py`
- Modify: `tests/test_server_wfo_jobs.py`(或新建 executor 测试文件)

- [ ] **Step 1: 写失败的测试**

在 `tests/test_server_wfo_jobs.py` 末尾追加,或新建 `tests/test_wfo_executor.py`:

```python
# tests/test_wfo_executor.py
"""wfo_executor 测试 —— 注入 fake run_walkforward,验证线程 + artifact + DB 状态。"""
import json
import os
import tempfile
import threading
import time

import pytest

from backtest.walkforward import WfoConfig, WfoResult, WfoSummary
from server.db import init_db
from server.jobs import (
    create_wfo_run, get_wfo_run,
)
from server.wfo_executor import execute_wfo_once, submit_wfo_background


@pytest.fixture
def db_conn():
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        db_path = tmp.name
    conn = init_db(db_path)
    yield conn
    conn.close()
    os.unlink(db_path)


@pytest.fixture
def artifact_dir(tmp_path):
    d = tmp_path / 'artifacts'
    d.mkdir()
    return str(d)


def _minimal_config_json():
    return json.dumps({
        'symbol': '000001', 'start': '20200101', 'end': '20210101',
        'cash': 100000.0, 'use_market_filter': False,
        'strategy_id': 'swing_ma_boll',
        'param_grid': {'fast_ma': [10.0, 20.0]},
        'train_days': 120, 'test_days': 60, 'step_days': 60,
    })


def test_execute_wfo_once_writes_artifact_and_marks_completed(db_conn, artifact_dir, monkeypatch):
    """execute_wfo_once:fake 引擎返回 WfoResult → 写 artifact → mark_completed。"""
    from backtest.walkforward import FoldResult

    def fake_run_walkforward(config, run, trading_calendar, on_fold_complete=None):
        return WfoResult(
            config=config,
            folds=(FoldResult(
                fold_index=0, train_start='20200101', train_end='20200601',
                test_start='20200602', test_end='20200801',
                best_params={'fast_ma': 20}, is_sharpe=1.5, is_return_pct=5.0,
                oos_sharpe=0.8, oos_return_pct=3.0, oos_drawdown_pct=1.0,
                oos_trade_count=5,
            ),),
            summary=WfoSummary(
                fold_count=1, failed_folds=0,
                mean_is_sharpe=1.5, mean_oos_sharpe=0.8, efficiency=0.53,
                oos_win_folds=1, param_stability={'fast_ma': None},
            ),
        )

    monkeypatch.setattr('server.wfo_executor.run_walkforward', fake_run_walkforward)

    row = create_wfo_run(db_conn, _minimal_config_json(), 'swing_ma_boll',
                         '000001', '20200101', '20210101')
    execute_wfo_once(db_conn, row['id'], artifact_dir=artifact_dir)

    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'completed'
    assert fetched['artifact_path']
    assert os.path.exists(fetched['artifact_path'])
    with open(fetched['artifact_path'], encoding='utf-8') as f:
        artifact = json.load(f)
    assert artifact['result_type'] == 'wfo'
    assert len(artifact['folds']) == 1


def test_execute_wfo_once_marks_failed_on_exception(db_conn, artifact_dir, monkeypatch):
    """execute_wfo_once:引擎抛异常 → status=failed,error 字段记录。"""

    def boom(config, run, trading_calendar, on_fold_complete=None):
        raise RuntimeError('simulated')

    monkeypatch.setattr('server.wfo_executor.run_walkforward', boom)

    row = create_wfo_run(db_conn, _minimal_config_json(), 'swing_ma_boll',
                         '000001', '20200101', '20210101')
    execute_wfo_once(db_conn, row['id'], artifact_dir=artifact_dir)

    fetched = get_wfo_run(db_conn, row['id'])
    assert fetched['status'] == 'failed'
    assert 'simulated' in fetched['error']
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `python -m pytest tests/test_wfo_executor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.wfo_executor'`

- [ ] **Step 3: 创建 `server/wfo_executor.py`**

```python
# server/wfo_executor.py
"""WFO 后台执行器。照搬 server/executor.py 模式:线程 + artifact 落盘 + DB 状态。"""
import json
import os
import threading

from backtest.data_loader import default_trading_calendar
from backtest.service import run_backtest_service
from backtest.walkforward import WfoConfig, run_walkforward
from server.jobs import (
    create_wfo_run, get_wfo_run, mark_wfo_run_completed,
    update_wfo_run_progress, update_wfo_run_status,
)

DEFAULT_ARTIFACT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'results',
)


def execute_wfo_once(conn, wfo_id: int, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> None:
    row = get_wfo_run(conn, wfo_id)
    if row is None:
        return
    os.makedirs(artifact_dir, exist_ok=True)
    update_wfo_run_status(conn, wfo_id, 'running')
    config = WfoConfig(**json.loads(row['config_json']))

    def on_fold_complete(current: int, total: int) -> None:
        update_wfo_run_progress(conn, wfo_id, current, total)

    try:
        result = run_walkforward(
            config,
            run=run_backtest_service,
            trading_calendar=default_trading_calendar,
            on_fold_complete=on_fold_complete,
        )
        artifact_path = os.path.join(artifact_dir, f'wfo_{wfo_id}.json')
        with open(artifact_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        mark_wfo_run_completed(conn, wfo_id, artifact_path)
    except Exception as exc:
        update_wfo_run_status(conn, wfo_id, 'failed', str(exc))


def submit_wfo_background(
    conn, wfo_id: int, artifact_dir: str = DEFAULT_ARTIFACT_DIR,
) -> threading.Thread:
    thread = threading.Thread(
        target=execute_wfo_once,
        args=(conn, wfo_id, artifact_dir),
        daemon=True,
    )
    thread.start()
    return thread
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `python -m pytest tests/test_wfo_executor.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add server/wfo_executor.py tests/test_wfo_executor.py
git commit -m "feat(server): wfo_executor with thread + artifact pattern"
```

---

## Task 11: server/api.py 3 个端点

**Files:**
- Modify: `server/api.py`
- Create: `tests/test_server_wfo.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_server_wfo.py
"""WFO API 测试:POST/GET 3 个端点。"""
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from server.api import create_app
from server.db import init_db


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / 'test.sqlite')
    artifact_dir = tmp_path / 'artifacts'
    artifact_dir.mkdir()
    app = create_app(db_path=db_path)
    # patch DEFAULT_ARTIFACT_DIR via monkeypatching module attr
    import server.wfo_executor as exec_mod
    orig = exec_mod.DEFAULT_ARTIFACT_DIR
    exec_mod.DEFAULT_ARTIFACT_DIR = str(artifact_dir)
    yield TestClient(app)
    exec_mod.DEFAULT_ARTIFACT_DIR = orig


def _valid_config():
    return {
        'symbol': '000001', 'start': '20200101', 'end': '20210101',
        'cash': 100000.0, 'use_market_filter': False,
        'strategy_id': 'swing_ma_boll',
        'param_grid': {'fast_ma': [10.0, 20.0]},
        'train_days': 120, 'test_days': 60, 'step_days': 60,
    }


def test_post_wfo_rejects_grid_overflow(client, monkeypatch):
    """网格超 MAX_GRID_RUNS → 400, 不建表。"""
    # 简单构造超限:fast_ma 50 取值 × slow_ma 50 取值 = 2500 组合 × 1 fold
    payload = _valid_config()
    payload['param_grid'] = {
        'fast_ma': [float(i) for i in range(50)],
        'slow_ma': [float(i) for i in range(50)],
    }
    # monkeypatch trading_calendar 让 fold_count > 0
    import server.wfo_executor as exec_mod
    monkeypatch.setattr(exec_mod, 'default_trading_calendar',
                        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)])
    resp = client.post('/api/wfo', json=payload)
    assert resp.status_code == 400
    assert '网格过大' in resp.json()['detail']


def test_post_wfo_rejects_unknown_param(client, monkeypatch):
    """参数名不在策略声明 → 400。"""
    payload = _valid_config()
    payload['param_grid'] = {'nonexistent_param': [1.0, 2.0]}
    monkeypatch.setattr(
        'server.wfo_executor.default_trading_calendar',
        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)],
    )
    resp = client.post('/api/wfo', json=payload)
    assert resp.status_code == 400
    assert '未知参数' in resp.json()['detail']


def test_post_wfo_creates_run_and_submits_background(client, monkeypatch):
    """正常 POST → 200 + 返回 id/status/total_folds + 起后台线程。"""
    # 让 run_walkforward 直接返回一个空 fold 的结果,避免真跑回测
    from backtest.walkforward import WfoResult, WfoSummary, FoldResult
    monkeypatch.setattr(
        'server.wfo_executor.default_trading_calendar',
        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)],
    )
    monkeypatch.setattr(
        'server.wfo_executor.run_walkforward',
        lambda config, run, trading_calendar, on_fold_complete=None: WfoResult(
            config=config, folds=(),
            summary=WfoSummary(
                fold_count=0, failed_folds=0, mean_is_sharpe=0.0,
                mean_oos_sharpe=0.0, efficiency=None, oos_win_folds=0,
                param_stability={},
            ),
        ),
    )

    payload = _valid_config()
    resp = client.post('/api/wfo', json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 'id' in body
    assert body['status'] in ('queued', 'running', 'completed')
    assert 'total_folds' in body


def test_get_wfo_status_returns_progress(client, monkeypatch):
    """GET /api/wfo/{id} 返回状态行(含 current_fold/total_folds)。"""
    monkeypatch.setattr(
        'server.wfo_executor.default_trading_calendar',
        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)],
    )
    monkeypatch.setattr(
        'server.wfo_executor.run_walkforward',
        lambda config, run, trading_calendar, on_fold_complete=None: type('R', (), {
            'to_dict': lambda self: {'result_type': 'wfo', 'config': {}, 'folds': [], 'summary': {}},
        })(),
    )

    payload = _valid_config()
    post_resp = client.post('/api/wfo', json=payload)
    wfo_id = post_resp.json()['id']

    # 等待后台线程结束
    import time
    for _ in range(20):
        get_resp = client.get(f'/api/wfo/{wfo_id}')
        if get_resp.json()['status'] in ('completed', 'failed'):
            break
        time.sleep(0.05)

    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body['id'] == wfo_id
    assert 'current_fold' in body
    assert 'total_folds' in body


def test_get_wfo_result_returns_full_payload_with_result_type(client, monkeypatch):
    """GET /api/wfo/{id}/result 完成后返回完整 WfoResult 含 result_type='wfo'。"""
    monkeypatch.setattr(
        'server.wfo_executor.default_trading_calendar',
        lambda s, st, e: [f'20200{i:03d}' for i in range(1, 200)],
    )
    fake_payload = {
        'result_type': 'wfo',
        'config': _valid_config(),
        'folds': [],
        'summary': {
            'fold_count': 0, 'failed_folds': 0,
            'mean_is_sharpe': 0.0, 'mean_oos_sharpe': 0.0,
            'efficiency': None, 'oos_win_folds': 0,
            'param_stability': {},
        },
    }
    monkeypatch.setattr(
        'server.wfo_executor.run_walkforward',
        lambda config, run, trading_calendar, on_fold_complete=None: type('R', (), {
            'to_dict': lambda self: fake_payload,
        })(),
    )

    payload = _valid_config()
    post_resp = client.post('/api/wfo', json=payload)
    wfo_id = post_resp.json()['id']

    import time
    for _ in range(20):
        get_resp = client.get(f'/api/wfo/{wfo_id}/result')
        if get_resp.status_code == 200:
            break
        time.sleep(0.05)

    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body['result_type'] == 'wfo'
    assert 'folds' in body
    assert 'summary' in body
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `python -m pytest tests/test_server_wfo.py -v`
Expected: FAIL with 404 (路由不存在) 或 ImportError

- [ ] **Step 3: 在 `server/api.py` 的 `create_app` 内追加 3 个端点**

读 `server/api.py` 找到 `@app.delete('/api/jobs')` 这一行的位置,在它后面追加:

```python
    @app.post('/api/wfo')
    def create_wfo(payload: dict):
        from backtest.walkforward import WfoConfig
        from server.wfo_executor import submit_wfo_background
        from server.jobs import create_wfo_run

        try:
            config = WfoConfig(
                symbol=str(payload['symbol']).zfill(6),
                start=str(payload['start']),
                end=str(payload['end']),
                cash=float(payload.get('cash', 100000.0)),
                use_market_filter=bool(payload.get('use_market_filter', True)),
                strategy_id=str(payload.get('strategy_id', 'swing_ma_boll')),
                param_grid=dict(payload.get('param_grid', {})),
                train_days=int(payload.get('train_days', 504)),
                test_days=int(payload.get('test_days', 126)),
                step_days=int(payload.get('step_days', 126)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"配置无效: {exc}") from exc

        # 同步校验:调 default_trading_calendar 算 fold_count 并触发 run_walkforward 前置校验
        try:
            from backtest.walkforward import _compute_windows, _typed_param_grid, _cartesian, MAX_GRID_RUNS
            from backtest.data_loader import default_trading_calendar
            from strategies.registry import get_strategy_spec
            spec = get_strategy_spec(config.strategy_id)
            allowed = {p.name for p in spec.params if p.type in ('int', 'float')}
            for key in config.param_grid:
                if key not in allowed:
                    raise ValueError(
                        f"未知参数 {key},策略 {config.strategy_id} 支持的数值参数为 {sorted(allowed)}"
                    )
            calendar = default_trading_calendar(config.symbol, config.start, config.end)
            if not calendar:
                raise ValueError("区间内无可用交易日")
            windows = _compute_windows(calendar, config.train_days, config.test_days, config.step_days)
            typed_grid = _typed_param_grid(spec, config.param_grid)
            combos = _cartesian(typed_grid)
            total_runs = len(windows) * len(combos)
            if total_runs > MAX_GRID_RUNS:
                raise ValueError(
                    f"参数网格过大:{total_runs} 次样本内回测 > {MAX_GRID_RUNS} 上限。请缩小网格或缩短区间。"
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        config_json = json.dumps({
            'symbol': config.symbol, 'start': config.start, 'end': config.end,
            'cash': config.cash, 'use_market_filter': config.use_market_filter,
            'strategy_id': config.strategy_id,
            'param_grid': dict(config.param_grid),
            'train_days': config.train_days,
            'test_days': config.test_days,
            'step_days': config.step_days,
        })
        row = create_wfo_run(conn, config_json, config.strategy_id, config.symbol,
                              config.start, config.end)
        submit_wfo_background(conn, row['id'])
        return {
            'id': row['id'],
            'status': row['status'],
            'total_folds': len(windows),
            'symbol': config.symbol,
            'start_date': config.start,
            'end_date': config.end,
            'strategy_id': config.strategy_id,
            'current_fold': 0,
            'error': None,
        }

    @app.get('/api/wfo/{wfo_id}')
    def wfo_status(wfo_id: int):
        from server.jobs import get_wfo_run
        row = get_wfo_run(conn, wfo_id)
        if row is None:
            raise HTTPException(status_code=404, detail='wfo run not found')
        return {
            'id': row['id'],
            'status': row['status'],
            'symbol': row['symbol'],
            'start_date': row['start_date'],
            'end_date': row['end_date'],
            'strategy_id': row['strategy_id'],
            'current_fold': row['current_fold'],
            'total_folds': row['total_folds'],
            'error': row['error'],
        }

    @app.get('/api/wfo/{wfo_id}/result')
    def wfo_result(wfo_id: int):
        from server.jobs import get_wfo_run
        row = get_wfo_run(conn, wfo_id)
        if row is None or not row.get('artifact_path'):
            raise HTTPException(status_code=404, detail='result not found')
        with open(row['artifact_path'], encoding='utf-8') as f:
            return json.load(f)
```

并在 `create_app` 顶部加 `from fastapi import HTTPException` 确认(项目已 import)。若未 import,加在文件顶部。

- [ ] **Step 4: 跑测试,确认通过**

Run: `python -m pytest tests/test_server_wfo.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add server/api.py tests/test_server_wfo.py
git commit -m "feat(server): 3 WFO API endpoints with synchronous validation"
```

---

## Task 12: web/src/types.ts + WFO 配置表单

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 在 `web/src/types.ts` 末尾追加 WFO 类型**

读 `web/src/types.ts` 末尾(在 ComparisonResponse 之后),追加:

```typescript
export interface WfoConfig {
  symbol: string;
  start: string;
  end: string;
  cash: number;
  use_market_filter: boolean;
  strategy_id: string;
  param_grid: Record<string, number[]>;
  train_days: number;
  test_days: number;
  step_days: number;
}

export interface FoldResult {
  fold_index: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  best_params: Record<string, number>;
  is_sharpe: number;
  is_return_pct: number;
  oos_sharpe: number;
  oos_return_pct: number;
  oos_drawdown_pct: number;
  oos_trade_count: number;
  no_signal: boolean;
  failed: boolean;
}

export interface ParamStability {
  value: number;
  count: number;
  mean: number;
  std: number;
  occurrences: Record<string, number>;
}

export interface WfoSummary {
  fold_count: number;
  failed_folds: number;
  mean_is_sharpe: number;
  mean_oos_sharpe: number;
  efficiency: number | null;
  oos_win_folds: number;
  param_stability: Record<string, ParamStability>;
}

export interface WfoResult {
  result_type: 'wfo';
  config: WfoConfig;
  folds: FoldResult[];
  summary: WfoSummary;
}

export interface WfoRun {
  id: number;
  status: JobStatus;
  symbol: string;
  start_date: string;
  end_date: string;
  strategy_id: string;
  current_fold: number;
  total_folds: number;
  error: string | null;
}
```

- [ ] **Step 2: 编译验证类型**

Run: `cd web && npm run build`
Expected: 0 errors(类型正确)

- [ ] **Step 3: 在 `web/src/App.tsx` 加 WFO 配置表单**

读 `web/src/App.tsx` 找当前回测表单结束的位置(通常在 `</form>` 之后)。在表单闭合后插入 WFO 配置折叠区:

```tsx
// web/src/App.tsx 中,在主表单 </form> 之后插入:

<details className="wfo-config">
  <summary>{t('wfo.configTitle')}</summary>
  <WfoConfigForm
    baseSymbol={form.symbol}
    baseStart={form.start}
    baseEnd={form.end}
    baseStrategyId={form.strategy_id}
    strategyParams={currentStrategyParams}  // 从 /api/strategies 取出的 params
    onSubmitted={(run) => setActiveWfoRun(run)}
  />
</details>
```

并在 `App.tsx` 顶部 import:

```tsx
import { WfoConfigForm } from './WfoConfigForm';
import { WfoResultPage } from './WfoResultPage';
import type { WfoRun, WfoResult } from './types';
```

并在 App state 区添加:

```tsx
const [activeWfoRun, setActiveWfoRun] = useState<WfoRun | null>(null);
const [wfoResult, setWfoResult] = useState<WfoResult | null>(null);
```

在合适位置(主结果页旁边)渲染:

```tsx
{activeWfoRun && (
  <WfoResultPage
    run={activeWfoRun}
    onResult={(r) => setWfoResult(r)}
    result={wfoResult}
  />
)}
```

- [ ] **Step 4: 创建 `web/src/WfoConfigForm.tsx`**

```tsx
// web/src/WfoConfigForm.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { StrategyParamSpec, WfoRun } from './types';

interface Props {
  baseSymbol: string;
  baseStart: string;
  baseEnd: string;
  baseStrategyId: string;
  strategyParams: StrategyParamSpec[];
  onSubmitted: (run: WfoRun) => void;
}

interface ParamRange {
  name: string;
  min: number;
  max: number;
  step: number;
}

export function WfoConfigForm({
  baseSymbol, baseStart, baseEnd, baseStrategyId,
  strategyParams, onSubmitted,
}: Props) {
  const { t } = useTranslation();
  const numericParams = strategyParams.filter(p => p.type === 'int' || p.type === 'float');

  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [ranges, setRanges] = useState<Record<string, ParamRange>>({});
  const [trainDays, setTrainDays] = useState(504);
  const [testDays, setTestDays] = useState(126);
  const [stepDays, setStepDays] = useState(126);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    const paramGrid: Record<string, number[]> = {};
    for (const name of Object.keys(selected)) {
      if (!selected[name]) continue;
      const r = ranges[name];
      if (!r) continue;
      const vals: number[] = [];
      for (let v = r.min; v <= r.max + 1e-9; v += r.step) {
        vals.push(Number(v.toFixed(6)));
      }
      paramGrid[name] = vals;
    }
    setSubmitting(true);
    try {
      const resp = await fetch('/api/wfo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: baseSymbol, start: baseStart, end: baseEnd,
          cash: 100000, use_market_filter: true,
          strategy_id: baseStrategyId,
          param_grid: paramGrid,
          train_days: trainDays, test_days: testDays, step_days: stepDays,
        }),
      });
      if (!resp.ok) {
        const detail = (await resp.json()).detail;
        throw new Error(detail || `HTTP ${resp.status}`);
      }
      onSubmitted(await resp.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="wfo-form">
      <div>
        <label>{t('wfo.selectParams')}</label>
        {numericParams.map(p => (
          <div key={p.name}>
            <input
              type="checkbox"
              checked={!!selected[p.name]}
              onChange={(e) => setSelected({ ...selected, [p.name]: e.target.checked })}
            />
            <span>{p.label} ({p.name})</span>
            {selected[p.name] && (
              <span style={{ marginLeft: 12 }}>
                <input
                  type="number" placeholder={t('wfo.min')} value={ranges[p.name]?.min ?? ''}
                  onChange={(e) => setRanges({
                    ...ranges, [p.name]: { ...(ranges[p.name] || { min: 0, max: 0, step: 1 }), min: Number(e.target.value) },
                  })}
                />
                <input
                  type="number" placeholder={t('wfo.max')} value={ranges[p.name]?.max ?? ''}
                  onChange={(e) => setRanges({
                    ...ranges, [p.name]: { ...(ranges[p.name] || { min: 0, max: 0, step: 1 }), max: Number(e.target.value) },
                  })}
                />
                <input
                  type="number" placeholder={t('wfo.step')} value={ranges[p.name]?.step ?? ''}
                  onChange={(e) => setRanges({
                    ...ranges, [p.name]: { ...(ranges[p.name] || { min: 0, max: 0, step: 1 }), step: Number(e.target.value) },
                  })}
                />
              </span>
            )}
          </div>
        ))}
      </div>
      <div>
        <label>{t('wfo.trainDays')}</label>
        <input type="number" value={trainDays} onChange={(e) => setTrainDays(Number(e.target.value))} />
      </div>
      <div>
        <label>{t('wfo.testDays')}</label>
        <input type="number" value={testDays} onChange={(e) => setTestDays(Number(e.target.value))} />
      </div>
      <div>
        <label>{t('wfo.stepDays')}</label>
        <input type="number" value={stepDays} onChange={(e) => setStepDays(Number(e.target.value))} />
      </div>
      <button onClick={submit} disabled={submitting}>
        {submitting ? t('wfo.running') : t('wfo.submit')}
      </button>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
```

- [ ] **Step 5: 编译验证**

Run: `cd web && npm run build`
Expected: 0 errors

- [ ] **Step 6: 提交**

```bash
git add web/src/types.ts web/src/App.tsx web/src/WfoConfigForm.tsx
git commit -m "feat(web): WFO types and config form"
```

---

## Task 13: web WFO 结果页三块布局 + i18n

**Files:**
- Create: `web/src/WfoResultPage.tsx`
- Modify: `web/src/i18n/locales/zh.json`
- Modify: `web/src/i18n/locales/en.json`

- [ ] **Step 1: 创建 `web/src/WfoResultPage.tsx`**

```tsx
// web/src/WfoResultPage.tsx
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import type { WfoRun, WfoResult } from './types';

interface Props {
  run: WfoRun;
  result: WfoResult | null;
  onResult: (r: WfoResult) => void;
}

function efficiencyColor(eff: number | null): string {
  if (eff === null) return '#888';
  if (eff >= 0.6) return '#37a169';
  if (eff >= 0.3) return '#e0913a';
  return '#e05a4f';
}

export function WfoResultPage({ run, result, onResult }: Props) {
  const { t } = useTranslation();
  const [progressLabel, setProgressLabel] = useState('');

  // 轮询状态直到完成
  useEffect(() => {
    if (result) return;
    if (run.status === 'completed' || run.status === 'failed') return;
    const interval = setInterval(async () => {
      const r = await fetch(`/api/wfo/${run.id}`);
      if (r.ok) {
        const data = await r.json();
        setProgressLabel(t('wfo.progress', { current: data.current_fold, total: data.total_folds }));
        if (data.status === 'completed') {
          const rr = await fetch(`/api/wfo/${run.id}/result`);
          if (rr.ok) onResult(await rr.json());
          clearInterval(interval);
        }
        if (data.status === 'failed') clearInterval(interval);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [run.id, run.status, result, onResult, t]);

  if (run.status === 'failed') {
    return <div className="wfo-failed">WFO failed: {run.error}</div>;
  }
  if (!result) {
    return <div className="wfo-progress">{progressLabel || t('wfo.running')}</div>;
  }

  const { summary, folds } = result;
  const efficiency = summary.efficiency;
  const isNoValidFold = efficiency === null && summary.mean_is_sharpe === 0 && summary.fold_count > 0;

  const chartData = folds.map(f => ({
    name: `Fold ${f.fold_index + 1}`,
    is: f.failed || f.no_signal ? 0 : f.is_sharpe,
    oos: f.failed ? 0 : f.oos_sharpe,
  }));

  return (
    <div className="wfo-result">
      {/* 裁决卡 */}
      <div className="wfo-verdict">
        <div className="vcard">
          <div className="cap">{t('wfo.summary.isSharpe')}</div>
          <div className="big">{summary.mean_is_sharpe.toFixed(2)}</div>
        </div>
        <div className="vcard">
          <div className="cap">{t('wfo.summary.oosSharpe')}</div>
          <div className="big">{summary.mean_oos_sharpe.toFixed(2)}</div>
        </div>
        <div className="vcard" style={{ color: efficiencyColor(efficiency) }}>
          <div className="cap">{t('wfo.summary.efficiency')}</div>
          <div className="big">
            {isNoValidFold ? t('wfo.summary.noValidFold') :
             efficiency === null ? t('wfo.summary.efficiencyInvalid') :
             efficiency.toFixed(2)}
          </div>
        </div>
        <div className="vcard">
          <div className="cap">{t('wfo.summary.oosWins')}</div>
          <div className="big">{summary.oos_win_folds} / {summary.fold_count}</div>
        </div>
      </div>

      {/* 柱状图 */}
      <h3>{t('wfo.chartTitle')}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="is" fill="#4f6bed" name="IS" />
          <Bar dataKey="oos" fill="#e0913a" name="OOS" />
        </BarChart>
      </ResponsiveContainer>

      {/* 明细表 */}
      <h3>{t('wfo.tableTitle')}</h3>
      <table className="wfo-table">
        <thead>
          <tr>
            <th>Fold</th>
            <th>Train</th>
            <th>Test</th>
            <th>Best Params</th>
            <th>IS Sharpe</th>
            <th>OOS Sharpe</th>
            <th>OOS Return %</th>
            <th>OOS Trades</th>
          </tr>
        </thead>
        <tbody>
          {folds.map(f => (
            <tr key={f.fold_index} className={f.failed ? 'failed' : f.no_signal ? 'no-signal' : ''}>
              <td>{f.fold_index + 1}</td>
              <td>{f.train_start}~{f.train_end}</td>
              <td>{f.test_start}~{f.test_end}</td>
              <td>
                {f.failed ? <i>{t('wfo.foldFailed')}</i> :
                 f.no_signal ? <i>{t('wfo.foldNoSignal')}</i> :
                 Object.entries(f.best_params).map(([k, v]) => `${k}=${v}`).join(', ')}
              </td>
              <td>{f.is_sharpe.toFixed(2)}</td>
              <td>{f.oos_sharpe.toFixed(2)}</td>
              <td>{f.oos_return_pct.toFixed(2)}</td>
              <td>{f.oos_trade_count}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* 参数稳定性 */}
      <h3>{t('wfo.summary.paramStability')}</h3>
      <p className="hint">{t('wfo.stabilityHint')}</p>
      <table className="wfo-stability">
        <thead>
          <tr><th>Param</th><th>Mode</th><th>Count</th><th>Mean</th><th>Std</th></tr>
        </thead>
        <tbody>
          {Object.entries(summary.param_stability).map(([name, ps]) => (
            <tr key={name}>
              <td>{name}</td>
              <td>{ps.value}</td>
              <td>{ps.count}</td>
              <td>{ps.mean.toFixed(3)}</td>
              <td>{ps.std.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: 在 `web/src/i18n/locales/zh.json` 末尾追加 WFO keys**

读 `web/src/i18n/locales/zh.json` 末尾,追加:

```json
,
  "wfo": {
    "title": "Walk-Forward 验证",
    "configTitle": "WFO 配置",
    "selectParams": "选择要寻优的参数(2-3 个)",
    "min": "最小值",
    "max": "最大值",
    "step": "步长",
    "trainDays": "训练窗口(交易日)",
    "testDays": "验证窗口(交易日)",
    "stepDays": "滚动步长(交易日)",
    "submit": "开始 WFO 分析",
    "running": "分析中…",
    "progress": "窗口 {current}/{total}",
    "summary": {
      "isSharpe": "样本内 Sharpe(均)",
      "oosSharpe": "样本外 Sharpe(均)",
      "efficiency": "效率比 OOS/IS",
      "efficiencyInvalid": "样本内无效",
      "noValidFold": "无有效窗口",
      "oosWins": "样本外胜窗",
      "paramStability": "参数稳定性"
    },
    "stabilityHint": "众数(最高频取值)与离散度仅供参考,连续参数众数意义有限。",
    "foldNoSignal": "样本内无信号",
    "foldFailed": "失败",
    "chartTitle": "逐窗样本内 vs 样本外",
    "tableTitle": "逐窗明细"
  }
```

- [ ] **Step 3: 在 `web/src/i18n/locales/en.json` 末尾追加 WFO keys(英文版)**

```json
,
  "wfo": {
    "title": "Walk-Forward Validation",
    "configTitle": "WFO Configuration",
    "selectParams": "Select Parameters to Optimize (2-3)",
    "min": "Min",
    "max": "Max",
    "step": "Step",
    "trainDays": "Train Window (trading days)",
    "testDays": "Test Window (trading days)",
    "stepDays": "Step Size (trading days)",
    "submit": "Start WFO Analysis",
    "running": "Analyzing…",
    "progress": "Fold {current}/{total}",
    "summary": {
      "isSharpe": "IS Sharpe (avg)",
      "oosSharpe": "OOS Sharpe (avg)",
      "efficiency": "Efficiency OOS/IS",
      "efficiencyInvalid": "IS Invalid",
      "noValidFold": "No Valid Fold",
      "oosWins": "OOS Winning Folds",
      "paramStability": "Parameter Stability"
    },
    "stabilityHint": "Mode + dispersion; least informative for continuous params.",
    "foldNoSignal": "No IS signal",
    "foldFailed": "Failed",
    "chartTitle": "IS vs OOS by Fold",
    "tableTitle": "Fold Details"
  }
```

- [ ] **Step 4: 编译验证**

Run: `cd web && npm run build`
Expected: 0 errors

- [ ] **Step 5: 提交**

```bash
git add web/src/WfoResultPage.tsx web/src/i18n/locales/zh.json web/src/i18n/locales/en.json
git commit -m "feat(web): WFO result page (verdict + chart + table) + i18n"
```

---

## Task 14: 全量回归 + build

**Files:** (none)

- [ ] **Step 1: Python 全部测试**

Run: `python -m pytest -q tests/`
Expected: 所有已有测试 + 新增 19 (engine) + 1 (calendar) + 1 (db schema) + 5 (jobs helpers) + 2 (executor) + 5 (api) = 33 个新测试全绿,无回归

- [ ] **Step 2: 前端 build**

Run: `cd web && npm run build`
Expected: 0 errors

- [ ] **Step 3: 全量 CLI 回测 smoke(确认未破坏既有路径)**

Run: `python backtest/run_backtest.py --symbol 000001 --start 20210101 --end 20211231 --cash 100000`
Expected: 输出 Starting cash、Final value、Return %,无报错

- [ ] **Step 4: 整理 commit log(若 Step 1 暴露失败需修)**

若 Step 1-3 全部通过,WFO 功能开发完成。无需额外提交。

- [ ] **Step 5: (可选)创建 PR 描述**

若用户希望走 PR:

```bash
git log --oneline fb730c5..HEAD
```

汇总 13 个新 commit,每个 task 一个。推送到 origin 后开 PR。

---

## Self-Review

**1. Spec coverage:**
- ✅ 引擎纯逻辑(Task 1-6):覆盖 spec "引擎核心" 全部内容
- ✅ trading_calendar 注入(Task 7):覆盖 spec "交易日数据源" 决策
- ✅ wfo_runs 表 + 5 helper(Task 8-9):覆盖 spec "持久化"
- ✅ wfo_executor(Task 10):覆盖 spec "新增模块"
- ✅ 3 个端点(Task 11):覆盖 spec "API"
- ✅ 前端配置表单(Task 12):覆盖 spec "入口与导航"
- ✅ 结果页三块布局 + i18n(Task 13):覆盖 spec "三块布局实现" + "i18n"

**2. Placeholder scan:**
- ✅ 无 TBD/TODO/待定/未定义

**3. Type consistency:**
- `WfoConfig.param_grid` 在 Task 1 定义,Task 3 用 `_typed_param_grid` 转 typed,Task 4 用于构造 `BacktestRequest.strategy_params` —— 类型一致。
- `FoldResult.failed` 在 Task 1 定义,Task 4 构造时设置,Task 5 用于 `_build_summary` 过滤 —— 一致。
- `WfoSummary.efficiency` 在 Task 1 定义为 `float | None`,Task 5 实现 `None` 回退,Task 13 前端用 `efficiency === null` 判断 —— 一致。
- `WfoResult.result_type` 在 Task 1 定义为 `Literal['wfo']`,Task 5 `_build_summary` 不修改,Task 11 API 直接 dump `to_dict()`,Task 13 前端检查 `body.result_type === 'wfo'` —— 一致。
- `MAX_GRID_RUNS = 300` 在 Task 1 定义,Task 1 + Task 4 + Task 11 三处引用同一常量 —— 一致。