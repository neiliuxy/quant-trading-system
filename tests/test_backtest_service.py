import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest

from backtest.run_backtest import generate_synthetic_data
from backtest.service import BacktestRequest, run_backtest_service


class FakeHub:
    """In-memory DataHub stand-in for backtest.service tests."""

    def __init__(self, *args, **kwargs):
        self.frames: dict[tuple[str, str | None], pd.DataFrame] = {}
        self.requests: list = []

    def feed(self, dataset_type: str, frame: pd.DataFrame, symbol: str | None = None) -> None:
        self.frames[(dataset_type, symbol)] = frame

    def get_dataset(self, request):
        from datahub.models import DatasetResult
        self.requests.append(request)
        key = (request.dataset_type, request.symbol)
        if key in self.frames:
            frame = self.frames[key]
        elif (request.dataset_type, None) in self.frames:
            frame = self.frames[(request.dataset_type, None)]
        else:
            frame = pd.DataFrame()
        return DatasetResult(request=request, frame=frame.copy(), cache_hit=False)

    def resolve_feed_requests(self, feed_ids, start, end):
        from datahub.registry import request_for_feed_id
        return [request_for_feed_id(feed_id, start, end) for feed_id in feed_ids]


def _patch_hub(monkeypatch, hub: FakeHub) -> None:
    monkeypatch.setattr('backtest.service.DataHub', lambda *a, **kw: hub)


def test_run_backtest_service_returns_serializable_result(monkeypatch):
    df = generate_synthetic_data(start='20240101', end='20240630')
    hub = FakeHub()
    hub.feed('stock_daily', df)
    _patch_hub(monkeypatch, hub)

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
    hub = FakeHub()
    hub.feed('stock_daily', df)
    _patch_hub(monkeypatch, hub)
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

    hub = FakeHub()
    hub.feed('stock_daily', stock_df)
    hub.feed('index_daily', shanghai_df, symbol='sh000001')
    hub.feed('etf_daily', security_etf_df, symbol='sh512880')
    hub.feed('market_turnover', market_turnover_df)
    _patch_hub(monkeypatch, hub)

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


def test_cli_run_accepts_legacy_b1_strategy_alias(monkeypatch, capsys):
    import backtest.run_backtest as cli_backtest

    stock_df = generate_synthetic_data(start='20240101', end='20240630')
    index_df = stock_df.copy()

    monkeypatch.setattr(cli_backtest, 'load_market_data', lambda symbol, start, end: stock_df.copy())
    monkeypatch.setattr(
        cli_backtest,
        '_load_cli_required_feed_frames',
        lambda strategy_id, start, end: [index_df.copy()],
    )

    cli_backtest.run(
        symbol='600030',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=False,
        strategy_id='b1',
    )

    output = capsys.readouterr().out
    assert 'Final value:' in output


def test_cli_run_accepts_canonical_b1_strategy_id(monkeypatch, capsys):
    import backtest.run_backtest as cli_backtest

    stock_df = generate_synthetic_data(start='20240101', end='20240630')
    index_df = stock_df.copy()

    monkeypatch.setattr(cli_backtest, 'load_market_data', lambda symbol, start, end: stock_df.copy())
    monkeypatch.setattr(
        cli_backtest,
        '_load_cli_required_feed_frames',
        lambda strategy_id, start, end: [index_df.copy()],
    )

    cli_backtest.run(
        symbol='600030',
        start='20240101',
        end='20240630',
        cash=100000.0,
        use_market_filter=False,
        strategy_id='b1_strategy',
    )

    output = capsys.readouterr().out
    assert 'Final value:' in output


def test_market_filter_scores_are_exposed(monkeypatch):
    df = generate_synthetic_data(start='20240101', end='20240630')
    hub = FakeHub()
    hub.feed('stock_daily', df)
    _patch_hub(monkeypatch, hub)

    def fake_score(start, end, config):
        dates = pd.bdate_range(start=start, end=end)
        return pd.DataFrame({
            'date': dates,
            'trend_score': [0.5] * len(dates),
            'sentiment_score': [0.6] * len(dates),
            'volume_score': [0.7] * len(dates),
            'total_score': [0.6] * len(dates),
        })

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
    """index_daily 返回有效 DataFrame 时，result.index_data 应有 OHLCV+amount。"""
    from backtest.run_backtest import generate_synthetic_data
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

    hub = FakeHub()
    hub.feed('stock_daily', stock_df)
    hub.feed('index_daily', index_df, symbol='sh000001')
    _patch_hub(monkeypatch, hub)

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
    """index_daily 返回空 DataFrame 时，index_data 为空 list，不抛错。"""
    from backtest.run_backtest import generate_synthetic_data
    stock_df = generate_synthetic_data(start='20240101', end='20240630')
    hub = FakeHub()
    hub.feed('stock_daily', stock_df)
    hub.feed('index_daily', pd.DataFrame(), symbol='sh000001')
    _patch_hub(monkeypatch, hub)

    request = BacktestRequest(
        symbol='000001', start='20240101', end='20240630',
        cash=100000.0, use_market_filter=False,
    )
    result = run_backtest_service(request)

    assert result.index_data == []
    assert result.final_value > 0  # 回测本身成功


def test_run_backtest_service_loads_primary_feed_through_datahub(monkeypatch):
    import backtest.service as service

    stock_df = generate_synthetic_data(start='20240101', end='20240630')
    calls = []

    class FakeHub:
        def __init__(self, *args, **kwargs):
            pass

        def get_dataset(self, request):
            calls.append(request)
            from datahub.models import DatasetResult
            return DatasetResult(request=request, frame=stock_df.copy(), cache_hit=False)

        def resolve_feed_requests(self, feed_ids, start, end):
            return []

    monkeypatch.setattr(service, 'DataHub', FakeHub)
    monkeypatch.setattr(service, 'get_market_score', lambda *args, **kwargs: None)

    result = run_backtest_service(BacktestRequest(
        symbol='000001',
        start='20240101',
        end='20240630',
        use_market_filter=False,
    ))

    assert result.symbol == '000001'
    assert calls[0].dataset_type == 'stock_daily'
    assert calls[0].symbol == '000001'


def test_run_backtest_service_includes_risk_metrics(monkeypatch):
    stock_df = generate_synthetic_data(start='20200101', end='20221231')
    # 构造已知涨幅的指数 feed：首 close 3000，末 close 3300 → 基准 +10%
    index_df = generate_synthetic_data(start='20200101', end='20221231').copy()
    index_df['amount'] = 1e12
    index_df.loc[index_df.index[0], 'close'] = 3000.0
    index_df.loc[index_df.index[-1], 'close'] = 3300.0

    hub = FakeHub()
    hub.feed('stock_daily', stock_df)
    hub.feed('index_daily', index_df, symbol='sh000001')
    _patch_hub(monkeypatch, hub)

    request = BacktestRequest(
        symbol='000001',
        start='20200101',
        end='20221231',
        cash=100000.0,
        use_market_filter=False,
    )

    result = run_backtest_service(request)
    payload = result.to_dict()

    # 5 个新字段存在且为 float
    for key in ('sharpe', 'annual_return_pct', 'profit_loss_ratio',
                'benchmark_return_pct', 'excess_return_pct'):
        assert key in payload
        assert isinstance(payload[key], float)

    # 基准收益 = (3300/3000 - 1)*100 = 10%
    assert payload['benchmark_return_pct'] == pytest.approx(10.0)
    # 超额收益 = 策略收益 - 基准收益
    assert payload['excess_return_pct'] == pytest.approx(
        payload['total_return_pct'] - payload['benchmark_return_pct']
    )
