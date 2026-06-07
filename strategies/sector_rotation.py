"""Sector rotation strategy for A-share securities brokers.

Adapted from the snowball / JoinQuant "ETF rotation" template:
- Universe: 3 securities brokerages (600030, 601066, 601688)
- Each bar, score every stock on two filters:
    * fast MA (5) > slow MA (20)  -> gold cross
    * 20-day return in [5%, 20%]  -> uptrend with room to run
- Pick top-N (default 1), equal-weight, rebalance every ~20 trading days.
- Optional RSRS market-timing filter: skip rotation when Shanghai Composite
  RSRS is below threshold.

Data feed layout (N+1 feeds):
    [0] Shanghai Composite (for RSRS)
    [1..N] brokerage stocks in the universe
"""

from __future__ import annotations

import backtrader as bt

from indicators.rsrs import RsrsIndicator
from strategies.base import StrategyParamSpec, StrategySpec


class SectorRotationStrategy(bt.Strategy):
    params = (
        # Momentum filters
        ('ma_fast', 5),
        ('ma_slow', 20),
        ('momentum_low', 0.05),
        ('momentum_high', 0.20),
        # Portfolio
        ('top_n', 1),
        ('rebalance_days', 20),
        ('risk_percent', 0.95),
        # RSRS market filter (uses datas[0] = Shanghai Composite)
        ('use_rsrs_filter', True),
        ('rsrs_period', 18),
        ('rsrs_threshold', 0.0),
    )

    def __init__(self):
        if len(self.datas) < 2:
            raise RuntimeError(
                'SectorRotationStrategy needs at least 2 data feeds: '
                'datas[0] = market index, datas[1..N] = stocks.'
            )
        self.data_market = self.datas[0]
        self.stock_data = list(self.datas[1:])

        # Per-stock indicators
        self.ma_fast = [bt.ind.SMA(d.close, period=self.p.ma_fast) for d in self.stock_data]
        self.ma_slow = [bt.ind.SMA(d.close, period=self.p.ma_slow) for d in self.stock_data]
        # 20-day return: (close - close[20]) / close[20]
        self.mom = [(d.close - d.close(-self.p.ma_slow)) / d.close(-self.p.ma_slow) for d in self.stock_data]

        if self.p.use_rsrs_filter:
            self.rsrs = RsrsIndicator(self.data_market, period=self.p.rsrs_period)

        self.bar_count = 0
        self.last_rebalance_bar = -10**9

    def _score_stocks(self):
        """Return list of (momentum, data_index) for stocks that pass filters."""
        scored = []
        for i, d in enumerate(self.stock_data):
            ma_f = self.ma_fast[i][0]
            ma_s = self.ma_slow[i][0]
            mom = self.mom[i][0]
            if ma_f <= 0 or ma_s <= 0:
                continue
            if not (ma_f > ma_s):
                continue
            if not (self.p.momentum_low < mom < self.p.momentum_high):
                continue
            scored.append((mom, i))
        scored.sort(reverse=True)
        return scored

    def next(self):
        self.bar_count += 1

        # Only rebalance on the configured cadence
        if self.bar_count - self.last_rebalance_bar < self.p.rebalance_days:
            return
        self.last_rebalance_bar = self.bar_count

        # Market filter
        if self.p.use_rsrs_filter and self.rsrs[0] < self.p.rsrs_threshold:
            return

        scored = self._score_stocks()
        if not scored:
            return

        selected = set(i for _, i in scored[:self.p.top_n])
        cash = self.broker.getcash() * self.p.risk_percent
        per_position_cash = cash / max(len(selected), 1)

        # Close any current holdings that aren't selected
        for i, d in enumerate(self.stock_data):
            pos = self.getposition(d)
            if pos.size > 0 and i not in selected:
                self.close(d)

        # Open new positions
        for i in selected:
            d = self.stock_data[i]
            pos = self.getposition(d)
            if pos.size == 0:
                price = d.close[0]
                if price <= 0:
                    continue
                size = int(per_position_cash / price)
                if size > 0:
                    self.buy(d, size=size)


# The strategy expects 1 market index feed + N stock feeds.
# The specific symbols are supplied by the caller via the backtest
# service. Here we document the data contract.
SECTOR_ROTATION_SPEC = StrategySpec(
    id='sector_rotation',
    name='Sector Rotation',
    description=(
        'Multi-stock rotation across securities brokerages. Each rebalance '
        'window ranks stocks on MA gold-cross + 20-day momentum, picks the '
        'top N, and holds them with optional RSRS market filter.'
    ),
    strategy_class=SectorRotationStrategy,
    params=(
        StrategyParamSpec('ma_fast', 'Fast MA', 'int', 5),
        StrategyParamSpec('ma_slow', 'Slow MA', 'int', 20),
        StrategyParamSpec('momentum_low', 'Momentum Low', 'float', 0.05),
        StrategyParamSpec('momentum_high', 'Momentum High', 'float', 0.20),
        StrategyParamSpec('top_n', 'Top N', 'int', 1),
        StrategyParamSpec('rebalance_days', 'Rebalance Days', 'int', 20),
        StrategyParamSpec('risk_percent', 'Risk Percent', 'float', 0.95),
        StrategyParamSpec('use_rsrs_filter', 'Use RSRS Filter', 'bool', True),
        StrategyParamSpec('rsrs_period', 'RSRS Period', 'int', 18),
        StrategyParamSpec('rsrs_threshold', 'RSRS Threshold', 'float', 0.0),
    ),
    # The specific symbols (brokerages) are passed via the strategy_params at
    # runtime. required_data declares the minimum feed contract.
    required_data=('shanghai_index',),
)
