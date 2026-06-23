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
| 窗口方案 | 滚动窗口（Rolling），按 train/test/step 长度指定 |
| 寻优目标 | Sharpe 比率（年化） |
| 执行方式 | 复用 `/api/jobs` 的后台线程 + artifact 模式 |
| 进度反馈 | 窗口级（current_fold / total_folds） |
| 引擎实现 | 纯编排层，循环调用 `run_backtest_service`，零内核修改 |
| 持久化 | 新建 `wfo_runs` 表 + artifact JSON（`data/results/wfo_{id}.json`） |
| 结果页布局 | 裁决卡 + 逐窗柱状图 + 逐窗明细表（三块都要） |
| 组合上限 | 300 次样本内回测（超限同步拒绝 400） |

---

## 实机核查结论

WFO 引擎的所有输入与已有单次回测完全一致，确认可零修改复用：

| 现有能力 | 位置 | WFO 是否复用 |
|----------|------|--------------|
| `run_backtest_service(request) -> BacktestResult` | `backtest/service.py:191` | **是**，每窗 N×M 次 |
| `BacktestRequest.normalized()` | `backtest/service.py:39` | **是**，每个组合构造 |
| `BacktestResult.sharpe` / `annual_return_pct` / `excess_return_pct` | `backtest/service.py:65` | **是**，样本内选优 + OOS 记录 |
| A 股成本模块 | `backtest/costs.py` | **是**，自动继承 |
| DataHub 数据缓存 | `datahub/cache.py` | **是**，同一股票同区间仅首次落盘 |
| 异步任务 + artifact 模式 | `server/executor.py:11-34`、`server/jobs.py:39,109` | **是**，照搬模式新增 WFO 变体 |

**关键边界确认**：
- `SharpeRatio` analyzer 在 `runonce=False, stdstats=False` 下工作正常（#2 已实测），零成交时返回 `None`。
- `BacktestRequest.normalized()` 对未知 strategy_id 抛 `ValueError`、对参数做静默过滤（与 strategy 声明对齐）。
- `create_or_reuse_job` 用 `run_key = sha256(asdict(request) + market_config_hash + code_version)` 做去重，WFO 配置差异全在 `config_json`，**不会与单次回测撞 key**（不同表）。

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
│    ├─ 切滚动窗口                                        │
│    ├─ 生成参数网格（笛卡尔积）                          │
│    ├─ 每窗按 Sharpe 选最优                              │
│    ├─ OOS 用最优参数验证                                │
│    └─ 汇总 summary                                      │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  核心回测 (backtest/service.py) — 零改动复用             │
│    ├─ run_backtest_service()  × 几百次                  │
│    ├─ A 股成本 · Sharpe · 基准 analyzer                 │
│    └─ DataHub 缓存                                      │
└─────────────────────────────────────────────────────────┘
```

**边界守则**：WFO 引擎只通过 `BacktestRequest` / `BacktestResult` 这个已有接口与回测核心通信，**不依赖其内部实现**。这保证引擎可脱离 Web / 脱离 backtrader 单独测试（注入 fake run 函数即可）。

---

## 引擎核心：`backtest/walkforward.py`（新文件）

### 数据结构

```python
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


# 输入：单次 WFO 分析的完整配置
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
    # 窗口长度（交易日）
    train_days: int = 504            # 默认 2 年
    test_days: int = 126             # 默认 6 个月
    step_days: int = 126             # 默认 = test_days


# 输出：单个窗口的明细
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


# 输出：汇总（裁决卡数据）
@dataclass(frozen=True)
class WfoSummary:
    fold_count: int
    mean_is_sharpe: float
    mean_oos_sharpe: float
    efficiency: float                # mean_oos_sharpe / mean_is_sharpe
    oos_win_folds: int               # oos_sharpe > 0 的窗口数
    param_stability: dict[str, Any]  # 最优参数在各窗的取值分布


# 输出：完整 WFO 结果
@dataclass(frozen=True)
class WfoResult:
    config: WfoConfig
    folds: tuple[FoldResult, ...]
    summary: WfoSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            'config': asdict(self.config),
            'folds': [asdict(f) for f in self.folds],
            'summary': asdict(self.summary),
        }


# 进度回调签名
OnFoldComplete = Callable[[int, int], None]
# 单次回测的抽象接口（生产 = run_backtest_service；测试 = fake）
RunFn = Callable[[BacktestRequest], BacktestResult]
```

### 入口函数

```python
def run_walkforward(
    config: WfoConfig,
    run: RunFn = run_backtest_service,
    on_fold_complete: OnFoldComplete | None = None,
) -> WfoResult:
    """执行 WFO 分析。纯编排，不依赖 backtrader/网络/Web。

    抛 ValueError：
      - 网格超 300 次样本内回测上限
      - 区间装不下 (train + test) 窗口
      - 参数名不在策略声明内（构造 BacktestRequest 时会被 normalized 过滤，
        但这里先期校验可给出更清晰错误）
    """
```

### 算法

1. **校验前置**：
   - `total_grid = len(param_grid_笛卡尔积)`；`total_runs = fold_count × total_grid`。
   - 若 `total_runs > 300`，抛 `ValueError(f"参数网格过大：{total_runs} 次样本内回测 > 300 上限。请缩小网格或缩短区间。")`。
   - 用 `resolve_date_range(start, end)` 取交易日总数；若 < `train_days + test_days`，抛 `ValueError(...)`。

2. **切窗**：从 `start` 起，按 `step_days` 滑动；每窗取 `train_days` 训练 + `test_days` 验证，直到 `test_end > end` 止。返回 `[(train_start, train_end, test_start, test_end), ...]`。

3. **每窗寻优**（伪代码）：
   ```
   for fold_idx, (ts, te, vs, ve) in enumerate(folds):
       best_combo, best_sharpe = None, -inf
       for combo in cartesian(param_grid):
           req = BacktestRequest(symbol, ts, te, cash, use_market_filter,
                                  strategy_id, strategy_params={**base_params, **combo})
           result = run(req)
           if result.sharpe > best_sharpe:
               best_combo, best_sharpe = combo, result.sharpe
       # 用最优组合在 OOS 段验证
       oos_req = same_req_with_dates(vs, ve)
       oos_result = run(oos_req)
       folds.append(FoldResult(...))
       if on_fold_complete:
           on_fold_complete(fold_idx + 1, len(folds))
   ```

4. **汇总**：算 `mean_is_sharpe / mean_oos_sharpe / efficiency / oos_win_folds / param_stability`（统计每个参数名在各窗最优取值中出现次数最多的值）。

### 边界处理

| 场景 | 处理 |
|------|------|
| 网格 > 300 上限 | **提交时同步拒绝** 400，附清晰中文错误（不在后台抛） |
| 区间不足 (train + test) | 同上，提交时同步拒绝 |
| 某组合在 train 段零成交 → Sharpe=None | 排序按 `-inf` 处理；只要有别的有效组合就不被选中 |
| 全部组合零成交 | 该窗 `best_sharpe = 0.0`、记录 `best_params={}`、OOS 用默认参数跑 |
| 某次回测异常（非业务错误） | 该窗标 `failed`、跳过 OOS、记入 summary 失败计数；不中断整体分析 |
| `param_stability` 多值并列最高 | 取首个出现，附带 ties 计数 |

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
    config_json TEXT NOT NULL,              -- 完整 WfoConfig（不含 cash/market_filter 外显冗余）
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
| `POST /api/wfo` | body = `WfoConfig`；同步校验（网格上限 / 区间不足 / 参数非法） → 写表 → 起后台线程 → 返回 `{id, status, total_folds}` | 400（校验失败） |
| `GET /api/wfo/{id}` | 返回状态行（含 `current_fold / total_folds`），轮询用 | 404（不存在） |
| `GET /api/wfo/{id}/result` | 读 artifact JSON 返回完整 `WfoResult.to_dict()` | 404（未完成或不存在） |

### 新增模块 `server/wfo_executor.py`

照搬 `server/executor.py` 的成熟模式：

```python
import json
import os
import threading

from backtest.service import BacktestResult
from backtest.walkforward import WfoConfig, run_walkforward
from server.jobs import get_wfo_run, update_wfo_run_status, mark_wfo_run_completed

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
        result = run_walkforward(config, on_fold_complete=on_fold_complete)
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

`server/jobs.py` 同步新增 `get_wfo_run / update_wfo_run_status / update_wfo_run_progress / mark_wfo_run_completed / create_wfo_run` 五个 helper（结构照搬现有 jobs 表的同名函数）。

### 序列化与缓存

- `WfoResult.to_dict()` → executor 写入 artifact → API `/result` 读盘返回。
- **run_key**：`sha256(json.dumps(asdict(WfoConfig), sort_keys=True) + code_version)`。配置完全一致时复用上次结果（含进度字段的"完成态"）。
- 缓存失效：`code_version` 含 git short hash，与现有机制一致。

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
}

export interface WfoSummary {
  fold_count: number;
  mean_is_sharpe: number;
  mean_oos_sharpe: number;
  efficiency: number;
  oos_win_folds: number;
  param_stability: Record<string, { value: number; count: number }>;
}

export interface WfoResult {
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
- 新增结果路由（或复用同一结果页，通过 result 形状判断）：`folds` 字段存在则走 WFO 三块布局。

### 三块布局实现

按已与用户确认的 mockup 实现：

1. **裁决卡**：4 张卡片（IS 均值 / OOS 均值 / efficiency / OOS 胜窗数）。efficiency ≥ 0.6 绿色，0.3-0.6 黄色，<0.3 红色。
2. **逐窗柱状图**：Recharts `BarChart`，双柱（IS Sharpe + OOS Sharpe）按 fold 排列。tooltip 显示完整 FoldResult。
3. **逐窗明细表**：列出 train/test 区间、最优参数 chip、两段 Sharpe/收益/OOS 回撤与交易数。

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
| `wfo.summary.oosWins` | 样本外胜窗 | OOS Winning Folds |
| `wfo.summary.paramStability` | 参数稳定性 | Parameter Stability |
| `wfo.chartTitle` | 逐窗样本内 vs 样本外 | IS vs OOS by Fold |
| `wfo.tableTitle` | 逐窗明细 | Fold Details |

---

## 测试

### `tests/test_walkforward.py`（新建，引擎纯逻辑，不依赖 backtrader/网络）

注入 fake `run` 函数（返回预设 `BacktestResult`）测：

1. **切窗正确性**：固定 train/test/step，断言窗口数量、起止日期。
2. **参数网格笛卡尔积**：2 参数 × 3 取值 = 9 组合，全部被调。
3. **每窗选最优**：fake 返回递增 Sharpe，断言选最大。
4. **OOS 用最优参数**：断言 OOS 调用的 `request.strategy_params` 是该窗的 `best_params`。
5. **summary 计算**：efficiency / oos_win_folds / param_stability 正确。
6. **网格 > 300 拒绝**：抛 `ValueError`，不调 `run`。
7. **区间不足拒绝**：抛 `ValueError`。
8. **零成交 Sharpe=None**：按 -inf 处理，不被选。
9. **进度回调**：`on_fold_complete(1, total)` 在每窗结束后被调用。
10. **`to_dict()` 结构稳定**：可序列化、字段齐全。

### `tests/test_server_wfo.py`（新建 API 测试，照 `tests/test_server_executor.py` 模式）

11. POST 网格超限 → 400，不建表。
12. POST 区间不足 → 400。
13. POST 正常 → 建表 + 返回 `{id, status, total_folds}`，后台线程跑。
14. GET /api/wfo/{id} 返回状态行。
15. GET /api/wfo/{id}/result 完成后返回完整 `WfoResult.to_dict()`。

### `tests/test_db.py`（扩展，新表 schema）

16. `init_db` 创建 `wfo_runs` 表，含所有字段与索引。

### 回归

- `python -m pytest -q tests/` 全绿。
- 前端 `npm run build` 通过。

---

## 落地步骤

1. **引擎与单元测试**：`backtest/walkforward.py` + `tests/test_walkforward.py`（TDD，先写测试再实现）。10 个纯逻辑测试全绿。
2. **持久化**：`server/db.py` 新表 + `tests/test_db.py` 扩展。schema 测试通过。
3. **jobs helper + executor**：`server/jobs.py` 加 5 个 wfo helper、`server/wfo_executor.py` 新建、`tests/test_server_wfo.py` API 测试。API 测试全绿。
4. **后端端点**：`server/api.py` 加 3 个路由 + `JobCreateRequest`/`WfoRun` 的 Pydantic 模型（如需）。端到端验证。
5. **前端类型**：`web/src/types.ts` 加 5 个接口。
6. **前端 UI**：配置表单 + 结果页三块布局 + i18n。`npm run build` 通过。
7. **全量回归**：`python -m pytest -q tests/` 无回归。