"""Unit tests for screening.filters — pure logic on synthetic frames."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import pytest

from screening.config import ScreenerFilterConfig
from screening.filters import (
    check_not_st,
    check_listing_days,
    check_avg_turnover,
    check_data_completeness,
    check_close_gt_ma20,
    check_ma20_gt_ma60,
    check_ma60_slope_up,
    check_outperform_index,
    apply_filters,
)


def _uptrend_frame(n: int = 120, base: float = 10.0) -> pd.DataFrame:
    """Monotonic uptrend — passes trend filters, has amount."""
    return pd.DataFrame({
        "date": pd.date_range("20240101", periods=n),
        "open": [base + i * 0.1 for i in range(n)],
        "high": [base + i * 0.1 + 0.5 for i in range(n)],
        "low": [base + i * 0.1 - 0.5 for i in range(n)],
        "close": [base + i * 0.1 for i in range(n)],
        "volume": [1_000_000] * n,
        "amount": [2e8] * n,
    })


def _downtrend_frame(n: int = 120) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("20240101", periods=n),
        "open": [20 - i * 0.1 for i in range(n)],
        "high": [20 - i * 0.1 + 0.2 for i in range(n)],
        "low": [20 - i * 0.1 - 0.2 for i in range(n)],
        "close": [20 - i * 0.1 for i in range(n)],
        "volume": [1_000_000] * n,
        "amount": [2e8] * n,
    })


def test_check_not_st():
    assert check_not_st("平安银行") == (True, "")
    assert check_not_st("ST 平安") == (False, "ST/*ST in name")
    assert check_not_st("*ST康美") == (False, "ST/*ST in name")
    assert check_not_st("") == (True, "name missing")


def test_check_listing_days():
    screen = pd.Timestamp("20260628")
    assert check_listing_days(pd.Timestamp("20251201"), screen, 180)[0]
    assert not check_listing_days(pd.Timestamp("20260401"), screen, 180)[0]
    assert check_listing_days(None, screen, 180)[0]  # missing → pass


def test_check_avg_turnover_passes_high_amount():
    frame = _uptrend_frame(120)
    passed, _ = check_avg_turnover(frame, 20, 1e8)
    assert passed


def test_check_avg_turnover_fails_low_amount():
    frame = _uptrend_frame(120)
    frame.loc[:, "amount"] = 5e7  # 5000万 < 1亿
    passed, msg = check_avg_turnover(frame, 20, 1e8)
    assert not passed
    assert "0.50e" in msg


def test_check_data_completeness_short_frame():
    frame = _uptrend_frame(50)  # only 50 rows
    passed, _ = check_data_completeness(frame, 60, 0.9)
    assert not passed


def test_check_close_gt_ma20_uptrend():
    frame = _uptrend_frame(120)
    passed, _ = check_close_gt_ma20(frame)
    assert passed


def test_check_close_gt_ma20_downtrend_fails():
    frame = _downtrend_frame(120)
    passed, _ = check_close_gt_ma20(frame)
    assert not passed


def test_check_ma20_gt_ma60_uptrend():
    frame = _uptrend_frame(120)
    passed, _ = check_ma20_gt_ma60(frame)
    assert passed


def test_check_ma60_slope_up_uptrend():
    frame = _uptrend_frame(120)
    passed, _ = check_ma60_slope_up(frame)
    assert passed


def test_check_outperform_index_stock_beats():
    stock = _uptrend_frame(120, base=10)
    idx = _downtrend_frame(120)
    # stock going up, idx going down → stock outperforms
    passed, _ = check_outperform_index(stock, idx, 60)
    assert passed


def test_apply_filters_all_pass_for_strong_stock():
    frame = _uptrend_frame(120)
    idx = _downtrend_frame(120)
    cfg = ScreenerFilterConfig()
    screening_date = pd.Timestamp("20260628")
    earliest = pd.Timestamp("20240101")
    flags = apply_filters(frame, "贵州茅台", earliest, idx, screening_date, cfg)
    assert all(flags.values()), f"expected all True, got {flags}"


def test_apply_filters_st_name_fails_first():
    frame = _uptrend_frame(120)
    idx = _downtrend_frame(120)
    cfg = ScreenerFilterConfig()
    screening_date = pd.Timestamp("20260628")
    earliest = pd.Timestamp("20240101")
    flags = apply_filters(frame, "*ST 测试", earliest, idx, screening_date, cfg)
    assert not flags["not_st"]
    assert flags["turnover"]  # other filters still run