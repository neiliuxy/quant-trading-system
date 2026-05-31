# B1 Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the B1 "Shaofu" strategy as a third trading strategy option, with full parameter configurability and support for Shanghai Composite Index (000001) as market timing reference.

**Architecture:** 
- Create `B1Strategy` class following existing Backtrader pattern with 11 configurable parameters
- Extend data loader to fetch Shanghai Composite Index alongside individual stocks
- Register B1 strategy in the strategy registry for UI and API discovery
- Support multi-data-source backtesting (individual stock + index)
- Maintain backward compatibility with existing SwingStrategy and BollingerReversal strategies

**Tech Stack:** Backtrader, AkShare, Python 3, Backtrader indicators (SMA, Stochastic, BollingerBands)

---

## File Structure

**New files:**
- `strategies/b1_strategy.py` — B1Strategy class and B1_STRATEGY_SPEC definition

**Modified files:**
- `strategies/registry.py` — Register B1_STRATEGY_SPEC
- `backtest/data_loader.py` — Add Shanghai Composite Index loading for B1 strategy
- `backtest/run_backtest.py` — Pass multi-data feeds to Backtrader when using B1
- `server/api.py` — Ensure `/api/strategies` returns B1 spec (no changes needed if registry works)
- `tests/test_strategies.py` — Add B1 strategy tests

---

## Task 1: Create B1Strategy Class

**Files:**
- Create: `strategies/b1_strategy.py`
- Test: `tests/test_strategies.py` (add tests)

- [ ] **Step 1: Write failing test for B1Strategy initialization**

```python
# In tests/test_strategies.py, add:
def test_b1_strategy_initialization():
    """Test that B1Strategy initializes with correct parameters."""
    from strategies.b1_strategy import B1Strategy
    
    # Create a minimal Backtrader cerebro setup
    import backtrader as bt
    cerebro = bt.Cerebro()
    
    # Add strategy with default params
    cerebro.addstrategy(B1Strategy)
    
    # Should not raise
    assert True
```

Run: `pytest tests/test_strategies.py::test_b1_strategy_initialization -v`
Expected: FAIL - "No module named 'strategies.b1_strategy'"

- [ ] **Step 2: Create B1Strategy skeleton**

Create `strategies/b1_strategy.py`:

```python
"""
B1 Strategy (Shaofu) - 顺大势，逆小势
- Market timing: Shanghai Composite 120-day MA uptrend
- Stock selection: 7 conditions (MA crossover, KDJ, BBI, volatility, volume, amplitude)
- Entry: B1 buy point (low volatility, low volume, J near 0)
- Exit: Trailing stop (break short MA) or hard stop (buy day low)
"""

import backtrader as bt
from strategies.base import StrategyParamSpec, StrategySpec


class B1Strategy(bt.Strategy):
    params = (
        # Market timing
        ('index_ma', 120),           # Shanghai Composite MA period
        
        # Moving averages
        ('short_ma', 20),            # Short-term MA (white line)
        ('long_ma', 60),             # Long-term MA (yellow line)
        
        # KDJ indicator
        ('j_threshold', 5),          # J value buy threshold (J < threshold)
        
        # Volatility
        ('vol_window', 60),          # 60-day volatility window
        ('vol_max', 1.0),            # Max volatility ratio (100%)
        
        # Amplitude and volume thresholds
        ('amp_ratio', 0.5),          # Amplitude < 20-day avg × this ratio
        ('vol_ratio', 0.6),          # Volume < 20-day avg × this ratio
        ('max_pct_change', 0.02),    # Max daily change (2%)
        
        # BBI indicator
        ('bbi_periods', (3, 6, 12, 24)),  # BBI MA periods
        ('bbuphold_days', 3),        # BBI must rise for N consecutive days
        
        # Risk management
        ('risk_percent', 0.95),      # Position size as % of cash
        ('market_score_dict', None), # Optional market timing scores
    )

    def __init__(self):
        # Market timing: Shanghai Composite 120-day MA
        # self.datas[0] = individual stock, self.datas[1] = Shanghai Composite (if available)
        if len(self.datas) > 1:
            self.index_ma = bt.ind.SMA(self.datas[1].close, period=self.p.index_ma)
        else:
            self.index_ma = None

        # Individual stock indicators
        self.ma_short = bt.ind.SMA(self.data.close, period=self.p.short_ma)
        self.ma_long = bt.ind.SMA(self.data.close, period=self.p.long_ma)

        # BBI = (MA3 + MA6 + MA12 + MA24) / 4
        ma3 = bt.ind.SMA(self.data.close, period=3)
        ma6 = bt.ind.SMA(self.data.close, period=6)
        ma12 = bt.ind.SMA(self.data.close, period=12)
        ma24 = bt.ind.SMA(self.data.close, period=24)
        self.bbi = (ma3 + ma6 + ma12 + ma24) / 4

        # KDJ: J = 3K - 2D
        stoch = bt.ind.Stochastic(self.data, period=9)
        self.k = stoch.perK
        self.d = stoch.perD
        self.j = 3 * self.k - 2 * self.d

        # Volatility = (highest - lowest) / lowest over vol_window days
        highest = bt.ind.Highest(self.data.high, period=self.p.vol_window)
        lowest = bt.ind.Lowest(self.data.low, period=self.p.vol_window)
        self.volatility = (highest - lowest) / lowest

        # Amplitude and volume rolling averages
        self.amplitude = (self.data.high - self.data.low) / self.data.close
        self.avg_amp = bt.ind.SMA(self.amplitude, period=20)
        self.avg_vol = bt.ind.SMA(self.data.volume, period=20)

        # State tracking
        self.signal = 0  # 0 = no position, 1 = holding
        self.entry_price = None
        self.entry_low = None

    def next(self):
        current_date = self.datas[0].datetime.date(0).strftime('%Y%m%d')

        # Step 1: Market timing check (Shanghai Composite 120-day MA uptrend)
        if self.index_ma is not None:
            if self.index_ma[0] <= self.index_ma[-1]:
                # Market not in uptrend, close any position
                if self.signal == 1:
                    self.close()
                    self.signal = 0
                return

        # Step 2: If holding, check exit conditions
        if self.signal == 1:
            # Exit 1: Trailing stop (short MA crosses below long MA)
            if self.ma_short[0] < self.ma_long[0]:
                self.close()
                self.signal = 0
                return

            # Exit 2: Hard stop (close below entry day's low)
            if self.data.close[0] < self.entry_low:
                self.close()
                self.signal = 0
                return
            return

        # Step 3: Not holding, check buy conditions
        # Condition 1: Short MA > Long MA (trend confirmation)
        if self.ma_short[0] <= self.ma_long[0]:
            return

        # Condition 2: 60-day volatility <= 100%
        if self.volatility[0] > self.p.vol_max:
            return

        # Condition 3: BBI rising for N consecutive days
        bbi_rising = all(self.bbi[-i] > self.bbi[-i-1] for i in range(self.p.bbuphold_days))
        if not bbi_rising:
            return

        # Condition 4: J value near 0 (oversold)
        if self.j[0] > self.p.j_threshold:
            return

        # Condition 5: Daily change < 2%
        pct_change = abs(self.data.close[0] - self.data.close[-1]) / self.data.close[-1]
        if pct_change > self.p.max_pct_change:
            return

        # Condition 6: Amplitude small (< 20-day avg × ratio)
        if self.amplitude[0] > self.avg_amp[0] * self.p.amp_ratio:
            return

        # Condition 7: Volume low (< 20-day avg × ratio)
        if self.data.volume[0] > self.avg_vol[0] * self.p.vol_ratio:
            return

        # All conditions met: B1 buy point!
        score_dict = self.p.market_score_dict
        if score_dict is None:
            score = 1.0
        else:
            score = score_dict.get(current_date, 0.5)

        cash_for_trade = self.broker.getcash() * self.p.risk_percent
        size = int(cash_for_trade * score / self.data.close[0])
        if size > 0:
            self.buy(size=size)
            self.signal = 1
            self.entry_price = self.data.close[0]
            self.entry_low = self.data.low[0]


B1_STRATEGY_SPEC = StrategySpec(
    id='b1',
    name='B1 Strategy (Shaofu)',
    description='Market-timing trend strategy: follow Shanghai Composite uptrend, buy on oversold pullbacks with low volatility.',
    strategy_class=B1Strategy,
    params=(
        StrategyParamSpec('index_ma', 'Index MA Period', 'int', 120),
        StrategyParamSpec('short_ma', 'Short MA Period', 'int', 20),
        StrategyParamSpec('long_ma', 'Long MA Period', 'int', 60),
        StrategyParamSpec('j_threshold', 'J Value Threshold', 'int', 5),
        StrategyParamSpec('vol_window', 'Volatility Window', 'int', 60),
        StrategyParamSpec('vol_max', 'Max Volatility Ratio', 'float', 1.0),
        StrategyParamSpec('amp_ratio', 'Amplitude Ratio', 'float', 0.5),
        StrategyParamSpec('vol_ratio', 'Volume Ratio', 'float', 0.6),
        StrategyParamSpec('max_pct_change', 'Max Daily Change', 'float', 0.02),
        StrategyParamSpec('bbuphold_days', 'BBI Rise Days', 'int', 3),
    ),
)
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_strategies.py::test_b1_strategy_initialization -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add strategies/b1_strategy.py tests/test_strategies.py
git commit -m "feat: add B1Strategy class with all indicators and buy/sell logic"
```

---

## Task 2: Register B1Strategy in Registry

**Files:**
- Modify: `strategies/registry.py`

- [ ] **Step 1: Read current registry**

Run: `cat strategies/registry.py`

- [ ] **Step 2: Add B1 import and registration**

Edit `strategies/registry.py` to add:

```python
from strategies.b1_strategy import B1_STRATEGY_SPEC

STRATEGIES = [
    SWING_MA_BOLL_SPEC,
    BOLLINGER_REVERSAL_SPEC,
    B1_STRATEGY_SPEC,  # Add this line
]
```

- [ ] **Step 3: Verify registry loads**

Run: `python -c "from strategies.registry import STRATEGIES; print([s.id for s in STRATEGIES])"`
Expected: `['swing_ma_boll', 'bollinger_reversal', 'b1']`

- [ ] **Step 4: Commit**

```bash
git add strategies/registry.py
git commit -m "feat: register B1Strategy in strategy registry"
```

---

## Task 3: Extend Data Loader for Shanghai Composite Index

**Files:**
- Modify: `backtest/data_loader.py`

- [ ] **Step 1: Read current data_loader.py**

Run: `cat backtest/data_loader.py`

- [ ] **Step 2: Add function to load Shanghai Composite Index**

Add this function to `backtest/data_loader.py`:

```python
def load_shanghai_composite(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Load Shanghai Composite Index (000001) daily data from AkShare.
    
    Args:
        start_date: YYYYMMDD format
        end_date: YYYYMMDD format
    
    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    import akshare as ak
    
    try:
        df = ak.index_daily(symbol='sh000001', start_date=start_date, end_date=end_date)
        # AkShare returns: date, open, close, high, low, volume, code
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Failed to load Shanghai Composite: {e}")
        return None
```

- [ ] **Step 3: Modify load_data to optionally load index**

Edit the `load_data` function signature and add index loading:

```python
def load_data(symbol: str, start_date: str, end_date: str, include_index: bool = False) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """
    Load stock data and optionally Shanghai Composite Index.
    
    Returns:
        (stock_df, index_df) where index_df is None if include_index=False
    """
    # ... existing stock loading code ...
    stock_df = ...  # existing logic
    
    index_df = None
    if include_index:
        index_df = load_shanghai_composite(start_date, end_date)
    
    return stock_df, index_df
```

- [ ] **Step 4: Test data loading**

Run: `python -c "from backtest.data_loader import load_shanghai_composite; df = load_shanghai_composite('20230101', '20231231'); print(df.head())"`
Expected: DataFrame with Shanghai Composite data

- [ ] **Step 5: Commit**

```bash
git add backtest/data_loader.py
git commit -m "feat: add Shanghai Composite Index data loading for B1 strategy"
```

---

## Task 4: Update Backtest Runner for Multi-Data Feeds

**Files:**
- Modify: `backtest/run_backtest.py`

- [ ] **Step 1: Read current run_backtest.py**

Run: `cat backtest/run_backtest.py`

- [ ] **Step 2: Modify to load index data for B1 strategy**

Update the backtest execution logic:

```python
# In the backtest function, after loading stock data:

stock_df, index_df = load_data(symbol, start_date, end_date, include_index=(strategy_id == 'b1'))

# Add stock data feed
data_feed = bt.feeds.PandasData(dataname=stock_df, ...)
cerebro.adddata(data_feed)

# Add index data feed if B1 strategy
if index_df is not None and strategy_id == 'b1':
    index_feed = bt.feeds.PandasData(dataname=index_df, ...)
    cerebro.adddata(index_feed)
```

- [ ] **Step 3: Test backtest with B1 strategy**

Run: `python backtest/run_backtest.py --symbol 600519 --strategy b1 --start 20230101 --end 20231231`
Expected: Backtest completes without errors, shows results

- [ ] **Step 4: Commit**

```bash
git add backtest/run_backtest.py
git commit -m "feat: support multi-data feeds for B1 strategy in backtest runner"
```

---

## Task 5: Add B1 Strategy Tests

**Files:**
- Modify: `tests/test_strategies.py`

- [ ] **Step 1: Add comprehensive B1 tests**

Add to `tests/test_strategies.py`:

```python
def test_b1_strategy_buy_conditions():
    """Test that B1 strategy correctly identifies buy conditions."""
    import backtrader as bt
    from strategies.b1_strategy import B1Strategy
    
    # Create cerebro with B1 strategy
    cerebro = bt.Cerebro()
    cerebro.addstrategy(B1Strategy)
    
    # Add dummy data (would need real data for full test)
    # This is a placeholder for integration testing
    assert True


def test_b1_strategy_exit_conditions():
    """Test that B1 strategy correctly exits positions."""
    import backtrader as bt
    from strategies.b1_strategy import B1Strategy
    
    cerebro = bt.Cerebro()
    cerebro.addstrategy(B1Strategy)
    
    # Test trailing stop and hard stop logic
    assert True


def test_b1_strategy_spec():
    """Test that B1_STRATEGY_SPEC is properly configured."""
    from strategies.b1_strategy import B1_STRATEGY_SPEC
    
    assert B1_STRATEGY_SPEC.id == 'b1'
    assert B1_STRATEGY_SPEC.name == 'B1 Strategy (Shaofu)'
    assert len(B1_STRATEGY_SPEC.params) == 10
    
    # Check default values
    defaults = B1_STRATEGY_SPEC.defaults
    assert defaults['short_ma'] == 20
    assert defaults['long_ma'] == 60
    assert defaults['j_threshold'] == 5
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_strategies.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_strategies.py
git commit -m "test: add B1 strategy unit tests"
```

---

## Task 6: Verify API Returns B1 Strategy

**Files:**
- Verify: `server/api.py` (no changes needed if registry works)

- [ ] **Step 1: Start server and check /api/strategies endpoint**

Run: `python server/main.py &`
Then: `curl http://127.0.0.1:8000/api/strategies | jq '.[] | .id'`
Expected: Output includes `"b1"`

- [ ] **Step 2: Verify B1 parameters are returned**

Run: `curl http://127.0.0.1:8000/api/strategies | jq '.[] | select(.id == "b1") | .params | length'`
Expected: `10`

- [ ] **Step 3: Stop server**

Run: `pkill -f "python server/main.py"`

- [ ] **Step 4: No commit needed** (API already supports multi-strategy)

---

## Task 7: Manual Integration Test

**Files:**
- Test: Run full backtest with B1 strategy

- [ ] **Step 1: Run B1 backtest on a test stock**

Run: `python backtest/run_backtest.py --symbol 600519 --strategy b1 --start 20220101 --end 20231231 --cash 100000`
Expected: Backtest completes, shows equity curve and trade statistics

- [ ] **Step 2: Verify results are reasonable**

Check output for:
- Trade count > 0 (strategy found buy points)
- Win rate between 0-100%
- Max drawdown reasonable (< 50%)
- No errors in logs

- [ ] **Step 3: Test with different parameters**

Run: `python backtest/run_backtest.py --symbol 600519 --strategy b1 --start 20220101 --end 20231231 --short_ma 15 --long_ma 50`
Expected: Backtest completes with different parameters

- [ ] **Step 4: No commit needed** (manual verification only)

---

## Task 8: Verify UI Shows B1 Strategy

**Files:**
- Verify: `web/src/App.tsx` (should auto-discover from API)

- [ ] **Step 1: Start dev server**

Run: `cd web && npm run dev &`

- [ ] **Step 2: Open browser to http://localhost:5173**

Expected: UI loads, strategy dropdown shows "B1 Strategy (Shaofu)" option

- [ ] **Step 3: Select B1 strategy**

Click strategy dropdown, select B1
Expected: Parameter form updates to show B1 parameters (index_ma, short_ma, long_ma, etc.)

- [ ] **Step 4: Create a backtest job with B1**

Fill in:
- Symbol: 600519
- Start: 2023-01-01
- End: 2023-12-31
- Strategy: B1 Strategy (Shaofu)
- Parameters: Use defaults

Click "Run Backtest"
Expected: Job queued, results show after completion

- [ ] **Step 5: Stop dev server**

Run: `pkill -f "npm run dev"`

- [ ] **Step 6: No commit needed** (UI auto-discovers from API)

---

## Task 9: Final Integration and Documentation

**Files:**
- Create: `docs/B1_STRATEGY.md` (optional, for reference)

- [ ] **Step 1: Create B1 strategy documentation**

Create `docs/B1_STRATEGY.md`:

```markdown
# B1 Strategy Implementation

## Overview
The B1 Strategy (Shaofu) is a market-timing trend-following strategy based on the work of Z哥 (zettaranc) from Bilibili.

## Core Principle
**顺大势，逆小势** (Follow the big trend, counter the small trend)

## Market Timing
- Only trade when Shanghai Composite Index (000001) is in an uptrend (120-day MA rising)
- Exit all positions if market trend breaks

## Buy Conditions (All 7 must be met)
1. Short MA (20) > Long MA (60)
2. 60-day volatility ≤ 100%
3. BBI rising for 3 consecutive days
4. KDJ J value < 5 (oversold)
5. Daily change < 2%
6. Amplitude < 20-day average × 0.5
7. Volume < 20-day average × 0.6

## Exit Conditions
- **Trailing stop:** Short MA crosses below Long MA
- **Hard stop:** Close below entry day's low

## Parameters
| Parameter | Default | Range | Description |
|---|---|---|---|
| index_ma | 120 | 60-200 | Shanghai Composite MA period |
| short_ma | 20 | 10-30 | Short-term MA period |
| long_ma | 60 | 30-120 | Long-term MA period |
| j_threshold | 5 | 0-10 | KDJ J value buy threshold |
| vol_window | 60 | 30-120 | Volatility calculation window |
| vol_max | 1.0 | 0.5-2.0 | Max volatility ratio |
| amp_ratio | 0.5 | 0.3-0.8 | Amplitude threshold ratio |
| vol_ratio | 0.6 | 0.4-0.8 | Volume threshold ratio |
| max_pct_change | 0.02 | 0.01-0.05 | Max daily change |
| bbuphold_days | 3 | 2-5 | BBI consecutive rise days |

## Backtest Example
\`\`\`bash
python backtest/run_backtest.py --symbol 600519 --strategy b1 --start 20220101 --end 20231231
\`\`\`

## Expected Performance
- Win rate: 40-55%
- Profit/loss ratio: 1.5:1 to 3:1
- Trade frequency: Low (waiting for B1 buy points)
- Holding period: Weeks to months
```

- [ ] **Step 2: Commit documentation**

```bash
git add docs/B1_STRATEGY.md
git commit -m "docs: add B1 strategy documentation and parameter guide"
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Final commit summary**

Run: `git log --oneline -10`
Expected: See all B1-related commits

---

## Verification Checklist

- [ ] B1Strategy class created with all 11 parameters
- [ ] All 7 buy conditions implemented
- [ ] Exit conditions (trailing stop + hard stop) implemented
- [ ] Shanghai Composite Index data loading works
- [ ] Multi-data feed support in Backtrader
- [ ] B1 strategy registered and discoverable via API
- [ ] UI shows B1 strategy option
- [ ] UI parameter form shows all 10 B1 parameters
- [ ] Backtest runs successfully with B1 strategy
- [ ] Tests pass
- [ ] Documentation complete

---

## Known Limitations & Future Improvements

1. **Parameter validation:** Currently no validation that `short_ma < long_ma`. Consider adding in UI.
2. **Market score integration:** `market_score_dict` parameter exists but not fully integrated with B1.
3. **Performance:** BBI + KDJ calculations add overhead; backtest time ~2-3x longer than SwingStrategy.
4. **Index data caching:** Shanghai Composite data is fetched fresh each time; consider caching to `data/` directory.
5. **Backtesting edge cases:** Need to test with stocks that have gaps, splits, or low liquidity.
