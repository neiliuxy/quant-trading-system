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


def generate_synthetic_data(days=800, start_price=12.0, seed=42):
    """生成模拟日线数据（牛市+震荡+熊市）"""
    import numpy as np
    np.random.seed(seed)
    dates = pd.date_range('2020-01-01', periods=days, freq='B')
    prices = [start_price]
    for i in range(days - 1):
        if i < 200:   # 牛市
            trend = 0.002
        elif i < 400:  # 震荡
            trend = 0.0001 * (np.random.rand() - 0.5)
        elif i < 600:  # 熊市
            trend = -0.0015
        else:         # 恢复
            trend = 0.001
        noise = np.random.randn() * 0.02 * prices[-1]
        prices.append(prices[-1] * (1 + trend) + noise)
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * (1 + np.random.rand() * 0.015) for p in prices],
        'low':  [p * (1 - np.random.rand() * 0.015) for p in prices],
        'close': prices,
        'volume': [int(1e7 + np.random.randn() * 2e6) for _ in prices],
    })
    return df


def run(symbol='000001', start='20200101', end='20231231', cash=100000):
    """运行回测"""
    cerebro = bt.Cerebro()

    # 获取数据
    try:
        print(f'正在获取 {symbol} 历史数据...')
        df = ak.stock_zh_a_hist(symbol=symbol, period='daily',
                                 start_date=start, end_date=end)
        df = df[['日期', '开盘', '最高', '最低', '收盘', '成交量']]
        df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    except Exception as e:
        print(f'网络获取失败({e})，使用模拟数据演示回测')
        df = generate_synthetic_data()
    df['date'] = pd.to_datetime(df['date'])

    data = bt.feeds.PandasData(dataname=df, datetime=0)
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
