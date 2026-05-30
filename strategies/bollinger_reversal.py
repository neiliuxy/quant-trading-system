import backtrader as bt
from strategies.base import StrategyParamSpec, StrategySpec


class BollingerReversalStrategy(bt.Strategy):
    params = (
        ('boll_period', 20),
        ('boll_devfactor', 2.0),
    )

    def __init__(self):
        self.boll = bt.ind.BollingerBands(
            period=self.p.boll_period,
            devfactor=self.p.boll_devfactor,
        )
        self.was_below_lower = False

    def next(self):
        close = self.data.close[0]
        if close < self.boll.lines.bot[0]:
            self.was_below_lower = True
            return
        if self.position and (close >= self.boll.lines.mid[0] or close >= self.boll.lines.top[0]):
            self.close()
            return
        if self.was_below_lower and close > self.boll.lines.bot[0] and not self.position:
            self.buy()
            self.was_below_lower = False


BOLLINGER_REVERSAL_SPEC = StrategySpec(
    id='bollinger_reversal',
    name='Bollinger Reversal',
    description='Mean-reversion strategy that buys after price reclaims the lower band.',
    strategy_class=BollingerReversalStrategy,
    params=(
        StrategyParamSpec('boll_period', 'Bollinger Period', 'int', 20),
        StrategyParamSpec('boll_devfactor', 'Deviation Factor', 'float', 2.0),
    ),
)
