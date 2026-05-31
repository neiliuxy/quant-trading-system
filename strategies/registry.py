from strategies.b1_strategy import B1Strategy, B1_STRATEGY_SPEC
from strategies.bollinger_reversal import BollingerReversalStrategy, BOLLINGER_REVERSAL_SPEC
from strategies.swing_ma_boll import SwingStrategy, SWING_MA_BOLL_SPEC

_STRATEGIES = {
    B1_STRATEGY_SPEC.id: B1_STRATEGY_SPEC,
    SWING_MA_BOLL_SPEC.id: SWING_MA_BOLL_SPEC,
    BOLLINGER_REVERSAL_SPEC.id: BOLLINGER_REVERSAL_SPEC,
}


def list_strategies():
    return list(_STRATEGIES.values())


def get_strategy_spec(strategy_id: str):
    return _STRATEGIES[strategy_id]
