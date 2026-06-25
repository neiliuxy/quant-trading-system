"""WFO 引擎。纯编排,不依赖 backtrader/网络/Web/DataHub。

通过注入 run(单次回测接口)和 trading_calendar(交易日历)实现可测性。
"""
from collections import Counter as _Counter
from dataclasses import asdict, dataclass, field
from itertools import product as _iter_product
from statistics import mean as _mean, pstdev as _pstdev
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


# ---------- 参数网格 ----------

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


# ---------- 切窗 ----------

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


# ---------- 汇总 ----------

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
            mode_value, mode_count = max(occurrences.items(), key=lambda kv: kv[1])
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


# ---------- 入口 ----------

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
