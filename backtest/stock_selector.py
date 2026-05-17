"""选股回测工具 - 找出适合双均线+布林带策略的股票"""
import os
import sys
import time
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import backtrader as bt
from backtest.data_loader import load_market_data
from strategies.swing_ma_boll import SwingStrategy


def run_single_backtest(symbol, start='20200101', end='20231231', cash=100000):
    """运行单只股票回测，返回关键指标"""
    try:
        df = load_market_data(symbol, start, end)
        if len(df) < 60:
            return None

        cerebro = bt.Cerebro()
        data = bt.feeds.PandasData(dataname=df, datetime=0)
        cerebro.adddata(data)
        cerebro.addstrategy(SwingStrategy)
        cerebro.broker.setcash(cash)

        initial = cash
        cerebro.run(runonce=False, stdstats=False)

        final_value = cerebro.broker.getvalue()
        total_return = (final_value / cash - 1) * 100

        return {
            'symbol': symbol,
            'initial_cash': initial,
            'final_value': final_value,
            'total_return': total_return,
            'data_points': len(df),
        }
    except Exception:
        return None


def main():
    print('=' * 60)
    print('选股回测工具 - 双均线+布林带策略')
    print('=' * 60)

    print('\n正在获取沪深300成分股列表...')
    symbols = None
    try:
        import akshare as ak
        df_index = ak.index_stock_cons_weight_csindex(symbol='000300')
        symbols = df_index['成分券代码'].head(50).tolist()
        print(f'获取到 {len(symbols)} 只候选股票')
    except Exception as e:
        print(f'获取成分股失败: {e}')

    if not symbols:
        symbols = [
            '600519', '000858', '601318', '600036', '000333',
            '300750', '600276', '601012', '600030', '000002',
            '600887', '601166', '000001', '601328', '600009',
            '600016', '601398', '601288', '600028', '600050',
        ]
        print(f'使用备用列表 {len(symbols)} 只股票')

    print(f'\n开始批量回测 ({len(symbols)} 只股票)...')
    print('-' * 60)

    results = []
    for i, symbol in enumerate(symbols, 1):
        print(f'[{i:2d}/{len(symbols)}] 回测 {symbol}...', end=' ', flush=True)
        result = run_single_backtest(symbol)
        if result:
            results.append(result)
            print(f"收益率: {result['total_return']:+.2f}%")
        else:
            print('失败 (数据不足或获取失败)')
        time.sleep(0.3)

    if not results:
        print('\n没有成功的回测结果')
        return

    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values('total_return', ascending=False)

    print('\n' + '=' * 60)
    print('回测结果汇总')
    print('=' * 60)
    print(f'成功回测: {len(results)} / {len(symbols)} 只')
    print(f'平均收益率: {df_results["total_return"].mean():.2f}%')
    print(f'中位数收益率: {df_results["total_return"].median():.2f}%')
    print(f'最大收益率: {df_results["total_return"].max():.2f}%')
    print(f'最小收益率: {df_results["total_return"].min():.2f}%')
    print(f'正收益股票: {(df_results["total_return"] > 0).sum()} 只 ({(df_results["total_return"] > 0).mean()*100:.1f}%)')

    print('\n--- 收益 TOP 10 ---')
    print(df_results.head(10)[['symbol', 'total_return', 'final_value']].to_string(index=False))

    print('\n--- 收益 BOTTOM 5 ---')
    print(df_results.tail(5)[['symbol', 'total_return', 'final_value']].to_string(index=False))

    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'backtest_results.csv'
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_results.to_csv(output_path, index=False)
    print(f'\n详细结果已保存到: {output_path}')


if __name__ == '__main__':
    main()
