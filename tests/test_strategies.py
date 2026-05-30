from strategies.registry import list_strategies, get_strategy_spec


def test_registry_exposes_both_strategies():
    ids = [spec.id for spec in list_strategies()]
    assert ids == ['swing_ma_boll', 'bollinger_reversal']


def test_strategy_spec_includes_params():
    spec = get_strategy_spec('bollinger_reversal')
    assert spec.name == 'Bollinger Reversal'
    assert [p.name for p in spec.params] == ['boll_period', 'boll_devfactor']
    assert spec.defaults == {'boll_period': 20, 'boll_devfactor': 2.0}


def test_swing_ma_boll_spec():
    spec = get_strategy_spec('swing_ma_boll')
    assert spec.name == 'Swing MA + Bollinger'
    assert [p.name for p in spec.params] == ['fast_ma', 'slow_ma', 'boll_period', 'boll_devfactor']
    assert spec.defaults == {'fast_ma': 10, 'slow_ma': 20, 'boll_period': 20, 'boll_devfactor': 2.0}
