"""Backtest the sector_rotation strategy across the A-share securities
brokerage universe (600030, 601066, 601688).

The strategy needs 1 market index feed + N stock feeds, which is a
different shape from the single-symbol strategies. We bypass the
service layer and build the cerebro engine directly.
"""

import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import backtrader as bt
import pandas as pd

from backtest.data_loader import (
    load_market_data,
    load_shanghai_composite,
)
from strategies.sector_rotation import SectorRotationStrategy


UNIVERSE = ['600030', '601066', '601688']
START = '20210101'
END = '20260529'
CASH = 100000.0

TRAIN_END = '20251231'
VALID_START = '20260101'


def _build_cerebro(params, symbols=UNIVERSE):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(SectorRotationStrategy, **params)
    # First feed: Shanghai Composite
    idx = load_shanghai_composite(START, END)
    cerebro.adddata(bt.feeds.PandasData(dataname=idx, datetime='date'))
    # Then each stock in the universe
    for sym in symbols:
        df = load_market_data(sym, START, END)
        cerebro.adddata(bt.feeds.PandasData(dataname=df, datetime='date'))
    cerebro.broker.set_cash(CASH)
    return cerebro


def _attach_analyzers(cerebro):
    class TradeLog(bt.Analyzer):
        def __init__(self):
            self.trades = []

        def notify_trade(self, trade):
            if trade.isclosed:
                self.trades.append({
                    'data': trade.data._name,
                    'open': bt.num2date(trade.dtopen).strftime('%Y-%m-%d'),
                    'close': bt.num2date(trade.dtclose).strftime('%Y-%m-%d'),
                    'open_p': round(trade.price, 2),
                    'pnl': round(trade.pnl, 0),
                })

    cerebro.addanalyzer(TradeLog, _name='trades')
    return cerebro


def _slice_trades(trades, start_str, end_str):
    sd = date.fromisoformat(start_str)
    ed = date.fromisoformat(end_str)
    return [t for t in trades if sd <= date.fromisoformat(t['open']) <= ed
            or sd <= date.fromisoformat(t['close']) <= ed]


def main():
    configs = [
        ('baseline (no RSRS)', dict(use_rsrs_filter=False)),
        ('RSRS thr=0.0', dict(use_rsrs_filter=True, rsrs_threshold=0.0)),
        ('RSRS thr=0.5', dict(use_rsrs_filter=True, rsrs_threshold=0.5)),
        ('RSRS thr=-0.5', dict(use_rsrs_filter=True, rsrs_threshold=-0.5)),
        ('RSRS thr=0.0 + top2', dict(use_rsrs_filter=True, rsrs_threshold=0.0, top_n=2)),
    ]
    base = dict(top_n=1, rebalance_days=20, momentum_low=0.05, momentum_high=0.20)

    print('=== Sector Rotation 回测 ===')
    print(f'宇宙: {UNIVERSE}, 期间: {START}..{END}')
    print()
    for name, extra in configs:
        params = {**base, **extra}
        cerebro = _build_cerebro(params)
        _attach_analyzers(cerebro)
        results = cerebro.run()
        strat = results[0]
        v = cerebro.broker.getvalue()
        trades = strat.analyzers.trades.trades
        ret = (v / CASH - 1) * 100
        train_sub = _slice_trades(trades, START, TRAIN_END)
        valid_sub = _slice_trades(trades, VALID_START, END)
        train_pnl = sum(t['pnl'] for t in train_sub)
        valid_pnl = sum(t['pnl'] for t in valid_sub)
        print(f'{name:>30}: full={ret:+6.2f}% train={train_pnl/1000:+5.1f}K valid={valid_pnl/1000:+5.1f}K n={len(trades):>2}/{len(train_sub):>2}/{len(valid_sub):>2}')
    print()

    # Print full trade list for the best config
    print('=== RSRS thr=0.0 (best balance) 完整交易 ===')
    params = {**base, 'use_rsrs_filter': True, 'rsrs_threshold': 0.0}
    cerebro = _build_cerebro(params)
    _attach_analyzers(cerebro)
    results = cerebro.run()
    v = cerebro.broker.getvalue()
    trades = results[0].analyzers.trades.trades
    print(f'final: {v:.0f} ret: {(v/CASH-1)*100:+.2f}% n={len(trades)}')
    for t in trades:
        marker = ' V' if _slice_trades([t], VALID_START, END) else '  '
        print(f'  {marker}{t}')


if __name__ == '__main__':
    main()
