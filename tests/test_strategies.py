import pytest
import backtrader as bt
import importlib
from datetime import datetime
from strategies.registry import list_strategies, get_strategy_spec
from strategies.b1_strategy import B1Strategy, B1_STRATEGY_SPEC
from strategies.base import StrategyParamSpec


def test_registry_exposes_all_strategies():
    ids = [spec.id for spec in list_strategies()]
    assert 'b1_strategy' in ids
    assert 'swing_ma_boll' in ids
    assert 'bollinger_reversal' in ids
    assert 'citic_wave' in ids
    assert len(ids) == 4


def test_strategy_spec_includes_params():
    spec = get_strategy_spec('bollinger_reversal')
    assert spec.name == 'Bollinger Reversal'
    assert [p.name for p in spec.params] == ['boll_period', 'boll_devfactor']
    assert spec.defaults == {'boll_period': 20, 'boll_devfactor': 2.0}


def test_strategy_spec_defaults_required_data_to_empty_tuple():
    spec = get_strategy_spec('bollinger_reversal')
    assert spec.required_data == ()


def test_b1_strategy_declares_required_data():
    assert B1_STRATEGY_SPEC.required_data == ('shanghai_index',)


def test_citic_wave_declares_required_data():
    try:
        module = importlib.import_module('strategies.citic_wave')
    except ModuleNotFoundError as exc:
        pytest.fail(f"citic_wave strategy module is missing: {exc}")

    assert module.CITIC_WAVE_STRATEGY_SPEC.required_data == (
        'shanghai_index',
        'security_etf',
        'market_turnover',
    )


def test_citic_wave_is_registered_with_expected_defaults():
    spec = get_strategy_spec('citic_wave')
    assert spec.id == 'citic_wave'
    assert spec.required_data == (
        'shanghai_index',
        'security_etf',
        'market_turnover',
    )
    assert spec.defaults['market_ma_long'] == 120
    assert spec.defaults['sector_ma'] == 60


def test_swing_ma_boll_spec():
    spec = get_strategy_spec('swing_ma_boll')
    assert spec.name == 'Swing MA + Bollinger'
    assert [p.name for p in spec.params] == ['fast_ma', 'slow_ma', 'boll_period', 'boll_devfactor']
    assert spec.defaults == {'fast_ma': 10, 'slow_ma': 20, 'boll_period': 20, 'boll_devfactor': 2.0}


# ============================================================================
# B1Strategy Tests
# ============================================================================

class TestB1StrategySpec:
    """Test B1_STRATEGY_SPEC configuration"""

    def test_spec_id(self):
        """Test spec has correct id"""
        assert B1_STRATEGY_SPEC.id == 'b1_strategy'

    def test_spec_name(self):
        """Test spec has correct name"""
        assert B1_STRATEGY_SPEC.name == 'B1 Strategy (少妇战法)'

    def test_spec_description(self):
        """Test spec has description"""
        assert 'Trend-following' in B1_STRATEGY_SPEC.description
        assert 'oversold pullback' in B1_STRATEGY_SPEC.description

    def test_spec_strategy_class(self):
        """Test spec references correct strategy class"""
        assert B1_STRATEGY_SPEC.strategy_class is B1Strategy

    def test_spec_has_10_params(self):
        """Test spec has exactly 10 parameters"""
        assert len(B1_STRATEGY_SPEC.params) == 10

    def test_spec_param_names(self):
        """Test spec has all expected parameter names"""
        param_names = [p.name for p in B1_STRATEGY_SPEC.params]
        expected = [
            'index_ma', 'short_ma', 'long_ma', 'j_threshold',
            'vol_window', 'vol_max', 'amp_ratio', 'vol_ratio',
            'max_pct_change', 'bbuphold_days'
        ]
        assert param_names == expected

    def test_spec_param_defaults(self):
        """Test spec parameters have correct default values"""
        defaults = B1_STRATEGY_SPEC.defaults
        assert defaults == {
            'index_ma': 120,
            'short_ma': 20,
            'long_ma': 60,
            'j_threshold': 5,
            'vol_window': 60,
            'vol_max': 1.0,
            'amp_ratio': 0.5,
            'vol_ratio': 0.6,
            'max_pct_change': 0.02,
            'bbuphold_days': 3,
        }

    def test_spec_param_types(self):
        """Test spec parameters have correct types"""
        param_types = {p.name: p.type for p in B1_STRATEGY_SPEC.params}
        assert param_types['index_ma'] == 'int'
        assert param_types['short_ma'] == 'int'
        assert param_types['long_ma'] == 'int'
        assert param_types['j_threshold'] == 'int'
        assert param_types['vol_window'] == 'int'
        assert param_types['bbuphold_days'] == 'int'
        assert param_types['vol_max'] == 'float'
        assert param_types['amp_ratio'] == 'float'
        assert param_types['vol_ratio'] == 'float'
        assert param_types['max_pct_change'] == 'float'

    def test_spec_params_are_param_specs(self):
        """Test all params are StrategyParamSpec instances"""
        for param in B1_STRATEGY_SPEC.params:
            assert isinstance(param, StrategyParamSpec)
            assert param.name
            assert param.label
            assert param.type in ('int', 'float', 'str', 'bool')
            assert param.default is not None


class TestB1StrategyInitialization:
    """Test B1Strategy initialization"""

    def _create_cerebro_with_data(self):
        """Helper to create a Cerebro engine with sample data"""
        cerebro = bt.Cerebro()

        # Create minimal OHLCV data
        data = bt.feeds.PandasData(
            dataname=self._create_sample_dataframe(),
            fromdate=datetime(2023, 1, 1),
            todate=datetime(2023, 12, 31),
        )
        cerebro.adddata(data)
        cerebro.broker.setcash(100000.0)
        return cerebro

    def _create_sample_dataframe(self):
        """Create a sample DataFrame with OHLCV data"""
        import pandas as pd
        import numpy as np

        dates = pd.date_range('2023-01-01', periods=250, freq='D')
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(250) * 0.5)

        df = pd.DataFrame({
            'open': close + np.random.randn(250) * 0.2,
            'high': close + abs(np.random.randn(250) * 0.3),
            'low': close - abs(np.random.randn(250) * 0.3),
            'close': close,
            'volume': np.random.randint(1000000, 5000000, 250),
        }, index=dates)

        return df

    def test_strategy_initializes(self):
        """Test B1Strategy can be instantiated"""
        cerebro = self._create_cerebro_with_data()
        cerebro.addstrategy(B1Strategy)

        # Should not raise
        cerebro.run()

    def test_strategy_has_default_params(self):
        """Test strategy has all default parameters"""
        cerebro = self._create_cerebro_with_data()
        cerebro.addstrategy(B1Strategy)

        results = cerebro.run()
        strategy = results[0]

        assert strategy.p.index_ma == 120
        assert strategy.p.short_ma == 20
        assert strategy.p.long_ma == 60
        assert strategy.p.j_threshold == 5
        assert strategy.p.vol_window == 60
        assert strategy.p.vol_max == 1.0
        assert strategy.p.amp_ratio == 0.5
        assert strategy.p.vol_ratio == 0.6
        assert strategy.p.max_pct_change == 0.02
        assert strategy.p.bbuphold_days == 3

    def test_strategy_initializes_indicators(self):
        """Test strategy initializes all required indicators"""
        cerebro = self._create_cerebro_with_data()
        cerebro.addstrategy(B1Strategy)

        results = cerebro.run()
        strategy = results[0]

        # Check indicators are created
        assert hasattr(strategy, 'index_ma')
        assert hasattr(strategy, 'ma_short')
        assert hasattr(strategy, 'ma_long')
        assert hasattr(strategy, 'bbi')
        assert hasattr(strategy, 'k')
        assert hasattr(strategy, 'd')
        assert hasattr(strategy, 'j')
        assert hasattr(strategy, 'volatility')
        assert hasattr(strategy, 'amplitude')
        assert hasattr(strategy, 'avg_amp')
        assert hasattr(strategy, 'avg_vol')

    def test_strategy_initializes_entry_tracking(self):
        """Test strategy initializes entry price tracking"""
        cerebro = self._create_cerebro_with_data()
        cerebro.addstrategy(B1Strategy)

        results = cerebro.run()
        strategy = results[0]

        assert strategy.entry_price is None
        assert strategy.entry_low is None

    def test_strategy_accepts_custom_params(self):
        """Test strategy accepts custom parameter values"""
        cerebro = self._create_cerebro_with_data()
        cerebro.addstrategy(
            B1Strategy,
            index_ma=100,
            short_ma=15,
            long_ma=50,
            j_threshold=10,
        )

        results = cerebro.run()
        strategy = results[0]

        assert strategy.p.index_ma == 100
        assert strategy.p.short_ma == 15
        assert strategy.p.long_ma == 50
        assert strategy.p.j_threshold == 10


class TestB1StrategyBuyConditions:
    """Test B1Strategy buy conditions logic"""

    def test_no_buy_when_market_not_in_uptrend(self):
        """Test strategy does not buy when market MA is not in uptrend"""
        # This is a structural test - the strategy checks index_ma[0] > index_ma[-1]
        # We verify the logic exists in the code
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.index_ma[0] <= self.index_ma[-1]' in source

    def test_no_buy_when_short_ma_below_long_ma(self):
        """Test strategy does not buy when short MA <= long MA"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.ma_short[0] <= self.ma_long[0]' in source

    def test_no_buy_when_volatility_too_high(self):
        """Test strategy does not buy when volatility exceeds threshold"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.volatility[0] > self.p.vol_max' in source

    def test_no_buy_when_bbi_not_rising(self):
        """Test strategy does not buy when BBI is not rising for required days"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.bbi[-i] <= self.bbi[-i - 1]' in source

    def test_no_buy_when_j_not_oversold(self):
        """Test strategy does not buy when KDJ J is not oversold"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.j[0] > self.p.j_threshold' in source

    def test_no_buy_when_daily_change_too_large(self):
        """Test strategy does not buy when daily pct change exceeds threshold"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'pct_change > self.p.max_pct_change' in source

    def test_no_buy_when_amplitude_too_large(self):
        """Test strategy does not buy when amplitude exceeds threshold"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.amplitude[0] > self.avg_amp[0] * self.p.amp_ratio' in source

    def test_no_buy_when_volume_too_high(self):
        """Test strategy does not buy when volume exceeds threshold"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.data.volume[0] > self.avg_vol[0] * self.p.vol_ratio' in source

    def test_all_seven_buy_conditions_checked(self):
        """Test all 7 buy conditions are checked in order"""
        import inspect
        source = inspect.getsource(B1Strategy.next)

        conditions = [
            'self.ma_short[0] <= self.ma_long[0]',
            'self.volatility[0] > self.p.vol_max',
            'self.bbi[-i] <= self.bbi[-i - 1]',
            'self.j[0] > self.p.j_threshold',
            'pct_change > self.p.max_pct_change',
            'self.amplitude[0] > self.avg_amp[0] * self.p.amp_ratio',
            'self.data.volume[0] > self.avg_vol[0] * self.p.vol_ratio',
        ]

        for condition in conditions:
            assert condition in source, f"Missing condition: {condition}"


class TestB1StrategyExitConditions:
    """Test B1Strategy exit conditions logic"""

    def test_exit_on_short_ma_below_long_ma(self):
        """Test strategy exits when short MA crosses below long MA"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.ma_short[0] < self.ma_long[0]' in source
        assert 'self.close()' in source

    def test_exit_on_close_below_entry_low(self):
        """Test strategy exits when close falls below entry low"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.data.close[0] < self.entry_low' in source

    def test_exit_clears_entry_tracking(self):
        """Test strategy clears entry price and low on exit"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.entry_price = None' in source
        assert 'self.entry_low = None' in source

    def test_exit_conditions_only_when_holding(self):
        """Test exit conditions are only checked when position exists"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'if self.position:' in source

    def test_two_exit_conditions_exist(self):
        """Test strategy has two distinct exit conditions"""
        import inspect
        source = inspect.getsource(B1Strategy.next)

        # Count exit conditions
        exit_count = source.count('self.close()')
        # Should have at least 2 exits (trailing stop + hard stop)
        assert exit_count >= 2


class TestB1StrategyBuyExecution:
    """Test B1Strategy buy execution logic"""

    def test_buy_uses_market_score_dict(self):
        """Test strategy uses market_score_dict if provided"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'score_dict = self.p.market_score_dict' in source
        assert 'score_dict.get(current_date' in source

    def test_buy_defaults_score_to_one(self):
        """Test strategy defaults score to 1.0 if no score_dict"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'score = 1.0' in source

    def test_buy_uses_95_percent_cash(self):
        """Test strategy uses 95% of available cash for position sizing"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert '0.95' in source

    def test_buy_records_entry_price(self):
        """Test strategy records entry price on buy"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.entry_price = self.data.close[0]' in source

    def test_buy_records_entry_low(self):
        """Test strategy records entry low on buy"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'self.entry_low = self.data.low[0]' in source

    def test_buy_only_if_size_positive(self):
        """Test strategy only buys if calculated size is positive"""
        import inspect
        source = inspect.getsource(B1Strategy.next)
        assert 'if size > 0:' in source
        assert 'self.buy(size=size)' in source
