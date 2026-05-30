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
        assert 0.45 < result.iloc[-1] < 0.55

    def test_increasing_series_gives_high(self):
        s = pd.Series(np.linspace(1, 100, 500))
        result = _rolling_percentile(s, lookback_years=1)
        assert result.iloc[-1] > 0.90

    def test_decreasing_series_gives_low(self):
        s = pd.Series(np.linspace(100, 1, 500))
        result = _rolling_percentile(s, lookback_years=1)
        assert result.iloc[-1] < 0.10

    def test_output_in_range(self):
        s = pd.Series(np.random.randn(200).cumsum() + 100)
        result = _rolling_percentile(s, lookback_years=1)
        assert result.min() >= 0.0
        assert result.max() <= 1.0
        assert not result.isna().any()


class TestTrendScore:
    @pytest.fixture
    def config(self):
        return MarketConfig()

    def test_bull_trend(self, config):
        """持续上涨 + MA60 向上 + MA20>MA60 + price>MA20 → 1.0"""
        n = 200
        prices = [100 + i * 0.5 for i in range(n)]
        df = make_ohlc_df(prices)

        scores = calc_trend_score(df, config)
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
        assert scores.iloc[-50:].mean() == pytest.approx(0.5, abs=0.25)

    def test_warmup_period_is_0_5(self, config):
        """均线未就绪时 fill 0.5"""
        n = 100
        prices = [100] * n
        df = make_ohlc_df(prices)

        scores = calc_trend_score(df, config)
        assert scores.iloc[0] == 0.5
        assert not scores.isna().any()


class TestSentimentScore:
    @pytest.fixture
    def config(self):
        return MarketConfig()

    def test_output_range(self, config):
        n = 300
        prices = [100 + i * 0.2 + np.random.randn() * 2 for i in range(n)]
        df = make_ohlc_df(prices)

        scores = calc_sentiment_score(df, config)
        assert scores.min() >= 0.0
        assert scores.max() <= 1.0
        assert not scores.isna().any()

    def test_high_intraday_strength(self, config):
        """持续高开高走 + 多数日收涨 → 情绪分偏高"""
        n = 300
        np.random.seed(42)
        # 95% 的日子收涨, 日内强度偏强 (close near high)
        dates = pd.date_range('2020-01-01', periods=n, freq='B')
        highs = [100.0 + i * 0.1 + np.random.rand() * 5 for i in range(n)]
        lows = [h - 2 - np.random.rand() * 3 for h in highs]
        opens = [l + (h - l) * 0.2 for l, h in zip(lows, highs)]
        closes = [l + (h - l) * 0.9 for l, h in zip(lows, highs)]
        df = pd.DataFrame({
            'date': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
        })
        scores = calc_sentiment_score(df, config)
        # 均匀走高走势 + 高日内强度 → 情绪偏强
        assert scores.iloc[-100:].mean() > 0.5


class TestVolumeScore:
    @pytest.fixture
    def config(self):
        return MarketConfig()

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

    def test_volume_score_varies_with_amount(self, config):
        """成交额变化时分数应有波动, 不是固定值。"""
        n = 800
        np.random.seed(42)
        amounts = np.abs(np.random.randn(n).cumsum() * 1e10 + 2e11)
        df_sh = make_ohlc_amt_df([100] * n, amounts)
        df_sz = make_ohlc_amt_df([100] * n, amounts * 0.7)

        scores = calc_volume_score(df_sh, df_sz, config)
        # 分数应在 [0, 1] 且有变化
        assert scores.min() >= 0.0
        assert scores.max() <= 1.0
        assert scores.std() > 0.01  # 非固定值
