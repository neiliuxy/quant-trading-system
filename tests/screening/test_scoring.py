"""Unit tests for screening.scoring."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import math

import pandas as pd

from screening.config import CandidateScore, ScreenerScoreConfig
from screening.scoring import (
    score_relative_strength,
    score_trend_quality,
    score_drawdown,
    score_vol_price,
    score_liquidity,
    compute_total_score,
    score_stock,
)


def _uptrend_frame(n: int = 120, base: float = 10.0, vol: float = 1e6, amount: float = 2e8) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("20240101", periods=n),
        "open": [base + i * 0.1 for i in range(n)],
        "high": [base + i * 0.1 + 0.5 for i in range(n)],
        "low": [base + i * 0.1 - 0.5 for i in range(n)],
        "close": [base + i * 0.1 for i in range(n)],
        "volume": [vol] * n,
        "amount": [amount] * n,
    })


def _flat_frame(n: int = 120, base: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("20240101", periods=n),
        "open": [base] * n,
        "high": [base] * n,
        "low": [base] * n,
        "close": [base] * n,
        "volume": [1_000_000] * n,
        "amount": [2e8] * n,
    })


def test_relative_strength_stock_beats():
    stock = _uptrend_frame(120, base=10)
    idx = pd.DataFrame({
        "date": pd.date_range("20240101", periods=120),
        "close": [10 - i * 0.01 for i in range(120)],
    })
    s = score_relative_strength(stock, idx, 60)
    assert s > 0.5  # stock up, idx down → strong outperformance


def test_relative_strength_stock_loses():
    stock = pd.DataFrame({
        "date": pd.date_range("20240101", periods=120),
        "close": [10 - i * 0.01 for i in range(120)],
    })
    idx = _uptrend_frame(120, base=10)
    s = score_relative_strength(stock, idx, 60)
    assert s < 0.5


def test_trend_quality_uptrend_high():
    s = score_trend_quality(_uptrend_frame(120))
    assert s > 0.5


def test_trend_quality_flat_low():
    s = score_trend_quality(_flat_frame(120))
    assert s <= 0.5


def test_drawdown_clean_uptrend_high():
    s = score_drawdown(_uptrend_frame(120))
    assert s >= 0.9  # no drawdown


def test_drawdown_with_drop_low():
    frame = _uptrend_frame(120)
    # force a 30% drop in last 20 bars
    frame.loc[frame.index[-20:], "close"] = [frame["close"].iloc[-21] * (1 - i * 0.02) for i in range(20)]
    s = score_drawdown(frame)
    assert s < 0.3


def test_liquidity_log_scaled():
    assert score_liquidity(_uptrend_frame(amount=1e8)) < score_liquidity(_uptrend_frame(amount=1e9))
    assert score_liquidity(_uptrend_frame(amount=1e9)) <= 1.0
    assert score_liquidity(_uptrend_frame(amount=5e7)) < score_liquidity(_uptrend_frame(amount=1e8))


def test_vol_price_range():
    s = score_vol_price(_uptrend_frame(120))
    assert 0.0 <= s <= 1.0


def test_total_score_weighted_sum():
    cfg = ScreenerScoreConfig(
        w_relative_strength=1.0, w_trend_quality=0.0,
        w_drawdown=0.0, w_vol_price=0.0, w_liquidity=0.0,
    )
    sub_score = CandidateScore(0.7, 0.5, 0.4, 0.3, 0.2)
    assert math.isclose(compute_total_score(sub_score, cfg), 0.7)


def test_score_stock_returns_candidate_score():
    stock = _uptrend_frame(120)
    idx = _uptrend_frame(120, base=10)
    cfg = ScreenerScoreConfig()
    sub = score_stock(stock, idx, cfg)
    assert 0 <= sub.relative_strength <= 1
    assert 0 <= sub.trend_quality <= 1
    assert 0 <= sub.drawdown <= 1
    assert 0 <= sub.vol_price <= 1
    assert 0 <= sub.liquidity <= 1