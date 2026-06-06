#!/usr/bin/env python3
"""CLI backtest runner."""

import os
import sys

import backtrader as bt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.data_loader import load_market_data, resolve_date_range
from backtest.service import _load_required_feed_frames
from market.market_analyzer import MarketConfig, get_market_score
from strategies.registry import get_strategy_spec


def generate_synthetic_data(start='2020-01-01', end='2023-01-01', start_price=12.0, seed=42):
    """Generate synthetic daily OHLCV data for fallback demos."""
    import numpy as np

    np.random.seed(seed)
    dates = pd.bdate_range(start=start, end=end)
    days = len(dates)
    prices = [start_price]
    for i in range(days - 1):
        if i < 200:
            trend = 0.002
        elif i < 400:
            trend = 0.0001 * (np.random.rand() - 0.5)
        elif i < 600:
            trend = -0.0015
        else:
            trend = 0.001
        noise = np.random.randn() * 0.02 * prices[-1]
        prices.append(prices[-1] * (1 + trend) + noise)
    return pd.DataFrame(
        {
            'date': dates,
            'open': prices,
            'high': [p * (1 + np.random.rand() * 0.015) for p in prices],
            'low': [p * (1 - np.random.rand() * 0.015) for p in prices],
            'close': prices,
            'volume': [int(1e7 + np.random.randn() * 2e6) for _ in prices],
        }
    )


def _normalize_strategy_id(strategy_id):
    aliases = {
        'swing': 'swing_ma_boll',
        'b1': 'b1_strategy',
    }
    return aliases.get(strategy_id, strategy_id)


def _load_cli_required_feed_frames(strategy_id, start, end):
    try:
        return _load_required_feed_frames(get_strategy_spec(strategy_id).required_data, start, end)
    except ValueError as exc:
        if strategy_id == 'b1_strategy' and "shanghai_index" in str(exc):
            print('Generating synthetic Shanghai Composite data for B1 strategy')
            index_df = generate_synthetic_data(start=start, end=end, start_price=3000)
            index_df['date'] = pd.to_datetime(index_df['date'])
            return [index_df]
        raise


def run(
    symbol='000001',
    start=None,
    end=None,
    cash=100000,
    use_market_filter=True,
    strategy_id='swing',
    **strategy_params,
):
    """Run a backtest from the CLI."""
    start, end = resolve_date_range(start, end)
    resolved_strategy_id = _normalize_strategy_id(strategy_id)
    spec = get_strategy_spec(resolved_strategy_id)
    cerebro = bt.Cerebro()

    market_score_dict = None
    if use_market_filter:
        config = MarketConfig()
        try:
            score_df = get_market_score(start, end, config)
            market_score_dict = dict(
                zip(score_df['date'].dt.strftime('%Y%m%d'), score_df['total_score'])
            )
            print(
                f'Market score range: '
                f'{score_df["total_score"].min():.2f} ~ {score_df["total_score"].max():.2f}'
            )
        except Exception as exc:
            print(f'Market data load failed ({exc}), falling back to no filter mode')
            market_score_dict = None

    try:
        stock_df = load_market_data(symbol, start, end)
    except Exception as exc:
        print(f'Data load failed ({exc}), using synthetic data for demo backtest')
        stock_df = generate_synthetic_data(start=start, end=end)
        stock_df['date'] = pd.to_datetime(stock_df['date'])

    required_feed_frames = _load_cli_required_feed_frames(resolved_strategy_id, start, end)

    cerebro.adddata(bt.feeds.PandasData(dataname=stock_df, datetime=0))
    for frame in required_feed_frames:
        cerebro.adddata(bt.feeds.PandasData(dataname=frame, datetime=0))

    strategy_kwargs = dict(strategy_params)
    strategy_kwargs['market_score_dict'] = market_score_dict
    strategy_param_names = set(spec.strategy_class.params._getkeys())
    strategy_kwargs = {k: v for k, v in strategy_kwargs.items() if k in strategy_param_names}
    cerebro.addstrategy(spec.strategy_class, **strategy_kwargs)
    cerebro.broker.setcash(cash)

    print(f'Starting cash: {cerebro.broker.getcash():.2f}')
    cerebro.run()
    final_value = cerebro.broker.getvalue()
    print(f'Final value: {final_value:.2f}')
    print(f'Return: {(final_value / cash - 1) * 100:.2f}%')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run quant backtest')
    parser.add_argument('--symbol', default='000001', help='Stock symbol')
    parser.add_argument('--start', default=None, help='Start date YYYYMMDD')
    parser.add_argument('--end', default=None, help='End date YYYYMMDD')
    parser.add_argument('--cash', type=float, default=100000, help='Initial cash')
    parser.add_argument('--no-market-filter', action='store_true', help='Disable market filter')
    parser.add_argument(
        '--strategy',
        default='swing',
        choices=[
            'swing',
            'swing_ma_boll',
            'bollinger_reversal',
            'b1',
            'b1_strategy',
            'citic_wave',
        ],
        help='Strategy ID',
    )
    parser.add_argument('--short_ma', type=int, default=None, help='Short MA period')
    parser.add_argument('--long_ma', type=int, default=None, help='Long MA period')
    args = parser.parse_args()

    strategy_params = {}
    if args.short_ma is not None:
        strategy_params['short_ma'] = args.short_ma
    if args.long_ma is not None:
        strategy_params['long_ma'] = args.long_ma

    run(
        args.symbol,
        args.start,
        args.end,
        args.cash,
        use_market_filter=not args.no_market_filter,
        strategy_id=args.strategy,
        **strategy_params,
    )
