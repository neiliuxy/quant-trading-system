#!/usr/bin/env python3
"""回测运行器"""

import pandas as pd
import backtrader as bt
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.swing_ma_boll import SwingStrategy
from strategies.b1_strategy import B1Strategy
from backtest.data_loader import load_market_data, load_data, resolve_date_range
from market.market_analyzer import MarketConfig, get_market_score


def generate_synthetic_data(start='2020-01-01', end='2023-01-01', start_price=12.0, seed=42):
    """生成模拟日线数据（牛市+震荡+熊市），日期范围对齐请求区间"""
    import numpy as np
    np.random.seed(seed)
    dates = pd.bdate_range(start=start, end=end)
    days = len(dates)
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


def run(symbol='000001', start=None, end=None, cash=100000, use_market_filter=True, strategy_id='swing', **strategy_params):
    """运行回测

    Args:
        symbol: 股票代码
        start:  开始日期 YYYYMMDD, None 则默认近 3 年
        end:    结束日期 YYYYMMDD, None 则今天
        cash:   初始资金
        use_market_filter: 是否启用市场过滤器
        strategy_id: 策略 ID ('swing' 或 'b1')
        **strategy_params: 策略参数，如 short_ma=15, long_ma=50
    """
    start, end = resolve_date_range(start, end)
    cerebro = bt.Cerebro()

    # ── 市场评分 ──
    market_score_dict = None
    if use_market_filter:
        config = MarketConfig()
        try:
            score_df = get_market_score(start, end, config)
            market_score_dict = dict(zip(
                score_df['date'].dt.strftime('%Y%m%d'),
                score_df['total_score'],
            ))
            print(f'市场评分范围: {score_df["total_score"].min():.2f} ~ {score_df["total_score"].max():.2f}')
        except Exception as e:
            print(f'市场数据获取失败 ({e}), 降级为无过滤模式')
            market_score_dict = None

    # ── 数据加载 ──
    # B1 策略需要加载指数数据，其他策略只需股票数据
    include_index = (strategy_id == 'b1')

    try:
        if include_index:
            stock_df, index_df = load_data(symbol, start, end, include_index=True)
        else:
            stock_df = load_market_data(symbol, start, end)
            index_df = None
    except Exception as e:
        print(f'数据获取失败({e})，使用模拟数据演示回测')
        stock_df = generate_synthetic_data(start=start, end=end)
        stock_df['date'] = pd.to_datetime(stock_df['date'])
        index_df = None

    # 如果 B1 策略没有指数数据，生成合成指数数据
    if strategy_id == 'b1' and index_df is None:
        print('生成合成上证综合指数数据用于 B1 策略')
        index_df = generate_synthetic_data(start=start, end=end, start_price=3000)
        index_df['date'] = pd.to_datetime(index_df['date'])

    # ── 添加数据源 ──
    stock_data = bt.feeds.PandasData(dataname=stock_df, datetime=0)
    cerebro.adddata(stock_data)

    # 如果有指数数据，添加为第二个数据源
    if index_df is not None:
        index_data = bt.feeds.PandasData(dataname=index_df, datetime=0)
        cerebro.adddata(index_data)
        print('已加载上证综合指数数据')

    # ── 添加策略 ──
    if strategy_id == 'b1':
        cerebro.addstrategy(B1Strategy, market_score_dict=market_score_dict, **strategy_params)
    else:
        cerebro.addstrategy(SwingStrategy, market_score_dict=market_score_dict, **strategy_params)

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
    parser.add_argument('--start', default=None, help='开始日期，默认当前日期近3年')
    parser.add_argument('--end', default=None, help='结束日期，默认当前日期')
    parser.add_argument('--cash', type=float, default=100000, help='初始资金')
    parser.add_argument('--no-market-filter', action='store_true', help='禁用市场过滤器')
    parser.add_argument('--strategy', default='swing', choices=['swing', 'b1'], help='策略 ID (swing 或 b1)')
    parser.add_argument('--short_ma', type=int, default=None, help='短期 MA 周期')
    parser.add_argument('--long_ma', type=int, default=None, help='长期 MA 周期')
    args = parser.parse_args()

    # 构建策略参数字典
    strategy_params = {}
    if args.short_ma is not None:
        strategy_params['short_ma'] = args.short_ma
    if args.long_ma is not None:
        strategy_params['long_ma'] = args.long_ma

    run(args.symbol, args.start, args.end, args.cash,
        use_market_filter=not args.no_market_filter, strategy_id=args.strategy, **strategy_params)
