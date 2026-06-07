import importlib
import inspect

import backtrader as bt
import pandas as pd
import pytest


def _load_citic_wave_module():
    try:
        return importlib.import_module('strategies.citic_wave')
    except ModuleNotFoundError as exc:
        pytest.fail(f"citic_wave strategy module is missing: {exc}")


def _build_ohlcv_frame(closes, *, opens=None, highs=None, lows=None, volumes=None):
    if opens is None:
        opens = closes
    if highs is None:
        highs = [max(open_, close) + 1.0 for open_, close in zip(opens, closes)]
    if lows is None:
        lows = [min(open_, close) - 1.0 for open_, close in zip(opens, closes)]
    if volumes is None:
        volumes = [1000.0] * len(closes)

    return pd.DataFrame(
        {
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes,
        },
        index=pd.date_range('2023-01-02', periods=len(closes), freq='B'),
    )


def _create_four_feed_frames():
    stock_closes = ([100.0] * 130) + [110.0, 112.0] + ([113.0] * 18)
    stock_opens = ([100.0] * 130) + [100.0, 112.0] + ([113.0] * 18)
    stock_highs = ([101.0] * 130) + [111.0, 113.0] + ([114.0] * 18)
    stock_lows = ([99.0] * 130) + [99.0, 111.0] + ([112.0] * 18)
    stock_volumes = ([1000.0] * 130) + [10000.0, 9000.0] + ([9000.0] * 18)

    market_closes = [100.0 + (idx * 0.5) for idx in range(len(stock_closes))]
    sector_closes = [50.0 + (idx * 0.3) for idx in range(len(stock_closes))]
    turnover_closes = [1000.0 + (idx * 5.0) for idx in range(len(stock_closes))]

    return (
        _build_ohlcv_frame(
            stock_closes,
            opens=stock_opens,
            highs=stock_highs,
            lows=stock_lows,
            volumes=stock_volumes,
        ),
        _build_ohlcv_frame(market_closes),
        _build_ohlcv_frame(sector_closes),
        _build_ohlcv_frame(turnover_closes),
    )


def _run_strategy(strategy_class, **strategy_params):
    cerebro = bt.Cerebro()
    for frame in _create_four_feed_frames():
        cerebro.adddata(bt.feeds.PandasData(dataname=frame))
    cerebro.broker.setcash(100000.0)
    cerebro.addstrategy(strategy_class, **strategy_params)
    return cerebro.run()[0]


def test_citic_wave_spec_has_expected_identity_and_defaults():
    module = _load_citic_wave_module()

    assert module.CITIC_WAVE_STRATEGY_SPEC.id == 'citic_wave'
    assert module.CITIC_WAVE_STRATEGY_SPEC.required_data == (
        'shanghai_index',
        'security_etf',
        'market_turnover',
    )
    assert module.CITIC_WAVE_STRATEGY_SPEC.defaults['market_ma_long'] == 120
    assert module.CITIC_WAVE_STRATEGY_SPEC.defaults['sector_ma'] == 60


def test_citic_wave_init_assigns_expected_feeds():
    module = _load_citic_wave_module()

    source = inspect.getsource(module.CiticWaveStrategy.__init__)
    assert 'self.data_market = self.datas[1]' in source
    assert 'self.data_sector = self.datas[2]' in source
    assert 'self.data_turnover = self.datas[3]' in source


def test_citic_wave_next_contains_required_entry_and_exit_logic():
    module = _load_citic_wave_module()

    source = inspect.getsource(module.CiticWaveStrategy.next)
    assert 'breakout_signal' in source
    assert 'pullback_signal' in source
    assert 'bottom_signal' in source
    assert 'self.buy(size=size)' in source
    assert 'current_stop' in source
    assert 'self.entry_atr' in source
    assert 'self.data.close[0] < self.ma_exit[0]' in source
    assert 'self.bar_executed' in source


def test_citic_wave_spec_exposes_optimization_params():
    module = _load_citic_wave_module()

    spec = module.CITIC_WAVE_STRATEGY_SPEC
    param_names = {p.name for p in spec.params}
    assert 'bottom_j_threshold' in param_names
    assert 'bottom_vol_mult' in param_names
    assert 'max_extension_pct' in param_names
    assert 'trailing_atr_mult' in param_names
    assert 'trailing_start_bars' in param_names
    assert spec.defaults['bottom_j_threshold'] == 5
    assert spec.defaults['bottom_vol_mult'] == 2.0
    assert spec.defaults['max_extension_pct'] == 0.25
    assert spec.defaults['trailing_atr_mult'] == 2.0


def test_citic_wave_init_uses_kdj_for_bottom_signal():
    module = _load_citic_wave_module()

    source = inspect.getsource(module.CiticWaveStrategy.__init__)
    assert 'Stochastic' in source
    assert 'self.j' in source


def test_citic_wave_next_has_top_filter_and_trailing_stop():
    module = _load_citic_wave_module()

    source = inspect.getsource(module.CiticWaveStrategy.next)
    assert 'max_extension_pct' in source
    assert 'ma_slow[0] * (1.0 + self.p.max_extension_pct)' in source
    assert 'trailing_active' in source
    assert 'trailing_start_bars' in source
    assert 'highest_since_entry' in source


def test_citic_wave_runs_with_four_feeds_without_index_error():
    module = _load_citic_wave_module()

    strategy = _run_strategy(module.CiticWaveStrategy, max_hold_days=200)

    assert len(strategy.datas) == 4
    assert strategy.data_market is strategy.datas[1]
    assert strategy.data_sector is strategy.datas[2]
    assert strategy.data_turnover is strategy.datas[3]


def test_citic_wave_records_entry_state_from_completed_buy_fill():
    module = _load_citic_wave_module()

    class ObservingCiticWaveStrategy(module.CiticWaveStrategy):
        def __init__(self):
            super().__init__()
            self.order_events = []

        def notify_order(self, order):
            super().notify_order(order)
            self.order_events.append(
                {
                    'status': order.getstatusname(),
                    'isbuy': order.isbuy(),
                    'bar': len(self),
                    'entry_price': self.entry_price,
                    'bar_executed': self.bar_executed,
                    'executed_price': order.executed.price,
                }
            )

    strategy = _run_strategy(ObservingCiticWaveStrategy, max_hold_days=200)

    submitted_events = [
        event for event in strategy.order_events
        if event['isbuy'] and event['status'] in {'Submitted', 'Accepted'}
    ]
    assert submitted_events
    for event in submitted_events:
        assert event['entry_price'] is None
        assert event['bar_executed'] is None

    completed_buy = next(
        event for event in strategy.order_events
        if event['isbuy'] and event['status'] == 'Completed'
    )
    assert completed_buy['entry_price'] == completed_buy['executed_price']
    assert completed_buy['bar_executed'] == completed_buy['bar']


def test_citic_wave_clears_entry_state_on_completed_exit_fill():
    module = _load_citic_wave_module()

    class ObservingCiticWaveStrategy(module.CiticWaveStrategy):
        def __init__(self):
            super().__init__()
            self.order_events = []

        def notify_order(self, order):
            super().notify_order(order)
            self.order_events.append(
                {
                    'status': order.getstatusname(),
                    'isbuy': order.isbuy(),
                    'entry_price': self.entry_price,
                    'bar_executed': self.bar_executed,
                }
            )

    strategy = _run_strategy(ObservingCiticWaveStrategy, max_hold_days=1)

    buy_completed = next(
        event for event in strategy.order_events
        if event['isbuy'] and event['status'] == 'Completed'
    )
    sell_submitted = [
        event for event in strategy.order_events
        if (not event['isbuy']) and event['status'] in {'Submitted', 'Accepted'}
    ]
    assert sell_submitted
    for event in sell_submitted:
        assert event['entry_price'] == buy_completed['entry_price']
        assert event['bar_executed'] == buy_completed['bar_executed']

    sell_completed = next(
        event for event in strategy.order_events
        if (not event['isbuy']) and event['status'] == 'Completed'
    )
    assert sell_completed['entry_price'] is None
    assert sell_completed['bar_executed'] is None
