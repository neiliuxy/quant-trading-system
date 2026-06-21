import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backtrader as bt
import pytest

from backtest.costs import (
    AShareCommission,
    COMMISSION_RATE,
    MIN_COMMISSION,
    STAMP_DUTY_RATE,
    TRANSFER_FEE_RATE,
    SLIPPAGE_PERC,
    apply_ashare_costs,
)


def test_buy_cost_excludes_stamp_duty():
    comm = AShareCommission()
    # 金额够大,佣金按比例(超过最低 5 元)。买入 size > 0。
    size, price = 1000, 50.0  # value = 50000
    value = size * price
    cost = comm._getcommission(size, price, pseudoexec=False)
    expected = value * COMMISSION_RATE + value * TRANSFER_FEE_RATE
    assert cost == pytest.approx(expected)
