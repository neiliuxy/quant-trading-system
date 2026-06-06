"""
B1 Strategy - Trend-following with oversold pullback entry
- Market timing: Shanghai Composite 120-day MA uptrend
- Entry: 7 conditions (short MA > long MA, low volatility, BBI rising, J oversold, etc.)
- Exit: Trailing stop (MA crossover) or hard stop (below entry low)
- Holding period: 3-10 trading days typical
"""

import backtrader as bt
from strategies.base import StrategyParamSpec, StrategySpec


class B1Strategy(bt.Strategy):
    params = (
        ('index_ma', 120),           # Market timing: Shanghai Composite MA period
        ('short_ma', 20),            # Short-term MA (white line)
        ('long_ma', 60),             # Long-term MA (yellow line)
        ('j_threshold', 5),          # KDJ J value buy threshold (oversold)
        ('vol_window', 60),          # Volatility calculation window (days)
        ('vol_max', 1.0),            # Max volatility ratio (100%)
        ('amp_ratio', 0.5),          # Amplitude threshold (× 20-day avg)
        ('vol_ratio', 0.6),          # Volume threshold (× 20-day avg)
        ('max_pct_change', 0.02),    # Max daily pct change (2%)
        ('bbi_periods', (3, 6, 12, 24)),  # BBI component periods
        ('bbuphold_days', 3),        # BBI consecutive up days required
        ('market_score_dict', None), # Optional market timing scores by date
    )

    def __init__(self):
        # --- Market timing: Shanghai Composite 120-day MA ---
        # Use index data feed (datas[1]) if available, otherwise fall back to stock data (datas[0])
        index_data = self.datas[1] if len(self.datas) > 1 else self.data
        self.index_ma = bt.ind.SMA(index_data.close, period=self.p.index_ma)

        # --- Individual stock indicators ---
        self.ma_short = bt.ind.SMA(self.data.close, period=self.p.short_ma)
        self.ma_long = bt.ind.SMA(self.data.close, period=self.p.long_ma)

        # BBI = (MA3 + MA6 + MA12 + MA24) / 4
        ma3 = bt.ind.SMA(self.data.close, period=self.p.bbi_periods[0])
        ma6 = bt.ind.SMA(self.data.close, period=self.p.bbi_periods[1])
        ma12 = bt.ind.SMA(self.data.close, period=self.p.bbi_periods[2])
        ma24 = bt.ind.SMA(self.data.close, period=self.p.bbi_periods[3])
        self.bbi = (ma3 + ma6 + ma12 + ma24) / 4.0

        # KDJ: J = 3K - 2D
        stoch = bt.ind.Stochastic(self.data, period=9)
        self.k = stoch.lines.percK
        self.d = stoch.lines.percD
        self.j = 3.0 * self.k - 2.0 * self.d

        # Volatility = (highest - lowest) / lowest over vol_window days
        highest = bt.ind.Highest(self.data.high, period=self.p.vol_window)
        lowest = bt.ind.Lowest(self.data.low, period=self.p.vol_window)
        self.volatility = (highest - lowest) / lowest

        # Amplitude = (high - low) / close, with 20-day SMA
        self.amplitude = (self.data.high - self.data.low) / self.data.close
        self.avg_amp = bt.ind.SMA(self.amplitude, period=20)
        self.avg_vol = bt.ind.SMA(self.data.volume, period=20)

        # Track entry price for hard stop loss
        self.entry_price = None
        self.entry_low = None

    def next(self):
        current_date = self.datas[0].datetime.date(0).strftime('%Y%m%d')

        # --- Market timing check: 120-day MA uptrend ---
        # Only trade when market is in uptrend
        if self.index_ma[0] <= self.index_ma[-1]:
            # Market not in uptrend, exit if holding
            if self.position:
                self.close()
            return

        # --- Exit conditions (if holding) ---
        if self.position:
            # Exit 1: Trailing stop - short MA crosses below long MA
            if self.ma_short[0] < self.ma_long[0]:
                self.close()
                self.entry_price = None
                self.entry_low = None
                return

            # Exit 2: Hard stop - close below entry low
            if self.entry_low is not None and self.data.close[0] < self.entry_low:
                self.close()
                self.entry_price = None
                self.entry_low = None
                return

            return

        # --- Buy conditions (if not holding) ---
        # All 7 conditions must be met for B1 entry

        # Condition 1: Short MA > Long MA (follow trend)
        if self.ma_short[0] <= self.ma_long[0]:
            return

        # Condition 2: 60-day volatility ≤ 100% (avoid overheated stocks)
        if self.volatility[0] > self.p.vol_max:
            return

        # Condition 3: BBI consecutive up days
        bbi_up = True
        for i in range(self.p.bbuphold_days):
            if self.bbi[-i] <= self.bbi[-i - 1]:
                bbi_up = False
                break
        if not bbi_up:
            return

        # Condition 4: KDJ J value near 0 (oversold)
        if self.j[0] > self.p.j_threshold:
            return

        # Condition 5: Daily pct change < 2% (low volume, stable)
        pct_change = abs(self.data.close[0] - self.data.close[-1]) / self.data.close[-1]
        if pct_change > self.p.max_pct_change:
            return

        # Condition 6: Amplitude small (current < 20-day avg × ratio)
        if self.amplitude[0] > self.avg_amp[0] * self.p.amp_ratio:
            return

        # Condition 7: Volume low (current < 20-day avg × ratio)
        if self.data.volume[0] > self.avg_vol[0] * self.p.vol_ratio:
            return

        # --- All conditions met: B1 buy point! ---
        score_dict = self.p.market_score_dict
        if score_dict is None:
            score = 1.0
        else:
            score = score_dict.get(current_date, 0.5)

        # Size calculation: use 95% of cash
        cash_for_trade = self.broker.getcash() * 0.95
        size = int(cash_for_trade * score / self.data.close[0])

        if size > 0:
            self.buy(size=size)
            self.entry_price = self.data.close[0]
            self.entry_low = self.data.low[0]


B1_STRATEGY_SPEC = StrategySpec(
    id='b1_strategy',
    name='B1 Strategy (少妇战法)',
    description='Trend-following with oversold pullback entry. Market timing via 120-day MA, entry via 7 conditions.',
    strategy_class=B1Strategy,
    params=(
        StrategyParamSpec('index_ma', 'Market Timing MA', 'int', 120),
        StrategyParamSpec('short_ma', 'Short MA', 'int', 20),
        StrategyParamSpec('long_ma', 'Long MA', 'int', 60),
        StrategyParamSpec('j_threshold', 'KDJ J Threshold', 'int', 5),
        StrategyParamSpec('vol_window', 'Volatility Window', 'int', 60),
        StrategyParamSpec('vol_max', 'Max Volatility', 'float', 1.0),
        StrategyParamSpec('amp_ratio', 'Amplitude Ratio', 'float', 0.5),
        StrategyParamSpec('vol_ratio', 'Volume Ratio', 'float', 0.6),
        StrategyParamSpec('max_pct_change', 'Max Daily Change', 'float', 0.02),
        StrategyParamSpec('bbuphold_days', 'BBI Up Days', 'int', 3),
    ),
    required_data=('shanghai_index',),
)
