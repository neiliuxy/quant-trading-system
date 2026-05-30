# Market Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a market-wide filter (Shanghai Composite trend + sentiment + volume) that produces a 0–1 score used to adjust position sizing in SwingStrategy.

**Architecture:** New `market/` package with `MarketConfig` dataclass, three pure indicator functions in `indicators.py`, and `get_market_score()` in `market_analyzer.py` handling data fetching, caching with config fingerprint, forward-fill, and weighted score synthesis. `SwingStrategy` gains optional `market_score_dict` and `risk_percent` params. `run_backtest.py` calls `get_market_score()` before running Cerebro and passes the score dict to the strategy.

**Tech Stack:** Python 3, pandas, numpy, akshare, backtrader, pytest

---

### Task 1: Create `market/__init__.py`

**Files:**
- Create: `market/__init__.py`

- [ ] **Step 1: Create the init file**

```python
# market/__init__.py
from market.market_analyzer import MarketConfig, get_market_score
```

- [ ] **Step 2: Commit**

```bash
git add market/__init__.py
git commit -m "feat: create market package init"
```

---

### Task 2: Create `MarketConfig` dataclass in `market/market_analyzer.py`

**Files:**
- Create: `market/market_analyzer.py`

- [ ] **Step 1: Write MarketConfig**

```python
# market/market_analyzer.py
import hashlib
import json
import os
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'data')


@dataclass
class MarketConfig:
    # ── trend ──
    trend_weight: float = 0.50
    trend_ma_fast: int = 20
    trend_ma_slow: int = 60
    trend_direction_lookback: int = 5
    trend_flat_threshold: float = 0.003

    # ── sentiment ──
    sentiment_weight: float = 0.30
    sentiment_lookback_years: int = 3
    sentiment_short_term_window: int = 20

    # ── volume ──
    volume_weight: float = 0.20
    volume_lookback_years: int = 3
    volume_trapezoid_low: float = 0.20
    volume_trapezoid_rise: float = 0.40
    volume_trapezoid_peak: float = 0.80
    volume_trapezoid_fall: float = 0.90
    volume_trapezoid_low_score: float = 0.2
    volume_trapezoid_high_score: float = 0.2

    @property
    def max_lookback_years(self) -> int:
        return max(self.sentiment_lookback_years, self.volume_lookback_years)

    def hash(self) -> str:
        """SHA256 前 8 位, 用于缓存文件名."""
        data = json.dumps({
            'tw': self.trend_weight,
            'tmaf': self.trend_ma_fast,
            'tmas': self.trend_ma_slow,
            'tdl': self.trend_direction_lookback,
            'tft': self.trend_flat_threshold,
            'sw': self.sentiment_weight,
            'sly': self.sentiment_lookback_years,
            'sstw': self.sentiment_short_term_window,
            'vw': self.volume_weight,
            'vly': self.volume_lookback_years,
            'vtl': self.volume_trapezoid_low,
            'vtr': self.volume_trapezoid_rise,
            'vtp': self.volume_trapezoid_peak,
            'vtf': self.volume_trapezoid_fall,
            'vtls': self.volume_trapezoid_low_score,
            'vths': self.volume_trapezoid_high_score,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:8]
```

- [ ] **Step 2: Verify it imports**

```bash
python -c "import sys; sys.path.insert(0,'.'); from market.market_analyzer import MarketConfig; c = MarketConfig(); print(c.hash())"
```
Expected: prints an 8-char hex string.

- [ ] **Step 3: Commit**

```bash
git add market/market_analyzer.py
git commit -m "feat: add MarketConfig dataclass with param hash"
```

---

### Task 3: Create `market/indicators.py` — trend, sentiment, volume scoring functions

**Files:**
- Create: `market/indicators.py`

- [ ] **Step 1: Write the rolling percentile helper and three scoring functions**

```python
# market/indicators.py
import numpy as np
import pandas as pd


def _rolling_percentile(series: pd.Series, lookback_years: int) -> pd.Series:
    """计算每个点在过去 lookback_years 窗口内的分位 (0.0~1.0)。"""
    window = int(lookback_years * 252)
    result = pd.Series(np.nan, index=series.index)
    for i in range(len(series)):
        if i < 1:
            result.iloc[i] = 0.5
            continue
        start = max(0, i - window + 1)
        window_data = series.iloc[start:i + 1]
        result.iloc[i] = (window_data < series.iloc[i]).sum() / len(window_data)
    return result.fillna(0.5).clip(0.0, 1.0)


def calc_trend_score(df_index: pd.DataFrame, config) -> pd.Series:
    """
    A 维度 — 上证趋势评分 (0 / 0.25 / 0.5 / 0.75 / 1.0).

    df_index 需含 close 列, index 为连续交易日。
    """
    close = df_index['close']
    ma_fast = close.rolling(config.trend_ma_fast).mean()
    ma_slow = close.rolling(config.trend_ma_slow).mean()
    ma_slow_prev = ma_slow.shift(config.trend_direction_lookback)

    ma60_change = (ma_slow - ma_slow_prev) / ma_slow_prev.abs()
    ma60_up = ma60_change > config.trend_flat_threshold
    ma60_down = ma60_change < -config.trend_flat_threshold

    scores = pd.Series(0.5, index=df_index.index)

    # 多头: MA60↑ + MA20>MA60 + price>MA20
    bull = ma60_up & (ma_fast > ma_slow) & (close > ma_fast)
    scores[bull] = 1.00

    # 偏多: MA60↑ + MA20>MA60, 但 price <= MA20
    mild_bull = ma60_up & (ma_fast > ma_slow) & ~bull
    scores[mild_bull] = 0.75

    # 偏空: MA60↓ + MA20<MA60, 但 price >= MA20
    mild_bear = ma60_down & (ma_fast < ma_slow) & (close >= ma_fast)
    scores[mild_bear] = 0.25

    # 空头: MA60↓ + MA20<MA60 + price<MA20
    bear = ma60_down & (ma_fast < ma_slow) & (close < ma_fast)
    scores[bear] = 0.00

    return scores.fillna(0.5).clip(0.0, 1.0)


def calc_sentiment_score(df_index: pd.DataFrame, config) -> pd.Series:
    """
    B 维度 — 情绪评分 (0~1)。

    两子指标等权: (1) 日内强度 (2) 短期涨跌惯性
    均取滚动分位后等权合成。
    """
    close = df_index['close']
    open_ = df_index['open']
    high = df_index['high']
    low = df_index['low']

    # 日内强度: (close - open) / (high - low)
    price_range = high - low
    price_range = price_range.replace(0, np.nan)
    intraday = ((close - open_) / price_range).fillna(0.5)

    # 短期涨跌惯性: 过去 N 日上涨占比
    up_days = (close > close.shift(1)).astype(float)
    bias = up_days.rolling(config.sentiment_short_term_window).mean()

    intraday_pct = _rolling_percentile(intraday, config.sentiment_lookback_years)
    bias_pct = _rolling_percentile(bias, config.sentiment_lookback_years)

    return ((intraday_pct + bias_pct) / 2.0).clip(0.0, 1.0)


def calc_volume_score(df_sh: pd.DataFrame, df_sz: pd.DataFrame, config) -> pd.Series:
    """
    C 维度 — 量能评分 (0~1)。

    df_sh, df_sz 均需含 amount 列, index 对齐。
    两市成交额合计 → 滚动分位 → 梯形映射。
    """
    total_amount = df_sh['amount'] + df_sz['amount']
    pct = _rolling_percentile(total_amount, config.volume_lookback_years)

    low = config.volume_trapezoid_low
    rise = config.volume_trapezoid_rise
    peak = config.volume_trapezoid_peak
    fall = config.volume_trapezoid_fall

    score = pd.Series(0.5, index=pct.index)

    # 活跃区 40%-80% → 1.0
    score[(pct >= rise) & (pct <= peak)] = 1.0

    # 上升段 20%-40% → 0.5→1.0 线性
    mask = (pct >= low) & (pct < rise)
    score[mask] = 0.5 + 0.5 * (pct[mask] - low) / (rise - low)

    # 过热段 80%-90% → 1.0→0.4 线性
    mask = (pct > peak) & (pct <= fall)
    score[mask] = 1.0 - 0.6 * (pct[mask] - peak) / (fall - peak)

    # 尾部分
    score[pct < low] = config.volume_trapezoid_low_score
    score[pct > fall] = config.volume_trapezoid_high_score

    return score.fillna(0.5).clip(0.0, 1.0)
```

- [ ] **Step 2: Verify import**

```bash
python -c "
import sys; sys.path.insert(0,'.')
from market.indicators import calc_trend_score, calc_sentiment_score, calc_volume_score, _rolling_percentile
print('indicators imported OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add market/indicators.py
git commit -m "feat: add trend, sentiment, volume indicator functions"
```

---

### Task 4: Add data fetching + cache + `get_market_score()` to `market/market_analyzer.py`

**Files:**
- Modify: `market/market_analyzer.py` (append below Task 2 content)

- [ ] **Step 1: Append data fetching functions to market_analyzer.py**

Add after the `MarketConfig` class:

```python


def _shift_years(date_val, years):
    """按年份平移日期, 处理 2 月 29 日。"""
    try:
        return date_val.replace(year=date_val.year + years)
    except ValueError:
        return date_val.replace(year=date_val.year + years, day=28)


def _fetch_index_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    通过 AkShare 获取指数日线, 带降级。

    Args:
        symbol: 'sh000001' 或 'sz399001'
        start:  YYYYMMDD
        end:    YYYYMMDD

    Returns:
        DataFrame with columns date, open, close, high, low, volume, amount
        date 列为 datetime64。

    Raises:
        RuntimeError: 所有数据源均失败。
    """
    import akshare as ak

    last_err = None

    # 主源: 东方财富
    for attempt in range(1, 4):
        try:
            df = ak.stock_zh_index_daily_em(
                symbol=symbol, start_date=start, end_date=end
            )
            df['date'] = pd.to_datetime(df['date'])
            return df[['date', 'open', 'close', 'high', 'low', 'volume', 'amount']].copy()
        except Exception as e:
            last_err = e
            if attempt < 3:
                time.sleep(2)

    # 备用: 腾讯
    for attempt in range(1, 3):
        try:
            df = ak.stock_zh_index_daily_tx(
                symbol=symbol, start_date=start, end_date=end
            )
            df['date'] = pd.to_datetime(df['date'])
            return df[['date', 'open', 'close', 'high', 'low', 'volume', 'amount']].copy()
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(1)

    raise RuntimeError(f'无法获取 {symbol} 的指数数据') from last_err
```

- [ ] **Step 2: Append cache logic to market_analyzer.py**

Add after the fetch function:

```python


def _cache_path(start: str, end: str, config: MarketConfig) -> str:
    """缓存文件完整路径。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    fname = f'market_score_{start}_{end}_{config.hash()}.csv'
    return os.path.join(DATA_DIR, fname)


def _read_cache(start: str, end: str, config: MarketConfig) -> pd.DataFrame | None:
    """读取缓存，校验 config 指纹。不一致返回 None。"""
    path = _cache_path(start, end, config)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        # 校验 JSON metadata 行 — 第一条注释即 metadata
        if not df.columns.tolist() == ['date', 'trend_score', 'sentiment_score', 'volume_score', 'total_score']:
            return None
        return df
    except Exception:
        return None


def _write_cache(df: pd.DataFrame, start: str, end: str, config: MarketConfig):
    """写入缓存, date 列存为 YYYYMMDD 字符串。"""
    path = _cache_path(start, end, config)
    out = df.copy()
    out['date'] = out['date'].dt.strftime('%Y%m%d')
    out.to_csv(path, index=False)
```

- [ ] **Step 3: Append forward fill and main function**

Add after cache logic:

```python


def _forward_fill(df: pd.DataFrame, start_dt, end_dt) -> pd.DataFrame:
    """
    按交易日历前向填充。

    Args:
        df: 含 date(datetime64) 和评分列
        start_dt: 回测起始 datetime
        end_dt:   回测结束 datetime

    Returns:
        从 start_dt 到 end_dt 的完整 DataFrame,
        缺失日向前填充 (max gap 5), 超窗口填 0.5。
    """
    df = df.set_index('date').sort_index()
    # 生成完整交易日历 (工作日)
    full_idx = pd.date_range(start_dt, end_dt, freq='B')
    df = df.reindex(full_idx)

    # 前向填充, limit=5
    score_cols = ['trend_score', 'sentiment_score', 'volume_score', 'total_score']
    df[score_cols] = df[score_cols].ffill(limit=5)

    # 仍未填充的 → 0.5
    df[score_cols] = df[score_cols].fillna(0.5)

    df.index.name = 'date'
    return df.reset_index()


def get_market_score(
    start: str,
    end: str,
    config: MarketConfig = None,
) -> pd.DataFrame:
    """
    获取市场评分 DataFrame。

    实际拉取区间为 start - max_lookback_years 到 end,
    计算完成后裁剪输出 start~end。

    Args:
        start:  回测起始, YYYYMMDD
        end:    回测结束, YYYYMMDD
        config: 参数配置, None 用默认值

    Returns:
        date | trend_score | sentiment_score | volume_score | total_score
        已前向填充, date 为 datetime64 列。
    """
    if config is None:
        config = MarketConfig()

    start_dt = pd.to_datetime(start, format='%Y%m%d')
    end_dt = pd.to_datetime(end, format='%Y%m%d')
    fetch_start = _shift_years(start_dt, -config.max_lookback_years)
    fetch_start_str = fetch_start.strftime('%Y%m%d')

    # 1. 读缓存
    cached = _read_cache(start, end, config)
    if cached is not None:
        print(f'从缓存读取市场评分: {os.path.basename(_cache_path(start, end, config))}')
        cached['date'] = pd.to_datetime(cached['date'], format='%Y%m%d')
        return cached

    # 2. 拉取数据
    from market.indicators import calc_trend_score, calc_sentiment_score, calc_volume_score

    print(f'正在拉取市场数据 ({fetch_start_str} ~ {end})...')

    df_sh = _fetch_index_data('sh000001', fetch_start_str, end)
    df_sz = _fetch_index_data('sz399001', fetch_start_str, end)

    # 对齐两市日期
    common_idx = df_sh.set_index('date').index.intersection(
        df_sz.set_index('date').index
    )
    df_sh = df_sh.set_index('date').loc[common_idx].reset_index()
    df_sz = df_sz.set_index('date').loc[common_idx].reset_index()

    # 3. 计算子分
    trend = calc_trend_score(df_sh, config)
    sentiment = calc_sentiment_score(df_sh, config)
    volume = calc_volume_score(df_sh, df_sz, config)

    total = (
        trend * config.trend_weight
        + sentiment * config.sentiment_weight
        + volume * config.volume_weight
    )

    result = pd.DataFrame({
        'date': df_sh['date'],
        'trend_score': trend.values,
        'sentiment_score': sentiment.values,
        'volume_score': volume.values,
        'total_score': total.values.clip(0.0, 1.0),
    })

    # 4. 裁剪 + 前向填充
    result = result[(result['date'] >= start_dt) & (result['date'] <= end_dt)]
    result = result.copy()
    result = _forward_fill(result, start_dt, end_dt)

    # 5. 写缓存
    _write_cache(result, start, end, config)

    return result
```

- [ ] **Step 4: Verify import and basic structure**

```bash
python -c "
import sys; sys.path.insert(0,'.')
from market.market_analyzer import MarketConfig, get_market_score
print('market_analyzer imports OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add market/market_analyzer.py
git commit -m "feat: add data fetching, cache with config fingerprint, and get_market_score"
```

---

### Task 5: Write tests for `indicators.py`

**Files:**
- Create: `tests/test_indicators.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_indicators.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pytest
from market.indicators import (
    _rolling_percentile,
    calc_trend_score,
    calc_sentiment_score,
    calc_volume_score,
)
from market.market_analyzer import MarketConfig


def make_ohlc_df(prices, start_date='2020-01-01'):
    """Helper: 从收盘价列表创建模拟 OHLC DataFrame。"""
    dates = pd.date_range(start_date, periods=len(prices), freq='B')
    return pd.DataFrame({
        'date': dates,
        'open': [p * 0.99 for p in prices],
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
    })


def make_ohlc_amt_df(prices, amounts):
    """Helper: OHLC + amount。"""
    dates = pd.date_range('2020-01-01', periods=len(prices), freq='B')
    return pd.DataFrame({
        'date': dates,
        'open': [p * 0.99 for p in prices],
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'amount': amounts,
    })


class TestRollingPercentile:
    def test_constant_series_gives_mid(self):
        s = pd.Series([10.0] * 100)
        result = _rolling_percentile(s, lookback_years=1)
        # Every value is equal, so pct should be ~0.5 for all after the first window
        assert 0.45 < result.iloc[-1] < 0.55

    def test_increasing_series_gives_high(self):
        s = pd.Series(np.linspace(1, 100, 500))
        result = _rolling_percentile(s, lookback_years=1)
        assert result.iloc[-1] > 0.90  # last value is highest ever seen

    def test_decreasing_series_gives_low(self):
        s = pd.Series(np.linspace(100, 1, 500))
        result = _rolling_percentile(s, lookback_years=1)
        assert result.iloc[-1] < 0.10  # last value is lowest ever seen

    def test_output_in_range(self):
        s = pd.Series(np.random.randn(200).cumsum() + 100)
        result = _rolling_percentile(s, lookback_years=1)
        assert result.min() >= 0.0
        assert result.max() <= 1.0
        assert not result.isna().any()


class TestTrendScore:
    def test_bull_trend(self, config):
        """持续上涨 + MA60 向上 + MA20>MA60 + price>MA20 → 1.0"""
        n = 200
        prices = [100 + i * 0.5 for i in range(n)]  # steady uptrend
        df = make_ohlc_df(prices)

        scores = calc_trend_score(df, config)
        # After warmup, should be 1.0
        assert scores.iloc[-1] == 1.0
        assert scores.iloc[130] == 1.0

    def test_bear_trend(self, config):
        """持续下跌 + MA60 向下 + MA20<MA60 + price<MA20 → 0.0"""
        n = 200
        prices = [100 - i * 0.3 for i in range(n)]
        df = make_ohlc_df(prices)

        scores = calc_trend_score(df, config)
        assert scores.iloc[-1] == 0.0

    def test_range_bound_is_neutral(self, config):
        """横盘震荡 → 0.5"""
        n = 200
        prices = [100 + np.sin(i / 20) * 2 for i in range(n)]
        df = make_ohlc_df(prices)

        scores = calc_trend_score(df, config)
        # Most scores should be 0.5 in range-bound market
        assert scores.iloc[-50:].mean() == pytest.approx(0.5, abs=0.25)

    def test_warmup_period_is_0_5(self, config):
        """均线未就绪时 fill 0.5"""
        n = 100
        prices = [100] * n
        df = make_ohlc_df(prices)

        scores = calc_trend_score(df, config)
        # NaN filled with 0.5
        assert scores.iloc[0] == 0.5
        assert not scores.isna().any()

    @pytest.fixture
    def config(self):
        return MarketConfig()


class TestSentimentScore:
    def test_output_range(self, config):
        n = 300
        prices = [100 + i * 0.2 + np.random.randn() * 2 for i in range(n)]
        df = make_ohlc_df(prices)

        scores = calc_sentiment_score(df, config)
        assert scores.min() >= 0.0
        assert scores.max() <= 1.0
        assert not scores.isna().any()

    def test_high_intraday_strength(self, config):
        """高开高走给出高日内强度"""
        n = 300
        dates = pd.date_range('2020-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates,
            'open': [100.0] * n,
            'high': [110.0] * n,
            'low': [98.0] * n,
            'close': [109.0] * n,  # close near high
        })
        scores = calc_sentiment_score(df, config)
        # skip warmup, check late period
        assert scores.iloc[-100:].mean() > 0.5

    @pytest.fixture
    def config(self):
        return MarketConfig()


class TestVolumeScore:
    def test_output_range(self, config):
        n = 300
        df_sh = make_ohlc_amt_df(
            [100] * n,
            [1e11 + i * 1e9 + np.random.randn() * 5e9 for i in range(n)]
        )
        df_sz = make_ohlc_amt_df(
            [100] * n,
            [8e10 + i * 8e8 + np.random.randn() * 3e9 for i in range(n)]
        )

        scores = calc_volume_score(df_sh, df_sz, config)
        assert scores.min() >= 0.0
        assert scores.max() <= 1.0
        assert not scores.isna().any()

    def test_rising_volume_through_peak(self, config):
        """成交量从地量单调增至天量, 分数应先升后降。"""
        n = 500
        amounts = np.linspace(5e10, 5e11, n)  # ramp up
        df_sh = make_ohlc_amt_df([100] * n, amounts)
        df_sz = make_ohlc_amt_df([100] * n, amounts * 0.7)

        scores = calc_volume_score(df_sh, df_sz, config)
        # 中间位置 (40-80% 分位) 分数应接近 1.0
        mid_start = int(n * 0.45)
        mid_end = int(n * 0.75)
        assert scores.iloc[mid_start:mid_end].mean() > 0.8

    @pytest.fixture
    def config(self):
        return MarketConfig()
```

- [ ] **Step 2: Run the tests**

```bash
python -m pytest tests/test_indicators.py -v
```

Expected: 10+ tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_indicators.py
git commit -m "test: add indicator function tests"
```

---

### Task 6: Write tests for `market_analyzer.py`

**Files:**
- Create: `tests/test_market_analyzer.py`

- [ ] **Step 1: Write tests for MarketConfig + cache path**

```python
# tests/test_market_analyzer.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest
from market.market_analyzer import (
    MarketConfig,
    _cache_path,
    _read_cache,
    _write_cache,
    _forward_fill,
    _shift_years,
)
from datetime import datetime


class TestMarketConfig:
    def test_default_hash_is_stable(self):
        c1 = MarketConfig()
        c2 = MarketConfig()
        assert c1.hash() == c2.hash()

    def test_different_params_different_hash(self):
        c1 = MarketConfig(trend_weight=0.5)
        c2 = MarketConfig(trend_weight=0.6)
        assert c1.hash() != c2.hash()

    def test_max_lookback_years(self):
        c = MarketConfig(sentiment_lookback_years=3, volume_lookback_years=5)
        assert c.max_lookback_years == 5

    def test_config_fields_are_default_values(self):
        c = MarketConfig()
        assert c.trend_ma_fast == 20
        assert c.trend_ma_slow == 60
        assert c.sentiment_weight == 0.30
        assert c.volume_weight == 0.20
        # weights sum check
        assert abs(c.trend_weight + c.sentiment_weight + c.volume_weight - 1.0) < 0.001


class TestCache:
    def test_cache_path_contains_hash(self, tmp_path):
        import market.market_analyzer as ma
        orig_data_dir = ma.DATA_DIR
        ma.DATA_DIR = str(tmp_path)
        try:
            config = MarketConfig()
            path = _cache_path('20200101', '20231231', config)
            assert config.hash() in path
            assert path.startswith(str(tmp_path))
        finally:
            ma.DATA_DIR = orig_data_dir

    def test_write_and_read_cache(self, tmp_path):
        import market.market_analyzer as ma
        orig_data_dir = ma.DATA_DIR
        ma.DATA_DIR = str(tmp_path)
        try:
            config = MarketConfig()
            df = pd.DataFrame({
                'date': pd.to_datetime(['2020-01-02', '2020-01-03']),
                'trend_score': [0.75, 0.5],
                'sentiment_score': [0.6, 0.7],
                'volume_score': [0.8, 0.8],
                'total_score': [0.71, 0.63],
            })
            _write_cache(df, '20200101', '20201231', config)

            cached = _read_cache('20200101', '20201231', config)
            assert cached is not None
            assert len(cached) == 2
            assert cached['trend_score'].iloc[0] == 0.75
        finally:
            ma.DATA_DIR = orig_data_dir

    def test_read_missing_cache_returns_none(self, tmp_path):
        import market.market_analyzer as ma
        orig_data_dir = ma.DATA_DIR
        ma.DATA_DIR = str(tmp_path)
        try:
            config = MarketConfig()
            assert _read_cache('19990101', '19991231', config) is None
        finally:
            ma.DATA_DIR = orig_data_dir


class TestForwardFill:
    def test_fills_gaps_within_5_days(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-02', '2020-01-06']),  # gap of 2 trading days
            'trend_score': [0.8, 0.6],
            'sentiment_score': [0.7, 0.5],
            'volume_score': [0.9, 0.8],
            'total_score': [0.79, 0.59],
        })
        start = pd.to_datetime('2020-01-02')
        end = pd.to_datetime('2020-01-06')
        result = _forward_fill(df, start, end)
        # Should have 3 rows: Jan 2, Jan 3, Jan 6
        assert len(result) >= 2  # at minimum
        assert result['total_score'].iloc[-1] == 0.59

    def test_large_gap_fills_neutral(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-02']),
            'trend_score': [0.8],
            'sentiment_score': [0.7],
            'volume_score': [0.9],
            'total_score': [0.79],
        })
        start = pd.to_datetime('2020-01-02')
        end = pd.to_datetime('2020-01-20')  # large gap
        result = _forward_fill(df, start, end)
        # Check that dates after the 5-day fill window are neutral
        later_rows = result[result['date'] >= pd.to_datetime('2020-01-13')]
        assert (later_rows['total_score'] == 0.5).all()


class TestShiftYears:
    def test_normal_year_shift(self):
        d = datetime(2020, 6, 15)
        result = _shift_years(d, -3)
        assert result == datetime(2017, 6, 15)

    def test_leap_year_feb29_shift(self):
        d = datetime(2020, 2, 29)
        result = _shift_years(d, -3)
        assert result == datetime(2017, 2, 28)
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_market_analyzer.py -v
```

Expected: all tests pass (cache read/write, config hash, forward fill, shift years).

- [ ] **Step 3: Commit**

```bash
git add tests/test_market_analyzer.py
git commit -m "test: add MarketConfig, cache, and forward_fill tests"
```

---

### Task 7: Modify `SwingStrategy` to support market filter

**Files:**
- Modify: `strategies/swing_ma_boll.py`

- [ ] **Step 1: Read the current file to see exact content**

Read `strategies/swing_ma_boll.py` — already done. The file is at revision 2147 bytes.

- [ ] **Step 2: Apply modifications**

The existing file:

```python
"""
双均线 + 布林带波段策略
...
"""

import akshare as ak
import backtrader as bt


class SwingStrategy(bt.Strategy):
    params = (
        ('fast_ma', 10),
        ('slow_ma', 20),
    )

    def __init__(self):
        self.ma_fast = bt.ind.SMA(period=self.p.fast_ma)
        self.ma_slow = bt.ind.SMA(period=self.p.slow_ma)
        self.boll = bt.ind.BollingerBands(period=20, devfactor=2)
        self.signal = 0  # 0=空仓, 1=持仓

    def next(self):
        # 买入条件：MA10上穿MA20 + 价格在布林中轨之上
        if self.ma_fast > self.ma_slow and self.data.close > self.boll.lines.mid:
            if self.signal != 1:
                self.buy()
                self.signal = 1

        # 卖出条件：MA10下穿MA20 或 跌破布林下轨
        elif (self.ma_fast < self.ma_slow or
              self.data.close < self.boll.lines.bot):
            if self.signal != 0:
                self.sell()
                self.signal = 0
```

Replace with:

```python
"""
双均线 + 布林带波段策略
- 快速均线：MA10
- 慢速均线：MA20
- 布林带：20日周期，2倍标准差
- 买入：MA10 上穿 MA20 + 价格在布林中轨之上
- 卖出：MA10 下穿 MA20 或 跌破布林下轨
- 支持可选的 market_score_dict 调节仓位大小
"""

import backtrader as bt


class SwingStrategy(bt.Strategy):
    params = (
        ('fast_ma', 10),
        ('slow_ma', 20),
        ('risk_percent', 0.95),          # 基础仓位比例
        ('market_score_dict', None),      # None=无过滤, dict={YYYYMMDD: score}
    )

    def __init__(self):
        self.ma_fast = bt.ind.SMA(period=self.p.fast_ma)
        self.ma_slow = bt.ind.SMA(period=self.p.slow_ma)
        self.boll = bt.ind.BollingerBands(period=20, devfactor=2)
        self.signal = 0

    def next(self):
        current_date = self.datas[0].datetime.date(0).strftime('%Y%m%d')

        # 买入条件：MA10上穿MA20 + 价格在布林中轨之上
        if self.ma_fast[0] > self.ma_slow[0] and self.data.close[0] > self.boll.lines.mid[0]:
            if self.signal != 1:
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

        # 卖出条件：MA10下穿MA20 或 跌破布林下轨
        elif (self.ma_fast[0] < self.ma_slow[0] or
              self.data.close[0] < self.boll.lines.bot[0]):
            if self.signal != 0:
                self.sell()
                self.signal = 0
```

Note changes from original:
1. Removed `import akshare as ak` (no longer used by strategy; data loading is in run_backtest.py)
2. Added `risk_percent` and `market_score_dict` params
3. In `next()`: `self.ma_fast[0]` / `self.data.close[0]` (explicit index for clarity, Backtrader accepts both)
4. Buy branch: look up market score, compute cash-adjusted size, skip if size=0
5. `self.signal` set to 1 even when score=0 (avoids re-entering buy branch every bar when market is bad)
6. Sell branch: added `[0]` index for consistency

- [ ] **Step 3: Verify the strategy still imports**

```bash
python -c "from strategies.swing_ma_boll import SwingStrategy; print('SwingStrategy imported OK')"
```

- [ ] **Step 4: Commit**

```bash
git add strategies/swing_ma_boll.py
git commit -m "feat: add market_score_dict and risk_percent to SwingStrategy"
```

---

### Task 8: Modify `run_backtest.py` to integrate market filter

**Files:**
- Modify: `backtest/run_backtest.py`

- [ ] **Step 1: Read current file**

The existing `run_backtest.py` (79 lines). Key sections:

```python
def run(symbol='000001', start=None, end=None, cash=100000):
    start, end = resolve_date_range(start, end)
    cerebro = bt.Cerebro()
    ...
    cerebro.addstrategy(SwingStrategy)
    ...
    cerebro.run()
```

- [ ] **Step 2: Apply modifications**

Replace `run()` function and add imports:

Current imports block:
```python
import pandas as pd
import backtrader as bt
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.swing_ma_boll import SwingStrategy
from backtest.data_loader import load_market_data, resolve_date_range
```

Change to:
```python
import pandas as pd
import backtrader as bt
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.swing_ma_boll import SwingStrategy
from backtest.data_loader import load_market_data, resolve_date_range
from market.market_analyzer import MarketConfig, get_market_score


class MarketDataError(RuntimeError):
    """市场数据完全不可用。"""
    pass
```

Replace the `run()` function:

```python
def run(symbol='000001', start=None, end=None, cash=100000, use_market_filter=True):
    """运行回测。

    Args:
        symbol: 股票代码
        start:  开始日期 YYYYMMDD, None 则默认近 3 年
        end:    结束日期 YYYYMMDD, None 则今天
        cash:   初始资金
        use_market_filter: 是否启用市场过滤器
    """
    start, end = resolve_date_range(start, end)
    cerebro = bt.Cerebro()

    # ── 市场评分 ──
    market_score_dict = None
    if use_market_filter:
        config = MarketConfig()
        try:
            score_df = get_market_score(start, end, config)
            market_score_dict = dict(zip(
                score_df['date'].dt.strftime('%Y%m%d'),
                score_df['total_score'],
            ))
            print(f'市场评分范围: {score_df["total_score"].min():.2f} ~ {score_df["total_score"].max():.2f}')
        except Exception as e:
            print(f'市场数据获取失败 ({e}), 降级为无过滤模式')
            market_score_dict = None

    # ── 个股数据 ──
    try:
        df = load_market_data(symbol, start, end)
    except Exception as e:
        print(f'数据获取失败({e})，使用模拟数据演示回测')
        df = generate_synthetic_data()
        df['date'] = pd.to_datetime(df['date'])

    data = bt.feeds.PandasData(dataname=df, datetime=0)
    cerebro.adddata(data)
    cerebro.addstrategy(SwingStrategy, market_score_dict=market_score_dict)
    cerebro.broker.setcash(cash)

    print(f'起始资金: {cerebro.broker.getcash():.2f}')
    cerebro.run()
    final_value = cerebro.broker.getvalue()
    print(f'结束资金: {final_value:.2f}')
    print(f'收益率: {(final_value / cash - 1) * 100:.2f}%')
```

In the `if __name__ == '__main__':` block, add the filter flag:

```python
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='运行量化回测')
    parser.add_argument('--symbol', default='000001', help='股票代码')
    parser.add_argument('--start', default=None, help='开始日期，默认当前日期近3年')
    parser.add_argument('--end', default=None, help='结束日期，默认当前日期')
    parser.add_argument('--cash', type=float, default=100000, help='初始资金')
    parser.add_argument('--no-market-filter', action='store_true', help='禁用市场过滤器')
    args = parser.parse_args()

    run(args.symbol, args.start, args.end, args.cash,
        use_market_filter=not args.no_market_filter)
```

- [ ] **Step 3: Verify script parses correctly**

```bash
python -c "import backtest.run_backtest" 2>&1 | head -5
```

- [ ] **Step 4: Commit**

```bash
git add backtest/run_backtest.py
git commit -m "feat: integrate market filter into run_backtest.py"
```

---

### Task 9: Modify `backtest/stock_selector.py` to share market score

**Files:**
- Modify: `backtest/stock_selector.py`

- [ ] **Step 1: Add market filter to batch backtesting**

In `stock_selector.py`, modify the `main()` function to compute market_score once and share across all symbols.

Current imports:
```python
import pandas as pd
import backtrader as bt
from backtest.data_loader import load_market_data, resolve_date_range
from strategies.swing_ma_boll import SwingStrategy
```

Change to:
```python
import pandas as pd
import backtrader as bt
from backtest.data_loader import load_market_data, resolve_date_range
from strategies.swing_ma_boll import SwingStrategy
from market.market_analyzer import MarketConfig, get_market_score
```

In `run_single_backtest()`, add `market_score_dict` parameter:

```python
def run_single_backtest(symbol, start=None, end=None, cash=100000, market_score_dict=None):
    """运行单只股票回测，返回关键指标"""
    start, end = resolve_date_range(start, end)
    try:
        df = load_market_data(symbol, start, end)
        if len(df) < 60:
            return None

        cerebro = bt.Cerebro()
        data = bt.feeds.PandasData(dataname=df, datetime=0)
        cerebro.adddata(data)
        cerebro.addstrategy(SwingStrategy, market_score_dict=market_score_dict)
        cerebro.broker.setcash(cash)
        ...
```

In `main()`, add market score loading before the batch loop:

```python
def main():
    print('=' * 60)
    print('选股回测工具 - 双均线+布林带策略')
    print('=' * 60)
    start, end = resolve_date_range()
    print(f'默认回测区间: {start} - {end}')

    # ── 市场评分 (共享一份) ──
    market_score_dict = None
    try:
        config = MarketConfig()
        score_df = get_market_score(start, end, config)
        market_score_dict = dict(zip(
            score_df['date'].dt.strftime('%Y%m%d'),
            score_df['total_score'],
        ))
        print(f'市场评分范围: {score_df["total_score"].min():.2f} ~ {score_df["total_score"].max():.2f}')
    except Exception as e:
        print(f'市场数据获取失败 ({e}), 降级为无过滤模式')
    ...
```

Then update the batch loop call:

```python
for i, symbol in enumerate(symbols, 1):
    print(f'[{i:2d}/{len(symbols)}] 回测 {symbol}...', end=' ', flush=True)
    result = run_single_backtest(symbol, start=start, end=end,
                                  market_score_dict=market_score_dict)
    ...
```

- [ ] **Step 2: Commit**

```bash
git add backtest/stock_selector.py
git commit -m "feat: share market score across batch backtests in stock_selector"
```

---

### Task 10: Integration test — run full backtest

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest
from backtest.data_loader import resolve_date_range
from market.market_analyzer import MarketConfig, get_market_score


class TestMarketScoreEndToEnd:
    """端到端: get_market_score 产出可用评分 dict 供策略消费。"""

    @pytest.mark.slow
    def test_get_market_score_returns_valid_dataframe(self):
        config = MarketConfig()
        start, end = resolve_date_range(years=1)  # 只拉 1 年, 快速验证
        df = get_market_score(start, end, config)

        expected_cols = ['date', 'trend_score', 'sentiment_score', 'volume_score', 'total_score']
        assert list(df.columns) == expected_cols
        assert len(df) > 0
        assert df['total_score'].min() >= 0.0
        assert df['total_score'].max() <= 1.0
        # date should be datetime64
        assert pd.api.types.is_datetime64_any_dtype(df['date'])

    @pytest.mark.slow
    def test_cache_hit_on_second_call(self):
        config = MarketConfig()
        start, end = resolve_date_range(years=1)
        df1 = get_market_score(start, end, config)
        df2 = get_market_score(start, end, config)  # should hit cache

        pd.testing.assert_frame_equal(df1, df2)

    @pytest.mark.slow
    def test_score_dict_format(self):
        config = MarketConfig()
        start, end = resolve_date_range(years=1)
        df = get_market_score(start, end, config)

        score_dict = dict(zip(
            df['date'].dt.strftime('%Y%m%d'),
            df['total_score'],
        ))
        # All keys should be 8-char strings
        for k in list(score_dict.keys())[:10]:
            assert len(k) == 8
            assert k.isdigit()

    @pytest.mark.slow
    def test_different_configs_produce_different_scores(self):
        start, end = resolve_date_range(years=1)
        config_a = MarketConfig(trend_weight=0.5, sentiment_weight=0.3, volume_weight=0.2)
        config_b = MarketConfig(trend_weight=0.3, sentiment_weight=0.5, volume_weight=0.2)
        df_a = get_market_score(start, end, config_a)
        df_b = get_market_score(start, end, config_b)

        # At least some days should differ
        diff = (df_a['total_score'] != df_b['total_score']).sum()
        assert diff > 0

    @pytest.mark.slow
    def test_no_nan_in_output(self):
        config = MarketConfig()
        start, end = resolve_date_range(years=1)
        df = get_market_score(start, end, config)

        assert not df.isna().any().any()
```

- [ ] **Step 2: Run integration tests (skips by default for slow)**

```bash
python -m pytest tests/test_integration.py -v -m slow --timeout=120
```

Or run without `-m slow` to skip network tests and only run unit tests:

```bash
python -m pytest tests/ -v --ignore=tests/test_integration.py
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration tests for market score"
```

---

### Task 11: Run final full backtest verification

- [ ] **Step 1: Run backtest WITHOUT market filter (baseline)**

```bash
python backtest/run_backtest.py --symbol 000001 --cash 100000 --no-market-filter
```

Expected: completes, prints 起始资金/结束资金/收益率.

- [ ] **Step 2: Run backtest WITH market filter**

```bash
python backtest/run_backtest.py --symbol 000001 --cash 100000
```

Expected: prints market score range, then completes with results.

- [ ] **Step 3: Verify both modes produce valid output**

Check that the filtered version produces different (likely fewer) trades.

- [ ] **Step 4: Run all unit tests one final time**

```bash
python -m pytest tests/ -v --ignore=tests/test_integration.py
```

Expected: all tests pass.

- [ ] **Step 5: Final commit (if any cleanups needed)**

```bash
git status
```
