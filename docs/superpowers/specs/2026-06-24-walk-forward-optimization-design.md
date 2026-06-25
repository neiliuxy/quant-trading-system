# Walk-Forward Optimization — 设计文档

> 创建日期：2026-06-24
> 对应改进项：`docs/improvement-directions.md` 第 3 项「过拟合防护（walk-forward / 寻优）」

---

## 背景与目标

改进项 #1（交易成本）与 #2（风险指标 + 基准对比）已让单次回测结果可信。但当前系统仍是"在一段历史上跑一次，看收益率"——这是业界共识的**不可靠做法**。`citic_wave` / `b1_strategy` 各有 20+ 参数，却从未做过样本外验证、也无参数敏感性分析，**很可能已在历史上过拟合**。

本设计引入 **Walk-Forward Optimization（WFO）**：把历史切成多个滚动窗口，每段在样本内（in-sample）按 Sharpe 寻优参数，再到紧邻的样本外（out-of-sample）验证，回答"策略在近期还有效吗、最优参数稳定吗"两个最关键的问题。

**目标**：
1. 让用户对**单只股票**发起一次 WFO 分析。
2. 在前端分析台直接看到**裁决卡 + 逐窗对比柱状图 + 逐窗明细表**三块结果。
3. 通过真实的多窗口样本外表现，直观判断策略是否过拟合、参数是否稳健。

**非目标**：
- 不做一篮子股票的横截面分布（改进项 #4，留作后续叠加）。
- 不做多策略组合的 WFO（仅单策略）。
- 不引入无风险利率可配置化（沿用 #2 的 Sharpe 默认 `riskfreerate=0`）。
- 不抽取引擎内核做共享抽象（YAGNI，待性能真成瓶颈时再做）。
- 不修改任何已上线的单次回测代码（`run_backtest_service`、`BacktestResult` 等零改动）。

---

## 决策汇总（已与用户敲定）

| 维度 | 决策 |
|------|------|
| 验证范围 | 单只股票 |
| 参数搜索空间 | UI 选 2-3 个数值参数 + 各填 min/max/step |
| 窗口方案 | 滚动窗口（Rolling），按 train/test/step 长度指定；**test_start = train_end 后第一个交易日（紧密衔接，避免未来函数）** |
| 寻优目标 | Sharpe 比率（年化） |
| 执行方式 | 复用 `/api/jobs` 的后台线程 + artifact 模式 |
| 进度反馈 | 窗口级（current_fold / total_folds） |
| 引擎实现 | 纯编排层，循环调用 `run_backtest_service`，零内核修改 |
| 交易日数据源 | `trading_calendar: Callable[[str, str], list[str]]` 注入；默认实现走 DataHub；测试可注入 fake |
| 持久化 | 新建 `wfo_runs` 表 + artifact JSON（`data/results/wfo_{id}.json`） |
| 结果页布局 | 裁决卡 + 逐窗柱状图 + 逐窗明细表（三块都要） |
| 组合上限 | `MAX_GRID_RUNS = 300` 模块常量（初期限流，保护 UX；一行可调，非配置项） |
| 参数稳定性统计 | 众数 + 离散度（`value / count / mean / std / occurrences`），并附前端文案说明语义 |
| 参数名校验 | 引擎**显式校验** `param_grid` key 是否在 `StrategySpec.params` 中；未知参数名**同步拒绝 400**，不被 `BacktestRequest.normalized()` 静默过滤 |
| 参数值类型 | 引擎按 `StrategySpec.params` 的 `type` 字段（`int` / `float`）转换候选值，避免 backtrader 类型告警 |
| 效率比回退 | `mean_is_sharpe <= 0` 时 `efficiency = None`；裁决卡显示"样本内无效"而非色标 |
| 失败窗口聚合 | `FoldResult.failed=True` 的窗口不计入 `mean_* / oos_win_folds / param_stability`；计入 `summary.failed_folds` |

---

## 实机核查结论

WFO 引擎的所有输入与已有单次回测完全一致，确认可零修改复用：

| 现有能力 | 位置 | WFO 是否复用 |
|----------|------|--------------|
| `run_backtest_service(request) -> BacktestResult` | `backtest/service.py:191` | **是**，每窗 N×M 次 |
| `BacktestRequest.normalized()` | `backtest/service.py:39` | **是**，每个组合构造 |
| `BacktestResult.sharpe / annual_return_pct / excess_return_pct` | `backtest/service.py:65` | **是**，样本内选优 + OOS 记录 |
| A 股成本模块 | `backtest/costs.py` | **是**，自动继承 |
| DataHub 数据缓存（含日期索引） | `datahub/cache.py`、`backtest/data_loader.py` | **是**，作为 `trading_calendar` 的默认实现 |
| 异步任务 + artifact 模式 | `server/executor.py:11-34`、`server/jobs.py:39,109` | **是**，照搬模式新增 WFO 变体 |
| `current_code_version()` | `server/jobs.py:11` | **是**，复用构造 WFO `run_key` |

**关键边界确认**：
- `SharpeRatio` analyzer 在 `runonce=False, stdstats=False` 下工作正常（#2 已实测），零成交时返回 `None`。
- `BacktestRequest.normalized()` 对未知 strategy_id 抛 `ValueError`、对参数做静默过滤（WFO 不能依赖这个静默行为，必须显式校验）。
- `create_or_reuse_job` 用 `run_key = sha256(asdict(request) + market_config_hash + code_version)` 做去重；WFO 用新表 `wfo_runs`，**不会与单次回测撞 key**。

**关键缺陷纠正（基于用户核查）**：
- `backtest/data_loader.py:51` 的 `resolve_date_range` **只格式化起止字符串，不返回交易日列表或总数**，无法支撑 WFO 切窗。WFO 引擎不依赖它做切窗和计数，而是通过 `trading_calendar` 注入一个"返回 [start,end] 区间内按交易日排序的日期字符串列表"的 callable；默认实现走 DataHub 取 `stock_daily` 的日期索引。

---

## 架构

四层结构，WFO 作为独立编排层穿插其中：

```
┌─────────────────────────────────────────────────────────┐
│  前端 React (web/)                                       │
│    ├─ WFO 配置表单（参数勾选 + 范围 + 窗口长度）         │
│    └─ WFO 结果页（裁决卡 · 柱状图 · 明细表）             │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  后端 FastAPI (server/)                                  │
│    ├─ POST /api/wfo                                     │
│    ├─ GET  /api/wfo/{id}                                │
│    ├─ GET  /api/wfo/{id}/result                         │
│    └─ wfo executor（线程 + artifact，照搬 executor.py）  │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  WFO 引擎 (backtest/walkforward.py) — 纯编排             │
│    ├─ 切滚动窗口（基于 trading_calendar）                │
│    ├─ 生成参数网格（笛卡尔积）                          │
│    ├─ 每窗按 Sharpe 选最优                              │
│    ├─ OOS 用最优参数验证                                │
│    └─ 汇总 summary（排除失败窗）                        │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  核心回测 (backtest/service.py) — 零改动复用             │
│    ├─ run_backtest_service()  × 几百次                  │
│    ├─ A 股成本 · Sharpe · 基准 analyzer                 │
│    └─ DataHub 缓存（也是 trading_calendar 默认源）      │
└─────────────────────────────────────────────────────────┘
```

**边界守则**：WFO 引擎只通过 `BacktestRequest` / `BacktestResult` / `trading_calendar` 三个抽象与外部通信，**不依赖回测核心的内部实现，也不直接访问 DataHub**（caller 在 executor 层注入 trading_calendar 默认实现）。这保证引擎可脱离 Web / 脱离 backtrader / 脱离 DataHub 单独测试（注入 fake `run` 和 fake `trading_calendar` 即可）。

---

## 引擎核心：`backtest/walkforward.py`（新文件）

### 常量

```python
MAX_GRID_RUNS = 300
# 初期限流：5 折窗口 × 60 组合 = 300 次样本内回测，已接近个人机器分钟级上限；
# 超此值视为 UX 警告，提示缩小网格或缩短区间。常量一行可调，非配置项。
```

### 类型别名

```python
from typing import Any, Callable, Literal, Mapping

# 单次回测的抽象接口（生产 = run_backtest_service；测试 = fake）
RunFn = Callable[[BacktestRequest], BacktestResult]

# 交易日日历：(symbol, start, end) -> 该区间内按交易日排序的 YYYYMMDD 字符串列表
# 默认实现走 DataHub.get_dataset(stock_daily) 取日期索引；测试注入 fake
TradingCalendar = Callable[[str, str, str], list[str]]
# 参数顺序为 (symbol, start, end)，与 DataHub 取数对称

# 进度回调签名
OnFoldComplete = Callable[[int, int], None]
```

### 数据结构

```python
@dataclass(frozen=True)
class WfoConfig:
    symbol: str
    start: str                       # YYYYMMDD
    end: str                         # YYYYMMDD
    cash: float = 100000.0
    use_market_filter: bool = True
    strategy_id: str = 'swing_ma_boll'
    # 仅数值参数（int/float），2-3 个
    param_grid: Mapping[str, list[float]] = field(default_factory=dict)
    # 窗口长度（**交易日**，非自然日）
    train_days: int = 504            # 默认 2 年
    test_days: int = 126             # 默认 6 个月
    step_days: int = 126             # 默认 = test_days


@dataclass(frozen=True)
class FoldResult:
    fold_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    best_params: dict[str, Any]
    is_sharpe: float                 # 样本内最优组合的 Sharpe
    is_return_pct: float             # 样本内最优组合的总收益%
    oos_sharpe: float
    oos_return_pct: float
    oos_drawdown_pct: float
    oos_trade_count: int
    no_signal: bool = False          # True 表示样本内全部组合零成交（用默认参数跑 OOS）
    failed: bool = False             # True 表示某次回测异常（非业务错误），其他字段为默认值


@dataclass(frozen=True)
class ParamStability:
    """一个参数在所有 IS 有效窗口最优取值上的统计。"""
    value: float                     # 众数（出现次数最多的值）
    count: int                       # 众数的出现次数
    mean: float                      # 各窗最优取值的算术平均
    std: float                       # 各窗最优取值的标准差（0 表示全部相等）
    occurrences: dict[str, int]      # 该参数所有出现过的取值 → 次数；键为 str(value)（如 "1.5"）以保证 JSON 序列化合法


@dataclass(frozen=True)
class WfoSummary:
    fold_count: int                  # 总窗口数（含失败）
    failed_folds: int                # 失败窗口数（不计入下列均值 / 胜窗 / 稳定性）
    mean_is_sharpe: float            # 仅成功窗口的样本内 Sharpe 均值
    mean_oos_sharpe: float           # 非失败窗口（含 no_signal）的样本外 Sharpe 均值
    efficiency: float | None         # mean_oos_sharpe / mean_is_sharpe；mean_is_sharpe <= 0 时为 None
    oos_win_folds: int               # 非失败窗口中 oos_sharpe > 0 的个数（含 no_signal）
    param_stability: dict[str, ParamStability]  # 每个被寻优参数的稳定性


@dataclass(frozen=True)
class WfoResult:
    config: WfoConfig
    folds: tuple[FoldResult, ...]
    summary: WfoSummary
    result_type: Literal['wfo'] = 'wfo'   # 前端路由判断字段（避免与单次结果顶层字段冲突）

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
```

### 入口函数

```python
def run_walkforward(
    config: WfoConfig,
    run: RunFn = run_backtest_service,
    trading_calendar: TradingCalendar = _default_trading_calendar,
    on_fold_complete: OnFoldComplete | None = None,
) -> WfoResult:
    """执行 WFO 分析。纯编排，不依赖 backtrader/网络/Web/DataHub（caller 注入依赖）。

    抛 ValueError：
      - 网格超 MAX_GRID_RUNS 上限
      - 区间装不下 (train_days + test_days) 交易日
      - param_grid 的 key 不在 StrategySpec.params 中（显式校验，不依赖 normalized 静默过滤）
      - trading_calendar 返回空列表
    """
```

### 算法

1. **校验前置**：
   - 校验策略存在：`get_strategy_spec(config.strategy_id)`。
   - 校验 `param_grid` 的每个 key 必须在 `spec.params` 中，且 type 为 `'int'` 或 `'float'`。否则 `raise ValueError(f"未知参数 {key}，策略 {spec.id} 支持的参数为 {...}")`。
   - 校验 `param_grid` 中每个参数至少 2 个取值。
   - 校验 `train_days / test_days / step_days >= 1`。
   - 调用 `trading_calendar(symbol, start, end)` 取交易日列表 `T`；若为空 `raise ValueError("区间无可用交易日")`。
   - 若 `len(T) < train_days + test_days`，`raise ValueError(f"区间仅含 {len(T)} 个交易日，少于 train+test={train_days + test_days}")`。
   - 切窗后得 `windows` 列表；若 `fold_count * len(grid) > MAX_GRID_RUNS`，`raise ValueError(f"参数网格过大：{total} 次样本内回测 > {MAX_GRID_RUNS} 上限。请缩小网格或缩短区间。")`。

2. **切窗**（基于 `T`，**紧密衔接**避免未来函数）：
   ```
   windows = []
   i = 0
   while i + train_days + test_days <= len(T):
       ts, te = T[i], T[i + train_days - 1]
       vs, ve = T[i + train_days], T[i + train_days + test_days - 1]
       windows.append((ts, te, vs, ve))
       i += step_days
   ```
   注释：**`test_start = T[i + train_days]`，即 `train_end` 后的第一个交易日；窗口之间无 gap、无 overlap。**

3. **参数值类型转换**：根据 `spec.params` 中每个参数的 `type` 字段，把网格里的 float 值转 int 或保持 float。例：`{'atr_multiplier': [1.0, 1.5, 2.0]}` 且 type='float' → 保持 float；`{'atr_period': [10.0, 14.0, 20.0]}` 且 type='int' → `[10, 14, 20]`。

4. **每窗寻优 + OOS 验证**（伪代码）：
   ```
   base_params = spec.defaults         # 策略声明的默认参数；combo 只覆盖用户选中的 2-3 个寻优参数
   total_folds = len(windows)
   fold_results = []
   for fold_idx, (ts, te, vs, ve) in enumerate(windows):
       try:
           best_combo, best_sharpe = None, float('-inf')
           for combo in cartesian(param_grid_typed):
               req = BacktestRequest(
                   symbol, ts, te, cash, use_market_filter,
                   strategy_id, strategy_params={**base_params, **combo},
               )
               result = run(req)
               # Sharpe=None 按 -inf 处理
               sharpe = result.sharpe if result.sharpe is not None else float('-inf')
               if sharpe > best_sharpe:
                   best_combo, best_sharpe = combo, sharpe
           if best_sharpe == float('-inf'):
               # 全部组合零成交 → 该窗 no_signal=True，OOS 用默认参数
               fold_results.append(FoldResult(
                   fold_index=fold_idx, train_start=ts, train_end=te,
                   test_start=vs, test_end=ve,
                   best_params={}, is_sharpe=0.0, is_return_pct=0.0,
                   oos_sharpe=0.0, oos_return_pct=0.0,
                   oos_drawdown_pct=0.0, oos_trade_count=0,
                   no_signal=True,
               ))
           else:
               # OOS 用最优参数验证
               oos_req = BacktestRequest(... best_params ...)
               oos_result = run(oos_req)
               fold_results.append(FoldResult(
                   fold_index=fold_idx, ..., oos_sharpe=oos_result.sharpe or 0.0,
                   oos_return_pct=..., oos_drawdown_pct=..., oos_trade_count=...,
               ))
       except Exception:
           # 非业务错误（数据/网络/代码异常）→ 该窗标 failed，跳过 OOS
           fold_results.append(FoldResult(
               fold_index=fold_idx, train_start=ts, train_end=te,
               test_start=vs, test_end=ve,
               best_params={}, is_sharpe=0.0, is_return_pct=0.0,
               oos_sharpe=0.0, oos_return_pct=0.0,
               oos_drawdown_pct=0.0, oos_trade_count=0,
               failed=True,
           ))
       if on_fold_complete:
           on_fold_complete(fold_idx + 1, total_folds)
   ```

5. **汇总 summary**——按指标语义拆集合（`no_signal` 窗的 IS 无结果、OOS 用默认参数跑有结果，两套集合必须分开）：
   - `fold_count = len(fold_results)`
   - `failed_folds = sum(1 for f in fold_results if f.failed)`
   - `valid_is = [f for f in fold_results if not f.failed and not f.no_signal]` → 用于 `mean_is_sharpe`、`param_stability`（无 IS 优化结果的窗不参与 IS 指标聚合）
   - `valid_oos = [f for f in fold_results if not f.failed]` → 用于 `mean_oos_sharpe`、`oos_win_folds`（`no_signal` 窗的 OOS 是真实跑出的结果，应参与 OOS 指标聚合）
   - `mean_is_sharpe = mean(f.is_sharpe for f in valid_is)`（空集 → `0.0`）
   - `mean_oos_sharpe = mean(f.oos_sharpe for f in valid_oos)`（空集 → `0.0`）
   - `efficiency = (mean_oos_sharpe / mean_is_sharpe) if mean_is_sharpe > 0 else None`
   - `oos_win_folds = sum(1 for f in valid_oos if f.oos_sharpe > 0)`
   - `param_stability[name]`：取每个 `valid_is` 窗的 `best_params[name]`（集合已排除 `no_signal`，`best_params` 必非空）：
     - `mean = mean(values)`
     - `std = pstdev(values)`（样本数 < 2 → `0.0`）
     - `occurrences = {str(v): c for v, c in Counter(values).items()}`（key 转 str 以保证 JSON 序列化合法）
     - `value, count = max(occurrences.items(), key=lambda kv: kv[1])`（ties 取首次出现的）

### 边界处理

| 场景 | 处理 |
|------|------|
| 网格 > `MAX_GRID_RUNS` 上限 | **提交时同步拒绝** 400，附清晰中文错误（不在后台抛） |
| 区间不足 (train + test) 个交易日 | 同上，同步拒绝 |
| `param_grid` key 不在策略声明内 | 同上，同步拒绝（**不被 normalized 静默过滤**） |
| `trading_calendar` 返回空 | 同上，同步拒绝 |
| 某组合在 train 段零成交 → Sharpe=None | 排序按 `-inf` 处理；只要有别的有效组合就不被选中 |
| 全部组合零成交 | 该窗 `no_signal=True`，**OOS 用默认参数跑**（不放弃整窗），让用户在表格里看到"无样本内信号" |
| 某次回测异常（非业务错误） | 该窗 `failed=True`、`failed_folds += 1`、OOS 不跑；**不中断整体分析**，继续后续窗口 |
| `mean_is_sharpe <= 0` | `efficiency = None`；前端裁决卡显示"样本内无效"而非色标 |
| `valid_is` 为空（全失败/全 no_signal） | `mean_is_sharpe=0.0`、`efficiency=None`；`mean_oos_sharpe` 仍按 `valid_oos` 算（若有 `no_signal` 窗跑了 OOS，可能非零）；前端裁决卡显示"无有效窗口" |
| `valid_oos` 为空（全失败） | `mean_oos_sharpe=0.0`、`oos_win_folds=0`；前端裁决卡显示"无有效窗口" |

---

## 持久化与 API

### 新建表 `wfo_runs`（`server/db.py` 的 `init_db` 中追加）

```sql
CREATE TABLE IF NOT EXISTS wfo_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_key TEXT NOT NULL,
    status TEXT NOT NULL,                   -- queued/running/completed/failed
    symbol TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    config_json TEXT NOT NULL,              -- 完整 WfoConfig
    artifact_path TEXT,
    current_fold INTEGER DEFAULT 0,
    total_folds INTEGER DEFAULT 0,
    error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wfo_runs_run_key ON wfo_runs(run_key);
```

> **不复用 `jobs` 表**：jobs 表是单次回测的扁平结构，WFO 多了 `param_grid + train/test/step + 进度字段`，硬塞会破坏 jobs 表的简洁契约，也污染任务历史视图。新表更干净。

### 新增 API 端点（`server/api.py:create_app` 内）

| 方法 + 路径 | 行为 | 错误码 |
|------------|------|--------|
| `POST /api/wfo` | body = `WfoConfig`；**同步校验**（网格上限 / 区间不足 / 参数名非法 / 交易日为空） → 写表 → 起后台线程 → 返回 `{id, status, total_folds}` | 400（校验失败） |
| `GET /api/wfo/{id}` | 返回状态行（含 `current_fold / total_folds`），轮询用 | 404（不存在） |
| `GET /api/wfo/{id}/result` | 读 artifact JSON 返回完整 `WfoResult.to_dict()`（含 `result_type: 'wfo'`） | 404（未完成或不存在） |

### 新增模块 `server/wfo_executor.py`

照搬 `server/executor.py` 的成熟模式 + 调用 `backtest/data_loader.default_trading_calendar`：

```python
import json
import os
import threading

from backtest.data_loader import default_trading_calendar
from backtest.service import run_backtest_service
from backtest.walkforward import WfoConfig, run_walkforward
from server.jobs import (
    get_wfo_run, update_wfo_run_status, update_wfo_run_progress,
    mark_wfo_run_completed,
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


def submit_wfo_background(conn, wfo_id: int, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> threading.Thread:
    thread = threading.Thread(
        target=execute_wfo_once,
        args=(conn, wfo_id, artifact_dir),
        daemon=True,
    )
    thread.start()
    return thread
```

### 新增 `backtest/data_loader.default_trading_calendar`（公开函数）

交易日历本质是数据加载层职责，从 executor 上移到 `data_loader.py`，避免 server 层直接依赖 backtest 的私有工厂函数：

```python
# backtest/data_loader.py 追加
from datahub.models import DatasetRequest
from datahub.service import DataHub
from server.db import init_db, DEFAULT_DB_PATH


def default_trading_calendar(symbol: str, start: str, end: str) -> list[str]:
    """WFO 引擎 trading_calendar 的默认实现：走 DataHub 取 stock_daily 日期索引。

    返回 [start, end] 区间内按交易日排序的 YYYYMMDD 字符串列表；数据为空返回空列表。
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hub = DataHub(root_dir=project_root, conn=init_db(DEFAULT_DB_PATH))
    df = hub.get_dataset(DatasetRequest(
        dataset_type='stock_daily', symbol=symbol, start=start, end=end,
    )).frame
    if df is None or df.empty:
        return []
    return sorted(df['date'].dt.strftime('%Y%m%d').tolist())
```

`server/jobs.py` 同步新增 `get_wfo_run / update_wfo_run_status / update_wfo_run_progress / mark_wfo_run_completed / create_wfo_run` 五个 helper（结构照搬现有 jobs 表的同名函数）。

### 序列化与缓存

- `WfoResult.to_dict()` → executor 写入 artifact → API `/result` 读盘返回。
- `result_type: 'wfo'` 字段让前端能稳健判断路由（不依赖 `folds` 字段存在性）。
- **run_key**：与 `server/jobs.py:run_key_for_request` 风格保持一致：
  ```python
  import hashlib, json
  from dataclasses import asdict
  from server.jobs import current_code_version

  payload = {
      'config': asdict(config),
      'code_version': current_code_version(),
  }
  encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
  run_key = hashlib.sha256(encoded.encode()).hexdigest()
  ```
  配置完全一致且代码版本一致时复用上次结果。
- 缓存失效：`code_version` 含 git short hash，与现有机制一致。

### POST 同步校验耗时说明

`POST /api/wfo` 在写入 `wfo_runs` 表前会同步调用 `default_trading_calendar` 以计算 `total_folds` 并校验网格上限。该调用对应该股票**首次**加载时需从 AkShare 拉取并写缓存，可能等待 1-2 秒；之后命中 DataHub 缓存，毫秒级返回。前端实现时若看到 ~1s 的请求延迟属正常，不应误判为接口卡死。若未来需避免阻塞，可将该校验挪到后台线程 + 改用 POST + GET 两阶段提交（YAGNI，本期不做）。

---

## 前端 `web/`

### `web/src/types.ts`

新增：
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
  train_start: string; train_end: string;
  test_start: string; test_end: string;
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
  value: number;        // 众数
  count: number;        // 众数次数
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
  created_at: string;
  updated_at: string;
}
```

### 入口与导航

- 在回测表单下方加 "Walk-Forward 验证" 折叠区，复用表单的 symbol/start/end/strategy_id，点击「开始 WFO 分析」提交。
- 结果页路由判断：`result.result_type === 'wfo'` 走 WFO 三块布局；`'single'`（或缺失）走原有单次结果页。

### 三块布局实现

按已与用户确认的 mockup 实现：

1. **裁决卡**：4 张卡片（IS 均值 / OOS 均值 / efficiency / OOS 胜窗数）。
   - `efficiency === null` → 卡片显示"样本内无效"（无色标）。
   - `efficiency === null && mean_is_sharpe === 0 && fold_count > 0` → 显示"无有效窗口"（等价于 valid_is 为空：`valid_is` 不直接暴露给前端，故用其派生结果反推）。
   - 否则：≥ 0.6 绿色，0.3-0.6 黄色，<0.3 红色。
2. **逐窗柱状图**：Recharts `BarChart`，双柱（IS Sharpe + OOS Sharpe）按 fold 排列。`failed` 窗标灰、`no_signal` 窗标浅色。tooltip 显示完整 FoldResult。
3. **逐窗明细表**：列出 train/test 区间、最优参数 chip、两段 Sharpe/收益/OOS 回撤与交易数；failed/no_signal 行用差异化样式。

### i18n

新增 key（`web/src/i18n/locales/{zh,en}.json`）：

| key | zh | en |
|-----|-----|-----|
| `wfo.title` | Walk-Forward 验证 | Walk-Forward Validation |
| `wfo.configTitle` | WFO 配置 | WFO Configuration |
| `wfo.selectParams` | 选择要寻优的参数（2-3 个） | Select Parameters to Optimize (2-3) |
| `wfo.min` | 最小值 | Min |
| `wfo.max` | 最大值 | Max |
| `wfo.step` | 步长 | Step |
| `wfo.trainDays` | 训练窗口（交易日） | Train Window (trading days) |
| `wfo.testDays` | 验证窗口（交易日） | Test Window (trading days) |
| `wfo.stepDays` | 滚动步长（交易日） | Step Size (trading days) |
| `wfo.submit` | 开始 WFO 分析 | Start WFO Analysis |
| `wfo.running` | 分析中… | Analyzing… |
| `wfo.progress` | 窗口 {current}/{total} | Fold {current}/{total} |
| `wfo.summary.isSharpe` | 样本内 Sharpe（均） | IS Sharpe (avg) |
| `wfo.summary.oosSharpe` | 样本外 Sharpe（均） | OOS Sharpe (avg) |
| `wfo.summary.efficiency` | 效率比 OOS/IS | Efficiency OOS/IS |
| `wfo.summary.efficiencyInvalid` | 样本内无效 | IS Invalid |
| `wfo.summary.noValidFold` | 无有效窗口 | No Valid Fold |
| `wfo.summary.oosWins` | 样本外胜窗 | OOS Winning Folds |
| `wfo.summary.paramStability` | 参数稳定性 | Parameter Stability |
| `wfo.stabilityHint` | 众数（最高频取值）与离散度仅供参考，连续参数众数意义有限。 | Mode + dispersion; least informative for continuous params. |
| `wfo.foldNoSignal` | 样本内无信号 | No IS signal |
| `wfo.foldFailed` | 失败 | Failed |
| `wfo.chartTitle` | 逐窗样本内 vs 样本外 | IS vs OOS by Fold |
| `wfo.tableTitle` | 逐窗明细 | Fold Details |

---

## 测试

### `tests/test_walkforward.py`（新建，引擎纯逻辑，不依赖 backtrader/网络/DataHub）

注入 fake `run` + fake `trading_calendar`，测：

1. **切窗正确性**：固定 train/test/step + 注入交易日日历，断言窗口数量、起止日期（**紧密衔接验证**）。
2. **参数网格笛卡尔积**：2 参数 × 3 取值 = 9 组合，全部被调。
3. **每窗选最优**：fake 返回递增 Sharpe，断言选最大。
4. **OOS 用最优参数**：断言 OOS 调用的 `request.strategy_params` 是该窗的 `best_params`。
5. **summary 计算**：efficiency / oos_win_folds / param_stability（含 mean/std）正确。
6. **网格 > MAX_GRID_RUNS 拒绝**：抛 `ValueError`，不调 `run`。
7. **区间不足拒绝**：交易日总数 < train + test 时抛 `ValueError`。
8. **零成交 Sharpe=None**：按 -inf 处理，不被选；全零成交 → fold.no_signal=True。
9. **某次回测异常 → fold.failed=True**：summary.failed_folds += 1；该窗不进 `valid_is` / `valid_oos`，因此不计入 mean/胜窗/param_stability。
9a. **`no_signal` 拆集合语义**：构造混合场景（含一个正常窗 + 一个 `no_signal` 窗 + 一个 `failed` 窗），断言：
   - `mean_is_sharpe` 只算正常窗（`no_signal` 不进）
   - `mean_oos_sharpe` 包含正常窗 + `no_signal` 窗
   - `oos_win_folds` 同上
   - `param_stability` 只取正常窗的 `best_params`
9b. **`occurrences` 序列化合法**：构造一个 `boll_devfactor` 网格（float 值），断言 `summary.param_stability[name].occurrences` 的键全部为字符串（如 `"1.5"`），可被 `json.dumps` 不抛异常。
10. **进度回调**：`on_fold_complete(current, total)` 传入预计算的 `total_folds`（**不是已完成数**）。
11. **`to_dict()` 结构稳定**：含 `result_type: 'wfo'`、可序列化、字段齐全。
12. **效率比回退**：`mean_is_sharpe <= 0` → `efficiency=None`。
13. **参数名校验**：`param_grid` key 不在策略声明 → 抛 `ValueError`，**不调用 normalized 静默过滤**。
14. **参数值类型转换**：int 类型参数候选值 float → 转 int。
15. **trading_calendar 返回空**：抛 `ValueError`。

### `tests/test_server_wfo.py`（新建 API 测试，照 `tests/test_server_executor.py` 模式）

16. POST 网格超限 → 400，不建表。
17. POST 区间不足 → 400。
18. POST 参数名非法 → 400（不被静默过滤）。
19. POST 正常 → 建表 + 返回 `{id, status, total_folds}`，后台线程跑。
20. GET /api/wfo/{id} 返回状态行（含 progress）。
21. GET /api/wfo/{id}/result 完成后返回 `result_type === 'wfo'`。

### `tests/test_db.py`（扩展，新表 schema）

22. `init_db` 创建 `wfo_runs` 表，含所有字段与索引。

### 回归

- `python -m pytest -q tests/` 全绿。
- 前端 `npm run build` 通过。

---

## 落地步骤

1. **引擎与单元测试**：`backtest/walkforward.py` + `tests/test_walkforward.py`（TDD，先写测试再实现）。15 个纯逻辑测试全绿。
2. **持久化**：`server/db.py` 新表 + `tests/test_db.py` 扩展。schema 测试通过。
3. **jobs helper + executor**：`server/jobs.py` 加 5 个 wfo helper、`server/wfo_executor.py` 新建、`tests/test_server_wfo.py` API 测试。6 个 API 测试全绿。
4. **后端端点**：`server/api.py` 加 3 个路由 + `JobCreateRequest`/`WfoRun` 的 Pydantic 模型（如需）。端到端验证。
5. **前端类型**：`web/src/types.ts` 加 6 个接口（含 `result_type`）。
6. **前端 UI**：配置表单 + 结果页三块布局 + 21 个 i18n key + 失败/无信号样式。`npm run build` 通过。
7. **全量回归**：`python -m pytest -q tests/` 无回归。