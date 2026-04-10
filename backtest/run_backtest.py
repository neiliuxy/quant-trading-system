#!/usr/bin/env python3
"""回测运行器"""

import pandas as pd
import backtrader as bt
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.swing_ma_boll import SwingStrategy
import akshare as ak


def run(symbol='000001', start='20200101', end='20231231', cash=100000):
    """运行回测"""
    cerebro = bt.Cerebro()

    # 获取数据
    print(f'正在获取 {symbol} 历史数据...')
    df = ak.stock_zh_a_hist(symbol=symbol, period='daily',
                             start_date=start, end_date=end)
    df = df[['日期', '开盘', '最高', '最低', '收盘', '成交量']]
    df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    df['date'] = bt.date2num(pd.to_datetime(df['date']))

    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)
    cerebro.addstrategy(SwingStrategy)
    cerebro.broker.setcash(cash)

    print(f'起始资金: {cerebro.broker.getcash():.2f}')
    cerebro.run()
    final_value = cerebro.broker.getvalue()
    print(f'结束资金: {final_value:.2f}')
    print(f'收益率: {(final_value / cash - 1) * 100:.2f}%')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='运行量化回测')
    parser.add_argument('--symbol', default='000001', help='股票代码')
    parser.add_argument('--start', default='20200101', help='开始日期')
    parser.add_argument('--end', default='20231231', help='结束日期')
    parser.add_argument('--cash', type=float, default=100000, help='初始资金')
    args = parser.parse_args()

    run(args.symbol, args.start, args.end, args.cash)
