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
        start, end = resolve_date_range(years=1)
        df = get_market_score(start, end, config)

        expected_cols = ['date', 'trend_score', 'sentiment_score', 'volume_score', 'total_score']
        assert list(df.columns) == expected_cols
        assert len(df) > 0
        assert df['total_score'].min() >= 0.0
        assert df['total_score'].max() <= 1.0
        assert pd.api.types.is_datetime64_any_dtype(df['date'])

    @pytest.mark.slow
    def test_cache_hit_on_second_call(self):
        config = MarketConfig()
        start, end = resolve_date_range(years=1)
        df1 = get_market_score(start, end, config)
        df2 = get_market_score(start, end, config)

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

        diff = (df_a['total_score'] != df_b['total_score']).sum()
        assert diff > 0

    @pytest.mark.slow
    def test_no_nan_in_output(self):
        config = MarketConfig()
        start, end = resolve_date_range(years=1)
        df = get_market_score(start, end, config)

        assert not df.isna().any().any()
