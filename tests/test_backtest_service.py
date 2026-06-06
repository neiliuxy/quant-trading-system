import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from backtest.run_backtest import generate_synthetic_data
from backtest.service import BacktestRequest, run_backtest_service


def test_run_backtest_service_returns_serializable_result(monkeypatch):
    df = generate_synthetic_data(start='20240101', end='20240630')

    def fake_loader(symbol, start, end):
        return df.copy()

    monkeypatch.setattr('backtest.service.load_market_data', fake_loader)
    request = BacktestRequest(
        symbol='000001',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=False,
    )

    result = run_backtest_service(request)

    payload = result.to_dict()
    assert payload['symbol'] == '000001'
    assert payload['start'] == '20240101'
    assert payload['end'] == '20240630'
    assert payload['initial_cash'] == 100000.0
    assert 'final_value' in payload
    assert 'total_return_pct' in payload
    assert isinstance(payload['equity_curve'], list)
    assert len(payload['equity_curve']) > 20
    assert payload['equity_curve'][0]['date'].isdigit()


def test_run_backtest_service_accepts_strategy_params(monkeypatch):
    from backtest.run_backtest import generate_synthetic_data
    df = generate_synthetic_data(start='20240101', end='20240630')
    monkeypatch.setattr('backtest.service.load_market_data', lambda symbol, start, end: df.copy())
    request = BacktestRequest(
        symbol='000001',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=False,
        strategy_id='bollinger_reversal',
        strategy_params={'boll_period': 20, 'boll_devfactor': 2.0},
    )
    result = run_backtest_service(request)
    assert result.symbol == '000001'


def test_run_backtest_service_adds_required_feeds_for_citic_wave(monkeypatch):
    stock_df = generate_synthetic_data(start='20240101', end='20240630')
    shanghai_df = stock_df.copy()
    shanghai_df['amount'] = 3e12
    security_etf_df = stock_df.copy()
    security_etf_df['amount'] = 0.0
    market_turnover_df = stock_df.copy()

    monkeypatch.setattr('backtest.service.load_market_data', lambda symbol, start, end: stock_df.copy())
    monkeypatch.setattr('backtest.service.load_shanghai_composite', lambda start, end: shanghai_df.copy())
    monkeypatch.setattr('backtest.service.load_security_etf_data', lambda start, end: security_etf_df.copy())
    monkeypatch.setattr('backtest.service.load_market_turnover_data', lambda start, end: market_turnover_df.copy())

    request = BacktestRequest(
        symbol='600030',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=False,
        strategy_id='citic_wave',
    )

    result = run_backtest_service(request)

    assert result.symbol == '600030'
    assert result.final_value > 0


def test_market_filter_scores_are_exposed(monkeypatch):
    df = generate_synthetic_data(start='20240101', end='20240630')

    def fake_loader(symbol, start, end):
        return df.copy()

    def fake_score(start, end, config):
        dates = pd.bdate_range(start=start, end=end)
        return pd.DataFrame({
            'date': dates,
            'trend_score': [0.5] * len(dates),
            'sentiment_score': [0.6] * len(dates),
            'volume_score': [0.7] * len(dates),
            'total_score': [0.6] * len(dates),
        })

    monkeypatch.setattr('backtest.service.load_market_data', fake_loader)
    monkeypatch.setattr('backtest.service.get_market_score', fake_score)

    request = BacktestRequest(
        symbol='000001',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=True,
    )

    result = run_backtest_service(request)

    assert result.market_score_summary['min'] == 0.6
    assert result.market_score_summary['max'] == 0.6
    assert len(result.market_scores) > 20


def test_index_data_is_populated_when_loader_returns_df(monkeypatch):
    """load_shanghai_composite 返回有效 DataFrame 时，result.index_data 应有 OHLCV+amount。"""
    from backtest.run_backtest import generate_synthetic_data
    from datetime import datetime
    import pandas as pd

    stock_df = generate_synthetic_data(start='20240101', end='20240630')

    dates = pd.date_range('20240101', periods=len(stock_df), freq='B')
    index_df = pd.DataFrame({
        'date': dates,
        'open': [3000.0] * len(stock_df),
        'high': [3050.0] * len(stock_df),
        'low':  [2980.0] * len(stock_df),
        'close':[3020.0] * len(stock_df),
        'volume': [1e9] * len(stock_df),
        'amount': [3e12] * len(stock_df),
    })

    monkeypatch.setattr('backtest.service.load_market_data', lambda s, st, e: stock_df.copy())
    monkeypatch.setattr('backtest.service.load_shanghai_composite', lambda st, e: index_df.copy())

    request = BacktestRequest(
        symbol='000001', start='20240101', end='20240630',
        cash=100000.0, use_market_filter=False,
    )
    result = run_backtest_service(request)

    assert result.index_data, 'index_data should be populated'
    assert len(result.index_data) == len(stock_df)
    first = result.index_data[0]
    assert set(first.keys()) == {'date', 'open', 'high', 'low', 'close', 'volume', 'amount'}
    assert first['date'].isdigit() and len(first['date']) == 8
    assert first['amount'] == 3e12


def test_index_data_empty_when_loader_returns_none(monkeypatch):
    """load_shanghai_composite 返回 None 时，index_data 为空 list，不抛错。"""
    from backtest.run_backtest import generate_synthetic_data
    stock_df = generate_synthetic_data(start='20240101', end='20240630')
    monkeypatch.setattr('backtest.service.load_market_data', lambda s, st, e: stock_df.copy())
    monkeypatch.setattr('backtest.service.load_shanghai_composite', lambda st, e: None)

    request = BacktestRequest(
        symbol='000001', start='20240101', end='20240630',
        cash=100000.0, use_market_filter=False,
    )
    result = run_backtest_service(request)

    assert result.index_data == []
    assert result.final_value > 0  # 回测本身成功
