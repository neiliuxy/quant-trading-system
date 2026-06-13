"""Diagnose which days trigger the shock-reversal signal and what
downtrend-context filters would refine it."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import backtrader as bt

from backtest.data_loader import (
    load_market_data,
    load_market_turnover_data,
    load_security_etf_data,
    load_shanghai_composite,
)


START, END = '20210531', '20260529'
SYMBOL = '600030'


class ShockProbe(bt.Strategy):
    params = (
        ('shock_vol_mult', 3.0),
        ('shock_intraday_pct', 0.03),
        ('decline_lookback', 5),
    )

    def __init__(self):
        self.ds = self.datas[0]
        self.dm = self.datas[1]
        self.dsec = self.datas[2]
        self.dt = self.datas[3]
        self.market_ma = bt.ind.SMA(self.dm.close, period=120)
        self.sector_ma = bt.ind.SMA(self.dsec.close, period=60)
        self.turnover_ma = bt.ind.SMA(self.dt.close, period=20)
        self.vol_ma = bt.ind.SMA(self.ds.volume, period=20)
        self.ma_mid = bt.ind.SMA(self.ds.close, period=20)
        self.lowest10 = bt.ind.Lowest(self.ds.low, period=10)
        self.events = []

    def next(self):
        dt = self.ds.datetime.date(0)
        vol = self.ds.volume[0]
        op = self.ds.open[0]
        cl = self.ds.close[0]
        vma = self.vol_ma[0]
        mkt = self.dm.close[0] > self.market_ma[0]
        sec = self.dsec.close[0] > self.sector_ma[0]
        trn = self.dt.close[0] > self.turnover_ma[0]
        raw = (
            vol > vma * self.p.shock_vol_mult
            and (cl / op - 1.0) >= self.p.shock_intraday_pct
            and cl > self.ma_mid[0]
        )
        if raw and mkt and sec and trn:
            lb = self.p.decline_lookback
            prior_decline = cl < self.ds.close[-lb]
            near_low = cl <= self.lowest10[0] * 1.05
            self.events.append({
                'date': str(dt),
                'close': round(cl, 2),
                'vol_x': round(vol / vma, 2),
                'intra%': round((cl / op - 1) * 100, 2),
                'prior_decline': prior_decline,
                'near_low': near_low,
            })


def _run_once(stock, idx, sec, turn, cfg):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(ShockProbe, **cfg)
    cerebro.adddata(bt.feeds.PandasData(dataname=stock, datetime='date'))
    cerebro.adddata(bt.feeds.PandasData(datenam