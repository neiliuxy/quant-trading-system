import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backtrader as bt
import pandas as pd
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
from backtest.run_backtest import generate_synthetic_data


def test_buy_cost_excludes_stamp_duty():
    comm = AShareCommission()
    # 金额够大,佣金按比例(超过最低 5 元)。买入 size > 0。
    size, price = 1000, 50.0  # value = 50000
    value = size * price
    cost = comm._getcommission(size, price, pseudoexec=False)
    expected = value * COMMISSION_RATE + value * TRANSFER_FEE_RATE
    assert cost == pytest.approx(expected)


def test_sell_cost_includes_stamp_duty():
    comm = AShareCommission()
    size, price = 1000, 50.0  # value = 50000
    value = size * price
    buy_cost = comm._getcommission(size, price, pseudoexec=False)
    sell_cost = comm._getcommission(-size, price, pseudoexec=False)
    # 卖出比买入恰好多一份印花税
    assert sell_cost - buy_cost == pytest.approx(value * STAMP_DUTY_RATE)


def test_minimum_commission_floor():
    comm = AShareCommission()
    # 小额交易:1 手(100 股)低价股,按比例佣金 < 5 元,应被托底到 5 元。
    size, price = 100, 3.0  # value = 300, 比例佣金 = 0.075 元
    value = size * price
    cost = comm._getcommission(size, price, pseudoexec=False)
    # 佣金被托底为 5 元 + 过户费(无印花税,买入)
    expected = MIN_COMMISSION + value * TRANSFER_FEE_RATE
    assert cost == pytest.approx(expected)


def test_apply_costs_sets_slippage():
    cerebro = bt.Cerebro()
    apply_ashare_costs(cerebro)
    assert cerebro.broker.p.slip_perc == pytest.approx(SLIPPAGE_PERC)


def _run_with(cerebro_mutator):
    """跑一段合成数据回测,返回 final_value。cerebro_mutator 用于注入成本。"""
    from strategies.swing_ma_boll import SwingStrategy

    df = generate_synthetic_data(start='20200101', end='20221231')
    df['date'] = pd.to_datetime(df['date'])
    cerebro = bt.Cerebro()
    cerebro.adddata(bt.feeds.PandasData(dataname=df, datetime=0))
    cerebro.addstrategy(SwingStrategy, market_score_dict=None)
    cerebro.broker.setcash(100000.0)
    cerebro_mutator(cerebro)
    cerebro.run(runonce=False, stdstats=False)
    return cerebro.broker.getvalue()


def test_costs_reduce_final_value():
    baseline = _run_with(lambda c: None)            # 无成本
    with_costs = _run_with(apply_ashare_costs)      # 有成本
    # 同样的策略与数据,加成本后最终市值必须更低
    assert with_costs < baseline
