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

# 包装 strategy，记录每个 next() 的 shock/breakout 状态
class Debug(CiticWaveStrategy):
    def __init__(self):
        super().__init__()
        self.fired = []
    def next(self):
        # 9/24 附近
        dt = self.data_stock.datetime.date(0)
        if str(dt) in ('2024-09-24','2024-09-25','2024-09-26','2024-09-27'):
            cl = self.data_stock.close[0]; op = self.data_stock.open[0]
            vol = self.data_stock.volume[0]; vma = self.vol_ma[0]
            ma20 = self.ma_mid[0]; lo10 = self.lowest_pullback[0]
            vol_ok = vol > vma * 3.0
            intraday = (cl/op - 1) >= 0.03
            ma_ok = cl > ma20
            near15 = cl <= lo10 * 1.15
            self.fired.append({
                'date': str(dt), 'vol_ok': vol_ok, 'intraday': intraday,
                'ma_ok': ma_ok, 'near15': near15, 'all_shock': vol_ok and intraday and ma_ok and near15,
                'position': self.position.size,
            })
        # 跳过真实 buy,只记日志
        # 但要重写以避免真实下单
        if len(self.data) < 60: return
        # 不调用 super().next()，只检查信号

cerebro = bt.Cerebro()
cerebro.addstrategy(Debug, shock_vol_mult=3.0, shock_intraday_pct=0.03, shock_near_low_pct=0.15,
    breakout_window=60, max_extension_pct=0.2, max_hold_days=30)
cerebro.adddata(bt.feeds.PandasData(dataname=stock, datetime='date'))
cerebro.adddata(bt.feeds.PandasData(dataname=idx, datetime='date'))
cerebro.adddata(bt.feeds.PandasData(dataname=sec, datetime='date'))
cerebro.adddata(bt.feeds.PandasData(dataname=turn, datetime='date'))
cerebro.broker.set_cash(100000.0)
r = cerebro.run()
print('=== 9/24 附近 shock 检查 ===')
for ev in r[0].fired:
    print(ev)
