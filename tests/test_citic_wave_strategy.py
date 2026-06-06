import importlib
import inspect

import pytest


def _load_citic_wave_module():
    try:
        return importlib.import_module('strategies.citic_wave')
    except ModuleNotFoundError as exc:
        pytest.fail(f"citic_wave strategy module is missing: {exc}")


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
    assert 'self.buy(size=size)' in source
    assert 'stop_loss_price' in source
    assert 'self.data.close[0] < self.ma_exit[0]' in source
    assert 'self.bar_executed' in source
