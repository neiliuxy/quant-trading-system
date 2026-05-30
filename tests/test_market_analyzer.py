# tests/test_market_analyzer.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest
from datetime import datetime
from market.market_analyzer import (
    MarketConfig,
    _cache_path,
    _read_cache,
    _write_cache,
    _forward_fill,
    _shift_years,
)


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

    def test_different_config_does_not_match(self, tmp_path):
        import market.market_analyzer as ma
        orig_data_dir = ma.DATA_DIR
        ma.DATA_DIR = str(tmp_path)
        try:
            c1 = MarketConfig(trend_weight=0.5)
            c2 = MarketConfig(trend_weight=0.6)
            assert c1.hash() != c2.hash()
            # read with c2 should not find c1's cache
            df = pd.DataFrame({
                'date': pd.to_datetime(['2020-01-02']),
                'trend_score': [0.5],
                'sentiment_score': [0.5],
                'volume_score': [0.5],
                'total_score': [0.5],
            })
            _write_cache(df, '20200101', '20201231', c1)
            assert _read_cache('20200101', '20201231', c2) is None
        finally:
            ma.DATA_DIR = orig_data_dir


class TestForwardFill:
    def test_fills_gaps_within_5_days(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-02', '2020-01-06']),
            'trend_score': [0.8, 0.6],
            'sentiment_score': [0.7, 0.5],
            'volume_score': [0.9, 0.8],
            'total_score': [0.79, 0.59],
        })
        start = pd.to_datetime('2020-01-02')
        end = pd.to_datetime('2020-01-06')
        result = _forward_fill(df, start, end)
        # Jan 6 row should still have its own score
        last_row = result[result['date'] == pd.to_datetime('2020-01-06')]
        assert last_row['total_score'].iloc[0] == 0.59

    def test_large_gap_fills_neutral(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-02']),
            'trend_score': [0.8],
            'sentiment_score': [0.7],
            'volume_score': [0.9],
            'total_score': [0.79],
        })
        start = pd.to_datetime('2020-01-02')
        end = pd.to_datetime('2020-01-20')
        result = _forward_fill(df, start, end)
        later_rows = result[result['date'] >= pd.to_datetime('2020-01-13')]
        assert (later_rows['total_score'] == 0.5).all()

    def test_no_gap_unchanged(self):
        df = pd.DataFrame({
            'date': pd.to_datetime(['2020-01-02', '2020-01-03', '2020-01-06']),
            'trend_score': [0.8, 0.7, 0.6],
            'sentiment_score': [0.7, 0.6, 0.5],
            'volume_score': [0.9, 0.8, 0.7],
            'total_score': [0.79, 0.69, 0.59],
        })
        start = pd.to_datetime('2020-01-02')
        end = pd.to_datetime('2020-01-06')
        result = _forward_fill(df, start, end)
        assert result['total_score'].iloc[0] == 0.79
        assert result['total_score'].iloc[-1] == 0.59


class TestShiftYears:
    def test_normal_year_shift(self):
        d = datetime(2020, 6, 15)
        result = _shift_years(d, -3)
        assert result == datetime(2017, 6, 15)

    def test_leap_year_feb29_shift(self):
        d = datetime(2020, 2, 29)
        result = _shift_years(d, -3)
        assert result == datetime(2017, 2, 28)
