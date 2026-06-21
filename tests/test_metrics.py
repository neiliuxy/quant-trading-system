import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from backtest.metrics import (
    extract_sharpe,
    extract_annual_return_pct,
    compute_profit_loss_ratio,
    compute_benchmark_return_pct,
    compute_excess_return_pct,
)


def test_extract_sharpe_normal():
    assert extract_sharpe({'sharperatio': 1.25}) == pytest.approx(1.25)


def test_extract_sharpe_none_returns_zero():
    assert extract_sharpe({'sharperatio': None}) == 0.0


def test_extract_sharpe_missing_key_returns_zero():
    assert extract_sharpe({}) == 0.0


def test_extract_annual_return_pct_normal():
    assert extract_annual_return_pct({'rnorm100': 21.7}) == pytest.approx(21.7)


def test_extract_annual_return_pct_missing_returns_zero():
    assert extract_annual_return_pct({}) == 0.0


def test_profit_loss_ratio_normal():
    stats = {
        'won': {'pnl': {'average': 16135.79}},
        'lost': {'pnl': {'average': -4496.12}},
    }
    assert compute_profit_loss_ratio(stats) == pytest.approx(16135.79 / 4496.12)


def test_profit_loss_ratio_no_losses_returns_zero():
    stats = {
        'won': {'pnl': {'average': 1000.0}},
        'lost': {'pnl': {'average': 0.0}},
    }
    assert compute_profit_loss_ratio(stats) == 0.0


def test_profit_loss_ratio_missing_lost_returns_zero():
    stats = {'won': {'pnl': {'average': 1000.0}}}
    assert compute_profit_loss_ratio(stats) == 0.0


def test_benchmark_return_normal():
    index_data = [{'close': 3000.0}, {'close': 3300.0}]
    # (3300/3000 - 1) * 100 = 10.0
    assert compute_benchmark_return_pct(index_data) == pytest.approx(10.0)


def test_benchmark_return_empty_returns_zero():
    assert compute_benchmark_return_pct([]) == 0.0


def test_benchmark_return_zero_first_close_returns_zero():
    index_data = [{'close': 0.0}, {'close': 3300.0}]
    assert compute_benchmark_return_pct(index_data) == 0.0


def test_excess_return_positive():
    # 策略 25%，基准 10% → 超额 15%
    assert compute_excess_return_pct(25.0, 10.0) == pytest.approx(15.0)


def test_excess_return_negative():
    # 策略跑输基准
    assert compute_excess_return_pct(5.0, 10.0) == pytest.approx(-5.0)
