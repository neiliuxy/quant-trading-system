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
