# B1 Strategy (少妇战法) Documentation

> **Core Principle: "Follow the major trend, counter the minor trend"** (顺大势，逆小势)
>
> A classic retail trading strategy from B站 UP 主 zettaranc (Z哥) that combines trend-following with oversold pullback entry.

---

## Overview

The B1 Strategy is a low-frequency swing trading approach designed for A-shares with typical holding periods of 3-10 trading days. It operates on the principle of entering during minor pullbacks within a major uptrend, using a disciplined set of quantifiable conditions.

| Metric | Value |
|--------|-------|
| Win Rate | 40-55% |
| Profit/Loss Ratio | 1.5:1 ~ 3:1 |
| Trading Frequency | Low (waiting for entry signals) |
| Holding Period | 3-10 trading days typical |
| Applicable Stocks | Mid-cap stocks in uptrend with pullbacks |
| Operability | ✅ High (office workers can check once at market close) |

---

## Core Principle

**顺大势** (Follow the major trend)
- Only trade when the market (Shanghai Composite or CSI 300) is in an uptrend or consolidation phase
- Avoid trading in downtrends

**逆小势** (Counter the minor trend)
- Enter when individual stocks pull back and stabilize at low volume
- Never chase rallies; wait for oversold conditions

---

## Market Timing Rules

The strategy only initiates trades when the broader market meets these conditions:

### Market Timing Criteria

| Condition | Status |
|-----------|--------|
| Shanghai Composite 120-day MA trending upward | ✅ Trade |
| Shanghai Composite 120-day MA trending downward | ❌ Do not trade |
| Consolidation phase (MA flat) | ✅ Trade cautiously |

**Implementation:** Use the Shanghai Composite Index (000001.SH) or CSI 300 (000300.SH) as the market timing reference. Calculate the 120-day simple moving average. Only proceed with entry signals when the current price is above this MA and the MA is rising.

---

## Buy Conditions (7 Criteria)

All 7 conditions must be satisfied simultaneously for a valid B1 entry signal. This multi-condition filter ensures high-quality entry points.

### Condition 1: Trend Alignment (Short MA > Long MA)
- **Rule:** 20-day MA > 60-day MA
- **Meaning:** Short-term trend is above long-term trend (white line above yellow line)
- **Rationale:** Confirms the stock is in an uptrend

### Condition 2: Volatility Control (60-day volatility ≤ 100%)
- **Rule:** (Highest - Lowest) / Lowest over past 60 days ≤ 1.0
- **Meaning:** Avoid stocks that have already surged dramatically
- **Rationale:** Prevents entering overheated, already-pumped stocks

### Condition 3: BBI Consecutive Rise (3+ days)
- **Rule:** BBI = (MA3 + MA6 + MA12 + MA24) / 4, rising for 3+ consecutive days
- **Meaning:** Multi-timeframe momentum indicator showing sustained strength
- **Rationale:** Confirms bullish momentum across multiple timeframes

### Condition 4: KDJ Oversold (J value near 0)
- **Rule:** KDJ J value < 5 (where J = 3K - 2D)
- **Meaning:** Stochastic indicator in oversold territory
- **Rationale:** Signals potential reversal from oversold conditions

### Condition 5: Low Daily Change (< 2%)
- **Rule:** |Close - Previous Close| / Previous Close < 0.02
- **Meaning:** Minimal daily price movement
- **Rationale:** Indicates low volume, stable consolidation (地量地价)

### Condition 6: Small Amplitude
- **Rule:** (High - Low) / Close < 20-day average amplitude × 0.5
- **Meaning:** Intraday range is smaller than historical average
- **Rationale:** Shows selling pressure has dried up

### Condition 7: Low Volume (缩量)
- **Rule:** Current volume < 20-day average volume × 0.6
- **Meaning:** Trading volume is below historical average
- **Rationale:** Confirms consolidation at low volume (地量)

---

## Exit Conditions

### Exit 1: Trailing Stop (Trend Reversal)
- **Trigger:** 20-day MA crosses below 60-day MA (死叉)
- **Meaning:** Short-term trend breaks below long-term trend
- **Action:** Close entire position
- **Rationale:** Trend-following discipline; let profits run until trend breaks

### Exit 2: Hard Stop Loss
- **Trigger:** Close price falls below entry day's low
- **Meaning:** Support level broken
- **Action:** Close entire position immediately
- **Rationale:** Risk management; no holding through support breaks

### Exit 3: Market Timing Exit
- **Trigger:** Shanghai Composite 120-day MA turns downward
- **Meaning:** Broader market exits uptrend
- **Action:** Close all positions
- **Rationale:** Macro-level risk management; don't fight the market

---

## Parameter Table

| Parameter | Default | Min | Max | Description |
|-----------|---------|-----|-----|-------------|
| `index_ma` | 120 | 100 | 150 | Market timing MA period (Shanghai Composite) |
| `short_ma` | 20 | 10 | 30 | Short-term MA period (white line) |
| `long_ma` | 60 | 30 | 120 | Long-term MA period (yellow line) |
| `j_threshold` | 5 | 0 | 10 | KDJ J value buy threshold (lower = fewer signals) |
| `vol_window` | 60 | 30 | 120 | Volatility calculation window (days) |
| `vol_max` | 1.0 | 0.8 | 1.5 | Max volatility ratio (100% = no limit) |
| `amp_ratio` | 0.5 | 0.3 | 0.7 | Amplitude threshold (× 20-day avg) |
| `vol_ratio` | 0.6 | 0.4 | 0.8 | Volume threshold (× 20-day avg) |
| `max_pct_change` | 0.02 | 0.01 | 0.03 | Max daily % change (2%) |
| `bbuphold_days` | 3 | 2 | 5 | BBI consecutive up days required |

### Parameter Tuning Guidelines

- **Stricter filters** (lower `amp_ratio`, `vol_ratio`, higher `j_threshold`): Fewer but higher-quality signals
- **Looser filters** (higher `amp_ratio`, `vol_ratio`, lower `j_threshold`): More frequent signals but lower quality
- **Recommendation:** Start with defaults, run 3-5 years of backtest, only adjust if trade frequency is too low (< 5 trades/year)

---

## Backtest Example Commands

### Basic Backtest (平安银行 000001, 2020-2023)
```bash
python backtest/run_backtest.py \
  --strategy b1_strategy \
  --symbol 000001 \
  --start 20200101 \
  --end 20231231 \
  --cash 100000
```

### Parameterized Backtest (中国平安, 2021-2023, Custom Parameters)
```bash
python backtest/run_backtest.py \
  --strategy b1_strategy \
  --symbol 000001 \
  --start 20210101 \
  --end 20231231 \
  --cash 200000 \
  --params short_ma=15,long_ma=50,j_threshold=3,amp_ratio=0.4
```

### Multiple Stocks Backtest
```bash
python backtest/run_backtest.py \
  --strategy b1_strategy \
  --symbol 000001,000858,600519 \
  --start 20200101 \
  --end 20231231 \
  --cash 100000
```

### Backtest with Market Timing (Shanghai Composite)
```bash
python backtest/run_backtest.py \
  --strategy b1_strategy \
  --symbol 000001 \
  --index 000001 \
  --start 20200101 \
  --end 20231231 \
  --cash 100000
```

---

## Expected Performance Metrics

### Historical Performance (Typical)

| Metric | Expected Range | Notes |
|--------|-----------------|-------|
| Annual Return | 15-40% | Depends on market conditions and parameter tuning |
| Win Rate | 40-55% | Fewer trades, higher quality entries |
| Profit Factor | 1.5-3.0 | Profit/Loss ratio |
| Max Drawdown | 15-30% | Typical for swing trading strategies |
| Sharpe Ratio | 0.8-1.5 | Risk-adjusted return |
| Trades/Year | 5-20 | Low frequency by design |
| Avg Hold Days | 5-10 | Typical holding period |

### Performance Factors

**Favorable Conditions:**
- Strong uptrend market (2020-2021, 2023 recovery)
- Mid-cap stocks with good liquidity
- Consistent market timing signals

**Unfavorable Conditions:**
- Prolonged downtrends (2022)
- Choppy consolidation markets (repeated whipsaws)
- Illiquid or highly volatile stocks

---

## Implementation Notes

### Quantifiable vs. Manual Judgment

| Component | Quantifiable | Parameters Required |
|-----------|--------------|---------------------|
| Market timing (120-day MA) | ✅ 100% | MA period |
| Short MA > Long MA | ✅ 100% | Short/long periods |
| 60-day volatility ≤ 100% | ✅ 100% | Calculation window |
| BBI consecutive rise | ✅ 100% | BBI periods, up days |
| KDJ J near 0 | ✅ 100% | J threshold |
| Daily change < 2% | ✅ 100% | Threshold |
| Small amplitude | ⚠️ 80% | Amplitude ratio |
| Low volume | ⚠️ 80% | Volume ratio |
| Trailing stop (MA crossover) | ✅ 100% | MA periods |
| Hard stop (entry low) | ✅ 100% | None |

**Conclusion:** ~80% of the strategy is fully quantifiable; the remaining 20% requires parameter definition for "small amplitude" and "low volume" thresholds.

### Code Structure

The B1 Strategy is implemented in `strategies/b1_strategy.py`:

- **Initialization (`__init__`):** Calculate all indicators (MAs, BBI, KDJ, volatility, amplitude, volume)
- **Main Loop (`next`):** Check market timing, evaluate 7 buy conditions, manage exits
- **Entry:** Buy when all 7 conditions are met; record entry price and low for stop loss
- **Exit:** Trailing stop (MA crossover) or hard stop (below entry low)

### Risk Management

1. **Position Sizing:** Use 95% of available cash per trade (adjustable)
2. **Hard Stop Loss:** Always set at entry day's low; no exceptions
3. **Trailing Stop:** Use MA crossover for trend-following exit
4. **Market Timing:** Exit all positions if market timing MA turns down
5. **Volatility Filter:** Avoid stocks with > 100% volatility in past 60 days

---

## Strengths & Weaknesses

### ✅ Strengths

- **Clear, executable 7-step process:** Each condition is quantifiable
- **High-quality entry signals:** Multi-condition filter reduces false signals
- **Trend-following discipline:** Combines trend-following with pullback entry
- **Low maintenance:** Suitable for office workers; check once at market close
- **Defined risk:** Hard stop loss at entry day's low

### ❌ Weaknesses

- **Infrequent signals:** B1 buy points may not appear for weeks
- **Whipsaw risk:** Choppy consolidation markets cause repeated stop losses
- **Parameter sensitivity:** Too many parameters increase overfitting risk
- **No fixed profit target:** Relies on MA crossover; can give back gains
- **Market timing dependency:** Requires accurate market timing signals

---

## Trading Discipline

> ⚠️ **Important:** The B1 Strategy is a **trend-following variant**, not a holy grail. It performs well in trending markets but suffers in choppy consolidations. Like all technical strategies, **position sizing and discipline matter more than the entry signal itself.**

### Key Principles

1. **Never skip the market timing check:** If Shanghai Composite 120-day MA is down, do not trade
2. **All 7 conditions must be met:** No exceptions; no "close enough" entries
3. **Hard stop loss is mandatory:** No holding through support breaks
4. **Let profits run:** Use MA crossover for exit, not fixed targets
5. **Avoid parameter optimization:** Use defaults for 3-5 years before tuning

---

## Comparison with Other Strategies

| Strategy | Entry | Exit | Holding | Frequency |
|----------|-------|------|---------|-----------|
| B1 (少妇战法) | 7 conditions + oversold | MA crossover | 3-10 days | Low |
| Swing MA+Bollinger | MA + Bollinger bands | Bollinger exit | 5-15 days | Medium |
| Bollinger Reversal | Bollinger extremes | Bollinger exit | 1-5 days | High |

---

## References

- **Original Strategy:** B站 UP 主 zettaranc (Z哥) 的少妇战法
- **Core Concept:** Trend-following + oversold pullback entry
- **Indicators:** SMA, BBI, KDJ, Volatility, Volume
- **Market Timing:** Shanghai Composite 120-day MA

---

## Backtest Results Template

When running backtests, track these metrics:

```
Strategy: B1 Strategy (少妇战法)
Symbol: [STOCK_CODE]
Period: [START_DATE] - [END_DATE]
Initial Cash: [AMOUNT]

Results:
- Total Return: [%]
- Annual Return: [%]
- Win Rate: [%]
- Profit Factor: [RATIO]
- Max Drawdown: [%]
- Sharpe Ratio: [VALUE]
- Total Trades: [COUNT]
- Avg Hold Days: [DAYS]

Parameters Used:
- index_ma: [VALUE]
- short_ma: [VALUE]
- long_ma: [VALUE]
- j_threshold: [VALUE]
- amp_ratio: [VALUE]
- vol_ratio: [VALUE]
```

---

**Last Updated:** 2026-05-31
**Strategy Version:** 1.0
**Implementation:** Backtrader + AkShare
