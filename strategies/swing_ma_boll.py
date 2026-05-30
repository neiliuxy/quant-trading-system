"""
双均线 + 布林带波段策略
- 快速均线：MA10
- 慢速均线：MA20
- 布林带：20日周期，2倍标准差
- 买入：MA10 上穿 MA20 + 价格在布林中轨之上
- 卖出：MA10 下穿 MA20 或 跌破布林下轨
"""

import backtrader as bt


class SwingStrategy(bt.Strategy):
    params = (
        ('fast_ma', 10),
        ('slow_ma', 20),
        ('risk_percent', 0.95),
        ('market_score_dict', None),
    )

    def __init__(self):
        self.ma_fast = bt.ind.SMA(period=self.p.fast_ma)
        self.ma_slow = bt.ind.SMA(period=self.p.slow_ma)
        self.boll = bt.ind.BollingerBands(period=20, devfactor=2)
        self.signal = 0

    def next(self):
        current_date = self.datas[0].datetime.date(0).strftime('%Y%m%d')

        # 买入条件：MA10上穿MA20 + 价格在布林中轨之上
        if self.ma_fast[0] > self.ma_slow[0] and self.data.close[0] > self.boll.lines.mid[0]:
            if self.signal != 1:
                score_dict = self.p.market_score_dict
                if score_dict is None:
                    score = 1.0
                else:
                    score = score_dict.get(current_date, 0.5)

                cash_for_trade = self.broker.getcash() * self.p.risk_percent
                size = int(cash_for_trade * score / self.data.close[0])
                if size > 0:
                    self.buy(size=size)
                    self.signal = 1

        # 卖出条件：MA10下穿MA20 或 跌破布林下轨
        elif (self.ma_fast[0] < self.ma_slow[0] or
              self.data.close[0] < self.boll.lines.bot[0]):
            if self.signal != 0:
                self.sell()
                self.signal = 0
