"""5-dimension scoring. All inputs are per-stock daily frames sliced to <=
screening date. Outputs are sub-scores in [0, 1]; final score is weighted sum
of sub-scores using ScreenerScoreConfig weights.
"""
from __future__ import annotations

import pandas as pd

from screening.indicators import (
    avg_amount,
    return_pct,
    sma,
)
from screening.config import CandidateScore, ScreenerScoreConfig


def score_relative_strength(
    frame: pd.DataFrame, index_frame: pd.DataFrame, window: int
) -> float:
    """Stock's return vs index return over `window`. Maps to [0,1] via
    log scaling; +30% excess -> 1.0, 0% -> 0.5, -30% -> 0.0."""
    stock_ret = return_pct(frame["close"], window)
    idx_ret = return_pct(index_frame["close"], window)
    if stock_ret is None or idx_ret is None:
        return 0.0
    diff = stock_ret - idx_ret
    # logistic-style mapping: 0.5 at diff=0, ~1.0 at diff=+0.3, ~0.0 at diff=-0.3
    return float(1.0 / (1.0 + pd.Series([-diff / 0.15]).map(lambda x: 2.71828 ** x).iloc[0]))


def score_trend_quality(frame: pd.DataFrame) -> float:
    """Reward close > MA20 > MA60 + aligned slopes. 0..1."""
    close = frame["close"]
    ma20 = sma(close, 20)
    ma60 = sma(close, 60)
    if ma20 is None or ma60 is None:
        return 0.0

    score = 0.0
    # Layer 1: price > ma20 — up to 0.4
    cur = float(close.iloc[-1])
    if cur > ma20:
        score += 0.2 + min(0.2, (cur / ma20 - 1.0) * 4)  # 0.2..0.4
    # Layer 2: ma20 > ma60 — up to 0.3
    if ma20 > ma60:
        score += 0.15 + min(0.15, (ma20 / ma60 - 1.0) * 4)
    # Layer 3: ma60 slope up — up to 0.3
    ma60_series = close.rolling(60).mean().dropna()
    if len(ma60_series) >= 6:
        slope = (float(ma60_series.iloc[-1]) - float(ma60_series.iloc[-6])) / abs(float(ma60_series.iloc[-6]))
        if slope > 0:
            score += 0.15 + min(0.15, slope * 30)
    return float(min(1.0, score))


def score_drawdown(frame: pd.DataFrame, window: int = 60) -> float:
    """Smaller recent drawdown = higher score. 0..1.
    0% drawdown -> 1.0, 20%+ drawdown -> 0.0."""
    if len(frame) < window:
        return 0.0
    recent = frame["close"].tail(window)
    peak = recent.cummax()
    dd = (recent - peak) / peak
    max_dd = float(dd.min())  # negative number, e.g. -0.18
    if max_dd >= 0:
        return 1.0
    # Map [-0.20, 0] -> [0, 1]
    return float(max(0.0, 1.0 + max_dd / 0.20))


def score_vol_price(frame: pd.DataFrame, window: int = 20) -> float:
    """Volume on up days vs down days (volume-price confirmation). 0..1.

    Higher when recent up-day volume > down-day volume (rising on volume)."""
    if len(frame) < window + 1:
        return 0.0
    recent = frame.tail(window).copy()
    recent["ret"] = recent["close"].pct_change()
    up_vol = recent.loc[recent["ret"] > 0, "volume"].sum()
    dn_vol = recent.loc[recent["ret"] < 0, "volume"].sum()
    total = up_vol + dn_vol
    if total == 0:
        return 0.5
    ratio = up_vol / total  # 0..1, neutral = 0.5
    return float(min(1.0, max(0.0, ratio)))


def score_liquidity(frame: pd.DataFrame, window: int = 20) -> float:
    """Average daily turnover, log-scaled. 0..1.

    1e8 -> 0.4, 5e8 -> 0.7, 2e9+ -> 1.0."""
    avg = avg_amount(frame, window)
    if avg is None or avg <= 0:
        return 0.0
    import math
    # log10 scaling: 1e8 -> 8, 1e10 -> 10. Map 8..10 -> 0.4..1.0
    log_amt = math.log10(avg)
    if log_amt <= 8:
        return max(0.0, log_amt / 8 * 0.4)
    if log_amt >= 10:
        return 1.0
    return 0.4 + (log_amt - 8) / 2 * 0.6


def compute_total_score(sub: CandidateScore, cfg: ScreenerScoreConfig) -> float:
    return float(
        cfg.w_relative_strength * sub.relative_strength
        + cfg.w_trend_quality * sub.trend_quality
        + cfg.w_drawdown * sub.drawdown
        + cfg.w_vol_price * sub.vol_price
        + cfg.w_liquidity * sub.liquidity
    )


def score_stock(
    frame: pd.DataFrame,
    index_frame: pd.DataFrame,
    cfg: ScreenerScoreConfig,
    return_window: int = 60,
    trend_window: int = 60,
    liquidity_window: int = 20,
) -> CandidateScore:
    sub = CandidateScore(
        relative_strength=score_relative_strength(frame, index_frame, return_window),
        trend_quality=score_trend_quality(frame),
        drawdown=score_drawdown(frame, trend_window),
        vol_price=score_vol_price(frame, 20),
        liquidity=score_liquidity(frame, liquidity_window),
    )
    return sub