import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import backtrader as bt
from backtest.data_loader import load_market_data, load_market_turnover_data, load_security_etf_data, load_shanghai_composite

START, END = '20210531', '20260529'
stock = load_market_data('600030', START, END)
idx = load_shanghai_composite(START, END)
sec = load_security_etf_data(START, END)
turn = load_market_turnover_data(START, END)

class Probe(bt.Strategy):
    def __init__(self):
        self.ds = self.datas[0]; self.dm = self.datas[1]; self.dsec = self.datas[2]; self.dt = self.datas[3]
        self.market_ma = bt.ind.SMA(self.dm.close, period=120)
        self.sector_ma = bt.ind.SMA(self.dsec.close, period=60)
        self.turnover_ma = bt.ind.SMA(self.dt.close, period=20)
        self.vol_ma = bt.ind.SMA(self.ds.volume, period=20)
        self.ma_mid = bt.ind.SMA(self.ds.close, period=20)
        self.lowest10 = bt.ind.Lowest(self.ds.low, period=10)
    def next(self):
        dt = self.ds.datetime.date(0)
        if str(dt) in ('2024-09-23','2024-09-24','2024-09-25','2024-09-26','2024-09-27'):
            cl=self.ds.close[0]; op=self.ds.open[0]; lo=self.ds.low[0]; vol=self.ds.volume[0]
            vma=self.vol_ma[0]; ma20=self.ma_mid[0]; lo10=self.lowest10[0]
            mk=self.dm.close[0]>self.market_ma[0]; se=self.dsec.close[0]>self.sector_ma[0]; tr=self.dt.close[0]>self.turnover_ma[0]
            ratio = vol / vma if vma else 0
            intraday = (cl/op-1)*100
            near15 = cl <= lo10 * 1.15
            near10 = cl <= lo10 * 1.10
            print(f'{dt}: cl={cl:.2f} op={op:.2f} lo={lo:.2f} vol={int(vol)} vma={int(vma)} ratio={ratio:.2f}x intra={intraday:+.1f}% ma20={ma20:.2f} lo10={lo10:.2f} near15={near15} near10={near10} | mkt={mk} sec={se} trn={tr}')

cerebro = bt.Cerebro()
cerebro.addstrategy(Probe)
cerebro.adddata(bt.feeds.PandasData(dataname=stock, datetime='date'))
cerebro.adddata(bt.feeds.PandasData(dataname=idx, datetime='date'))
cerebro.adddata(bt.feeds.PandasData(dataname=sec, datetime='date'))
cerebro.adddata(bt.feeds.PandasData(dataname=turn, datetime='date'))
cerebro.broker.set_cash(100000.0)
cerebro.run()
