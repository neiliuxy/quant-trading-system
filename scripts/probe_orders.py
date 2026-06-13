import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import backtrader as bt
from backtest.data_loader import load_market_data, load_market_turnover_data, load_security_etf_data, load_shanghai_composite
from strategies.citic_wave import CiticWaveStrategy

START, END = '20210531', '20260529'
stock = load_market_data('600030', START, END)
idx = load_shanghai_composite(START, END)
sec = load_security_etf_data(START, END)
turn = load_market_turnover_data(START, END)

class Debug(CiticWaveStrategy):
    def __init__(self):
        super().__init__()
        self.events = []
    def notify_order(self, order):
        if order.status == order.Submitted:
            self.events.append(('SUB', self.data_stock.datetime.date(0), order.isbuy(), order.size))
        elif order.status == order.Accepted:
            self.events.append(('ACC', self.data_stock.datetime.date(0), order.isbuy(), order.size))
        elif order.status == order.Completed:
            self.events.append(('COM', self.data_stock.datetime.date(0), order.isbuy(), order.executed.price))
        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            self.events.append(('XXX', self.data_stock.datetime.date(0), order.isbuy(), order.status))
        super().notify_order(order)

cerebro = bt.Cerebro()
cerebro.addstrategy(Debug, shock_vol_mult=3.0, shock_intraday_pct=0.03, shock_near_low_pct=0.15,
    breakout_window=60, max_extension_pct=0.2, max_hold_days=30, max_hold_days=30,
    trailing_atr_mult=99, trailing_start_bars=999)
cerebro.adddata(bt.feeds.PandasData(dataname=stock, datetime='date'))
cerebro.adddata(bt.feeds.PandasData(dataname=idx, datetime='date'))
cerebro.adddata(bt.feeds.PandasData(dataname=sec, datetime='date'))
cerebro.adddata(bt.feeds.PandasData(datenam
