import backtrader as bt

from indicators.rsrs import RsrsIndicator
from strategies.base import StrategyParamSpec, StrategySpec


class CiticWaveStrategy(bt.Strategy):
    params = (
        # Market / sector / turnover filters
        ('market_ma_long', 120),
        ('sector_ma', 60),
        ('turnover_ma', 20),
        # RSRS market-timing alternative (replaces the 3-filter when on)
        ('use_rsrs_filter', False),
        ('rsrs_period', 18),
        ('rsrs_threshold', 0.0),
        # Breakout / pullback entries
        ('breakout_window', 60),
        ('pullback_lookback', 10),
        ('volume_ma', 20),
        # Bottom-fishing entry (O2): KDJ oversold + positive bar + volume spike
        ('bottom_j_threshold', 5),
        ('bottom_vol_mult', 2.0),
        # Shock-reversal entry (O4): large intraday gain on huge volume,
        # NEAR the recent 10-day low. Bypasses the market filter because
        # the volume/price action alone is a major-reversal signature
        # (e.g. 2024-09-24 for 600030, +5.6% intraday, 3.86x volume).
        ('shock_vol_mult', 3.5),
        ('shock_intraday_pct', 0.04),
        ('shock_near_low_pct', 0.15),
        # Top filter (O3): reject entries that have run too far above MA60
        ('max_extension_pct', 0.20),
        # Stop loss / trailing
        ('stop_loss_pct', 0.06),       # hard floor for the stop loss
        ('atr_period', 14),
        ('atr_multiplier', 1.5),       # primary stop distance (O1)
        ('trailing_atr_mult', 2.0),    # trailing distance once activated
        ('trailing_start_bars', 3),    # bars held before trailing activates
        # Exit / sizing
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
        self.rsrs = RsrsIndicator(self.data_market, period=self.p.rsrs_period)

        self.ma_fast = bt.ind.SMA(self.data_stock.close, period=10)
        self.ma_mid = bt.ind.SMA(self.data_stock.close, period=20)
        self.ma_slow = bt.ind.SMA(self.data_stock.close, period=60)
        self.ma_exit = bt.ind.SMA(self.data_stock.close, period=20)
        self.vol_ma = bt.ind.SMA(self.data_stock.volume, period=self.p.volume_ma)
        self.atr = bt.ind.ATR(self.data_stock, period=self.p.atr_period)
        self.highest_breakout = bt.ind.Highest(self.data_stock.high, period=self.p.breakout_window)
        self.lowest_pullback = bt.ind.Lowest(self.data_stock.low, period=self.p.pullback_lookback)

        # O2: KDJ for bottom-fishing entry
        stoch = bt.ind.Stochastic(self.data_stock, period=9)
        self.j = 3.0 * stoch.lines.percK - 2.0 * stoch.lines.percD

        self.entry_price = None
        self.entry_atr = None
        self.highest_since_entry = None
        self.trailing_active = False
        self.bar_executed = None
        self.order = None

    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return

        if order.status == order.Completed:
            if order.isbuy():
                self.entry_price = order.executed.price
                self.bar_executed = len(self)
                self.entry_atr = self.atr[0]
                self.highest_since_entry = self.data_stock.high[0]
                self.trailing_active = False
            else:
                self.entry_price = None
                self.bar_executed = None
                self.entry_atr = None
                self.highest_since_entry = None
                self.trailing_active = False

        if order.status in (order.Completed, order.Canceled, order.Margin, order.Rejected):
            self.order = None

    def _market_filter_passed(self):
        if self.p.use_rsrs_filter:
            return self.rsrs[0] > self.p.rsrs_threshold
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

        if self.order is not None:
            return

        if self.position:
            held_bars = len(self) - self.bar_executed
            if self.highest_since_entry is None:
                self.highest_since_entry = self.data_stock.high[0]
            else:
                self.highest_since_entry = max(
                    self.highest_since_entry,
                    self.data_stock.high[0],
                )

            # O1: ATR-based primary stop
            atr_stop = self.entry_price - self.entry_atr * self.p.atr_multiplier
            pct_floor = self.entry_price * (1.0 - self.p.stop_loss_pct)
            current_stop = max(atr_stop, pct_floor)

            # ATR trailing stop (top protection)
            if held_bars >= self.p.trailing_start_bars:
                self.trailing_active = True
            if self.trailing_active:
                trail_stop = self.highest_since_entry - self.entry_atr * self.p.trailing_atr_mult
                current_stop = max(current_stop, trail_stop)

            if self.data.close[0] <= current_stop:
                self.order = self.close()
                return

            if self.data.close[0] < self.ma_exit[0] and self.ma_fast[0] < self.ma_mid[0]:
                self.order = self.close()
                return

            if held_bars >= self.p.max_hold_days:
                self.order = self.close()
                return

            return

        # Compute all four signal flags first. The market filter only
        # gates breakout / pullback / bottom; the shock signal is
        # strong enough to stand on its own and is allowed to fire even
        # when the Shanghai 120-day MA hasn't rolled over yet (e.g. the
        # 2024-09-24 reversal bar).
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
        # O2: bottom-fishing — KDJ J oversold + positive bar + volume spike
        bottom_signal = (
            self.j[0] < self.p.bottom_j_threshold
            and self.data_stock.close[0] > self.data_stock.open[0]
            and self.data_stock.volume[0] > self.vol_ma[0] * self.p.bottom_vol_mult
        )
        # O4: shock-reversal — big intraday gain on huge volume, NEAR the
        # recent 10-day low. The "near low" check is what makes the signal
        # fire on real bottoms (2024-09-24, when close was 9% above the
        # 10-day low of 18.77) and not on random high-volume up bars
        # during a sustained uptrend.
        shock_signal = (
            self.data_stock.volume[0] > self.vol_ma[0] * self.p.shock_vol_mult
            and (
                self.data_stock.close[0] / self.data_stock.open[0] - 1.0
                >= self.p.shock_intraday_pct
            )
            and self.data_stock.close[0] > self.ma_mid[0]
            and self.data_stock.close[0] <= self.lowest_pullback[0] * (1.0 + self.p.shock_near_low_pct)
        )

        # O3: top filter — reject entries that have run too far above MA60
        if self.data_stock.close[0] > self.ma_slow[0] * (1.0 + self.p.max_extension_pct):
            breakout_signal = False
            pullback_signal = False
            bottom_signal = False
            shock_signal = False

        # Market filter gates the trend-following signals but not shock.
        market_ok = self._market_filter_passed()
        breakout_signal = breakout_signal and market_ok
        pullback_signal = pullback_signal and market_ok
        bottom_signal = bottom_signal and market_ok

        if breakout_signal or pullback_signal or bottom_signal or shock_signal:
            size = self._position_size()
            if size > 0:
                self.order = self.buy(size=size)


CITIC_WAVE_STRATEGY_SPEC = StrategySpec(
    id='citic_wave',
    name='Citic Wave',
    description='Market-filtered breakout/pullback/bottom-fishing swing strategy for CITIC Securities. ATR stops with trailing exit.',
    strategy_class=CiticWaveStrategy,
    params=(
        StrategyParamSpec('market_ma_long', 'Market MA', 'int', 120),
        StrategyParamSpec('sector_ma', 'Sector MA', 'int', 60),
        StrategyParamSpec('turnover_ma', 'Turnover MA', 'int', 20),
        StrategyParamSpec('use_rsrs_filter', 'Use RSRS Filter', 'bool', False),
        StrategyParamSpec('rsrs_period', 'RSRS Period', 'int', 18),
        StrategyParamSpec('rsrs_threshold', 'RSRS Threshold', 'float', 0.0),
        StrategyParamSpec('breakout_window', 'Breakout Window', 'int', 60),
        StrategyParamSpec('pullback_lookback', 'Pullback Window', 'int', 10),
        StrategyParamSpec('volume_ma', 'Volume MA', 'int', 20),
        StrategyParamSpec('bottom_j_threshold', 'Bottom J Threshold', 'int', 5),
        StrategyParamSpec('bottom_vol_mult', 'Bottom Vol Mult', 'float', 2.0),
        StrategyParamSpec('shock_vol_mult', 'Shock Vol Mult', 'float', 3.5),
        StrategyParamSpec('shock_intraday_pct', 'Shock Intraday %', 'float', 0.04),
        StrategyParamSpec('shock_near_low_pct', 'Shock Near Low %', 'float', 0.15),
        StrategyParamSpec('max_extension_pct', 'Max Extension %', 'float', 0.20),
        StrategyParamSpec('stop_loss_pct', 'Stop Loss Floor', 'float', 0.06),
        StrategyParamSpec('atr_period', 'ATR Period', 'int', 14),
        StrategyParamSpec('atr_multiplier', 'ATR Multiple', 'float', 1.5),
        StrategyParamSpec('trailing_atr_mult', 'Trailing ATR Mult', 'float', 2.0),
        StrategyParamSpec('trailing_start_bars', 'Trailing Start Bars', 'int', 3),
        StrategyParamSpec('max_hold_days', 'Max Hold Days', 'int', 30),
        StrategyParamSpec('risk_percent', 'Risk Percent', 'float', 0.95),
    ),
    required_data=('shanghai_index', 'security_etf', 'market_turnover'),
)
