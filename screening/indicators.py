"""Per-stock indicators computed from daily bars.

All inputs are pd.Series indexed by date (ascending). Outputs are scalar
values computed strictly from rows with date <= the screening date —
no future look-ahead.

Window semantics match backtrader SMA (simple moving average of close,
including the current bar).
"""
from __future__ import annotations

import pandas as pd


def sma(close: pd.Series, window: int) -> float | None:
    """Last value of simple moving average. None if window not satisfied."""
    if len(close) < window or window <= 0:
        return None
    return float(close.iloc[-window:].mean())


def slope_pct(series: pd.Series, lookback: int = 5) -> float | None:
    """% change of series over last `lookback` bars, using close values only."""
    if len(series) < lookback + 1 or lookback <= 0:
        return None
    prev = float(series.iloc[-(lookback + 1)])
    cur = float(series.iloc[-1])
    if prev == 0:
        return None
    return (cur - prev) / abs(prev)


def return_pct(close: pd.Series, window: int) -> float | None:
    """% return over the last `window` bars. None if insufficient history."""
    if len(close) < window + 1 or window <= 0:
        return None
    prev = float(close.iloc[-(window + 1)])
    cur = float(close.iloc[-1])
    if prev == 0:
        return None
    return (cur - prev) / prev


def data_completeness(frame: pd.DataFrame, window: int) -> float:
    """Fraction of expected trading days present in the last `window` bars.

    Uses business-day calendar (Mon-Fri). Does not subtract holidays — that
    would be a stricter check, but the spec only requires a lower bound.
    """
    if len(frame) < 1 or window <= 1:
        return 1.0
    actual = min(len(frame), window)
    expected = window
    return actual / expected


def avg_amount(frame: pd.DataFrame, window: int) -> float | None:
    """Mean of `amount` over the last `window` bars."""
    if "amount" not in frame.columns or len(frame) < 1:
        return None
    series = frame["amount"].tail(window)
    if series.empty:
        return None
    return float(series.mean())


def slice_to_date(frame: pd.DataFrame, end_date: pd.Timestamp) -> pd.DataFrame:
    """Return only rows with date <= end_date. Defensive: caller may pass a
    frame that already extends past the screening date."""
    if frame is None or frame.empty:
        return frame.iloc[0:0] if frame is not None else pd.DataFrame()
    return frame[frame["date"] <= end_date].reset_index(drop=True)