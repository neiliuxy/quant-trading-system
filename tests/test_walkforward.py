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
from strategies.registry import get_strategy_spec
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
    with pytest.raises(ValueError, match='少于 train\\+test'):
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
    from backtest.walkforward import WfoSummary
    cfg = _basic_config()
    res = WfoResult(
        config=cfg,
        folds=(),
        summary=WfoSummary(
            fold_count=0, failed_folds=0,
            mean_is_sharpe=0.0, mean_oos_sharpe=0.0,
            efficiency=None, oos_win_folds=0,
            param_stability={},
        ),
    )
    d = res.to_dict()
    assert d['result_type'] == 'wfo'
    # 关键字段都在
    assert d['config']['symbol'] == '000001'
    # 必须能被 json.dumps
    json.dumps(d, default=str)


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
    assert windows[0] == ('20200101', '20200105', '20200106', '20200108')
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


# ---------- 每窗寻优 + OOS ----------

def _varying_sharpe_run(target_by_combo: dict[tuple, float]):
    """fake run:根据 (sort_key of combo) 返回不同 sharpe 用于验证选优逻辑。

    target_by_combo 的 key 只包含被寻优的参数;引擎会混入 base_params,
    这里自动从 target keys 推断被寻优的参数名,忽略 base_params。
    """
    varied_names = set()
    for key in target_by_combo:
        varied_names.update(name for name, _ in key)

    def run(req: BacktestRequest) -> BacktestResult:
        combo_key = tuple(sorted(
            (name, req.strategy_params[name])
            for name in varied_names if name in req.strategy_params
        ))
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
    calls = []

    def tracking_run(req: BacktestRequest) -> BacktestResult:
        calls.append(req)
        combo_key = (('fast_ma', req.strategy_params['fast_ma']),)
        sharpe = {(('fast_ma', 10),): 0.5, (('fast_ma', 20),): 2.0}.get(combo_key, 0.5)
        return BacktestResult(
            symbol=req.symbol, start=req.start, end=req.end,
            initial_cash=req.cash, final_value=req.cash * (1 + sharpe / 100),
            total_return_pct=sharpe, max_drawdown_pct=1.0,
            trade_count=1, win_rate_pct=100.0, sharpe=sharpe,
        )

    result = run_walkforward(cfg, run=tracking_run, trading_calendar=lambda s, st, e: calendar)
    # 按 fold 的 test 窗口找到 OOS 调用
    for fold in result.folds:
        oos_reqs = [
            r for r in calls
            if r.start == fold.test_start and r.end == fold.test_end
        ]
        assert oos_reqs, f'fold {fold.fold_index} 找不到 OOS 调用'
        assert oos_reqs[-1].strategy_params['fast_ma'] == fold.best_params['fast_ma']


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


# ---------- 汇总 summary ----------

def test_summary_valid_is_oos_split():
    """no_signal 窗不进 mean_is_sharpe/param_stability,但进 mean_oos_sharpe/oos_win_folds。"""
    cfg = _basic_config(
        end='20210101', train_days=5, test_days=3, step_days=3,
        param_grid={'fast_ma': [10.0, 20.0]},
    )
    calendar = _trading_days_252('20200101', 20)

    # 设计 fake:根据请求的 end 日期区分 IS/OOS;IS 时按 train_start 区分前两个 fold(正常)与之后 fold(零成交)
    def controlled_run(req: BacktestRequest) -> BacktestResult:
        train_starts = ['20200101', '20200104']
        train_ends = ['20200105', '20200108', '20200111', '20200114', '20200117']
        is_train = req.end in train_ends
        if is_train:
            if req.start in train_starts:
                # 前两个 fold:正常
                return BacktestResult(
                    symbol=req.symbol, start=req.start, end=req.end,
                    initial_cash=req.cash, final_value=req.cash * 1.05,
                    total_return_pct=5.0, max_drawdown_pct=1.0,
                    trade_count=1, win_rate_pct=100.0, sharpe=1.5,
                )
            else:
                # 后续 fold:零成交
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
    """occurrences 的键必须是 str 以保证 json.dumps 不抛。"""
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
