"""
双均线 + 布林带波段策略
- 快速均线：MA10
- 慢速均线：MA20
- 布林带：20日周期，2倍标准差
- 买入：MA10 上穿 MA20 + 价格在布林中轨之上
- 卖出：MA10 下穿 MA20 或 跌破布林下轨
"""

import akshare as ak
import backtrader as bt


class SwingStrategy(bt.Strategy):
    params = (
        ('fast_ma', 10),
        ('slow_ma', 20),
    )

    def __init__(self):
        self.ma_fast = bt.ind.SMA(period=self.p.fast_ma)
        self.ma_slow = bt.ind.SMA(period=self.p.slow_ma)
        self.boll = bt.ind.BollingerBands(period=20, devfactor=2)
        self.signal = 0  # 0=空仓, 1=持仓

    def next(self):
        # 买入条件：MA10上穿MA20 + 价格在布林中轨之上
        if self.ma_fast > self.ma_slow and self.data.close > self.boll.lines.mid:
            if self.signal != 1:
                self.buy()
                self.signal = 1

        # 卖出条件：MA10下穿MA20 或 跌破布林下轨
        elif (self.ma_fast < self.ma_slow or
              self.data.close < self.boll.lines.bot):
            if self.signal != 0:
                self.sell()
                self.signal = 0


def get_stock_data(code='000001', start='20200101', end='20231231'):
    """获取A股日线数据（以平安银行为例）"""
    df = ak.stock_zh_a_hist(symbol=code, period='daily',
                             start_date=start, end_date=end)
    df = df[['日期', '开盘', '最高', '最低', '收盘', '成交量']]
    df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    df['date'] = bt.date2num(pd.to_datetime(df['date']))
    return df


if __name__ == '__main__':
    import pandas as pd

    cerebro = bt.Cerebro()

    # 获取数据（默认平安银行）
    df = get_stock_data()
    data = bt.feeds.PandasData(dataname=df)

    cerebro.adddata(data)
    cerebro.addstrategy(SwingStrategy)
    cerebro.broker.setcash(100000)

    print(f'起始资金: {cerebro.broker.getvalue():.2f}')
    cerebro.run()
    print(f'结束资金: {cerebro.broker.getvalue():.2f}')
