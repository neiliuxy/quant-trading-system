"""MVP filter rules. Each returns (passed: bool, reason: str).

All inputs are per-stock daily frames sliced to <= screening date.
Listing date is estimated from earliest cached stock_daily date (Plan R2
mitigation: akshare lacks bulk listing-date source).
"""
from __future__ import annotations

import pandas as pd

from screening.indicators import (
    avg_amount,
    data_completeness,
    return_pct,
    slope_pct,
    sma,
)


def check_not_st(name: str) -> tuple[bool, str]:
    """Name prefix ST / *ST flags risk-warning status."""
    if not name:
        return True, "name missing"
    stripped = name.lstrip().lstrip("*")
    if stripped.startswith("ST"):
        return False, "ST/*ST in name"
    return True, ""


def check_listing_days(
    earliest_date: pd.Timestamp | None,
    screening_date: pd.Timestamp,
    min_days: int,
) -> tuple[bool, str]:
    """Listing days estimated from earliest cached trading day."""
    if earliest_date is None:
        return True, "listing data unavailable"
    days = (screening_date - earliest_date).days
    if days < min_days:
        return False, f"listed only {days}d (< {min_days})"
    return True, ""


def check_avg_turnover(
    frame: pd.DataFrame, window: int, threshold: float
) -> tuple[bool, str]:
    avg = avg_amount(frame, window)
    if avg is None:
        return False, "amount missing"
    if avg < threshold:
        return False, f"avg amount {avg/1e8:.2f}e (< {threshold/1e8:.2f}e)"
    return True, ""


def check_data_completeness(
    frame: pd.DataFrame, window: int, threshold: float
) -> tuple[bool, str]:
    """Require enough cached trading days in the recent window."""
    recent = frame.tail(window)
    completeness = data_completeness(recent, window)
    if completeness < threshold:
        return False, f"completeness {completeness:.2f} (< {threshold})"
    return True, ""


def check_close_gt_ma20(frame: pd.DataFrame) -> tuple[bool, str]:
    close = frame["close"]
    ma = sma(close, 20)
    if ma is None:
        return False, "ma20 unavailable"
    cur = float(close.iloc[-1])
    if cur <= ma:
        return False, f"close {cur:.2f} <= ma20 {ma:.2f}"
    return True, ""


def check_ma20_gt_ma60(frame: pd.DataFrame) -> tuple[bool, str]:
    close = frame["close"]
    ma20 = sma(close, 20)
    ma60 = sma(close, 60)
    if ma20 is None or ma60 is None:
        return False, "ma20/ma60 unavailable"
    if ma20 <= ma60:
        return False, f"ma20 {ma20:.2f} <= ma60 {ma60:.2f}"
    return True, ""


def check_ma60_slope_up(
    frame: pd.DataFrame, lookback: int = 5
) -> tuple[bool, str]:
    close = frame["close"]
    ma60_series = close.rolling(60).mean()
    slope = slope_pct(ma60_series, lookback)
    if slope is None:
        return False, "ma60 slope unavailable"
    if slope <= 0:
        return False, f"ma60 slope {slope:.4f} <= 0"
    return True, ""


def check_outperform_index(
    frame: pd.DataFrame, index_frame: pd.DataFrame, window: int
) -> tuple[bool, str]:
    stock_ret = return_pct(frame["close"], window)
    idx_ret = return_pct(index_frame["close"], window)
    if stock_ret is None or idx_ret is None:
        return False, "return window insufficient"
    diff = stock_ret - idx_ret
    if diff <= 0:
        return False, f"underperform index by {-diff:.2%}"
    return True, ""


def apply_filters(
    frame: pd.DataFrame,
    name: str,
    earliest_date: pd.Timestamp | None,
    index_frame: pd.DataFrame,
    screening_date: pd.Timestamp,
    cfg,  # ScreenerFilterConfig
) -> dict[str, bool]:
    """Run all MVP filters. Returns map of filter_name -> passed."""
    return {
        "not_st": check_not_st(name)[0],
        "listing_days": check_listing_days(earliest_date, screening_date, cfg.min_listing_days)[0],
        "turnover": check_avg_turnover(frame, cfg.turnover_window, cfg.min_avg_turnover)[0],
        "data_complete": check_data_completeness(frame, cfg.data_window, cfg.min_data_completeness)[0],
        "close_gt_ma20": check_close_gt_ma20(frame)[0] if cfg.require_close_gt_ma20 else True,
        "ma20_gt_ma60": check_ma20_gt_ma60(frame)[0] if cfg.require_ma20_gt_ma60 else True,
        "ma60_slope_up": check_ma60_slope_up(frame)[0] if cfg.require_ma60_slope_up else True,
        "outperform_index": check_outperform_index(frame, index_frame, cfg.return_window)[0] if cfg.require_outperform_index else True,
    }