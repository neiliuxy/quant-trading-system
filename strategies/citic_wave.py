import backtrader as bt

from strategies.base import StrategyParamSpec, StrategySpec


class CiticWaveStrategy(bt.Strategy):
    params = (
        ('market_ma_long', 120),
        ('sector_ma', 60),
        ('turnover_ma', 20),
        ('breakout_window', 40),
        ('pullback_lookback', 10),
        ('volume_ma', 20),
        ('stop_loss_pct', 0.06),
        ('atr_period', 14),
        ('atr_multiplier', 2.0),
        ('max_hold_days', 30),
        ('risk_percent', 0.95),
    )

    def __init__(self):
        self.data_stock = self.datas[0]
        self.data_market = self.datas[1]
        self.data_sector = self.datas[2]
        self.data_turnover = self.datas[3]

        self.market_ma = bt.ind.SMA(self.data_market.close, period=self.p.market_ma_long)
        self.sector_ma_line = bt.ind.SMA(self.data_sector.close, period=self.p.sector_ma)
        self.turnover_ma_line = bt.ind.SMA(self.data_turnover.close, period=self.p.turnover_ma)

        self.ma_fast = bt.ind.SMA(self.data_stock.close, period=10)
        self.ma_mid = bt.ind.SMA(self.data_stock.close, period=20)
        self.ma_slow = bt.ind.SMA(self.data_stock.close, period=60)
        self.ma_exit = bt.ind.SMA(self.data_stock.close, period=20)
        self.vol_ma = bt.ind.SMA(self.data_stock.volume, period=self.p.volume_ma)
        self.atr = bt.ind.ATR(self.data_stock, period=self.p.atr_period)
        self.highest_breakout = bt.ind.Highest(self.data_stock.high, period=self.p.breakout_window)
        self.lowest_pullback = bt.ind.Lowest(self.data_stock.low, period=self.p.pullback_lookback)

        self.entry_price = None
        self.bar_executed = None

    def _market_filter_passed(self):
        return (
            self.data_market.close[0] > self.market_ma[0]
            and self.data_sector.close[0] > self.sector_ma_line[0]
            and self.data_turnover.close[0] > self.turnover_ma_line[0]
        )

    def _position_size(self):
        cash_for_trade = self.broker.getcash() * self.p.risk_percent
        return int(cash_for_trade / self.data_stock.close[0])

    def next(self):
        if len(self.data) < max(self.p.market_ma_long, self.p.breakout_window, 60):
            return

        if self.position:
            stop_loss_price = max(
                self.entry_price * (1.0 - self.p.stop_loss_pct),
                self.entry_price - self.atr[0] * self.p.atr_multiplier,
            )
            held_bars = len(self) - self.bar_executed

            if self.data.close[0] <= stop_loss_price:
                self.close()
                self.entry_price = None
                self.bar_executed = None
                return

            if self.data.close[0] < self.ma_exit[0] and self.ma_fast[0] < self.ma_mid[0]:
                self.close()
                self.entry_price = None
                self.bar_executed = None
                return

            if held_bars >= self.p.max_hold_days:
                self.close()
                self.entry_price = None
                self.bar_executed = None
                return

            return

        if not self._market_filter_passed():
            return

        breakout_signal = (
            self.data_stock.close[0] >= self.highest_breakout[-1]
            and self.data_stock.volume[0] > self.vol_ma[0]
            and self.data_stock.close[0] > self.ma_mid[0]
            and self.data_stock.close[0] > self.ma_slow[0]
        )
        pullback_signal = (
            self.data_stock.close[0] > self.ma_slow[0]
            and self.lowest_pullback[0] >= self.ma_slow[0]
            and self.data_stock.close[-1] <= self.ma_mid[-1]
            and self.data_stock.close[0] > self.ma_mid[0]
            and self.data_stock.volume[0] > self.vol_ma[0]
        )

        if breakout_signal or pullback_signal:
            size = self._position_size()
            if size > 0:
                self.buy(size=size)
                self.entry_price = self.data_stock.close[0]
                self.bar_executed = len(self)


CITIC_WAVE_STRATEGY_SPEC = StrategySpec(
    id='citic_wave',
    name='Citic Wave',
    description='Market-filtered breakout and pullback swing strategy for CITIC Securities.',
    strategy_class=CiticWaveStrategy,
    params=(
        StrategyParamSpec('market_ma_long', 'Market MA', 'int', 120),
        StrategyParamSpec('sector_ma', 'Sector MA', 'int', 60),
        StrategyParamSpec('turnover_ma', 'Turnover MA', 'int', 20),
        StrategyParamSpec('breakout_window', 'Breakout Window', 'int', 40),
        StrategyParamSpec('pullback_lookback', 'Pullback Window', 'int', 10),
        StrategyParamSpec('volume_ma', 'Volume MA', 'int', 20),
        StrategyParamSpec('stop_loss_pct', 'Stop Loss %', 'float', 0.06),
        StrategyParamSpec('atr_period', 'ATR Period', 'int', 14),
        StrategyParamSpec('atr_multiplier', 'ATR Multiple', 'float', 2.0),
        StrategyParamSpec('max_hold_days', 'Max Hold Days', 'int', 30),
        StrategyParamSpec('risk_percent', 'Risk Percent', 'float', 0.95),
    ),
    required_data=('shanghai_index', 'security_etf', 'market_turnover'),
)
