import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import data_loader


class _LoaderFakeHub:
    """In-memory DataHub stand-in for data_loader wrapper tests."""

    def __init__(self, *args, **kwargs):
        self.frames: dict[tuple[str, str | None], pd.DataFrame] = {}

    def feed(self, dataset_type: str, frame: pd.DataFrame, symbol: str | None = None) -> None:
        self.frames[(dataset_type, symbol)] = frame

    def get_dataset(self, request):
        from datahub.models import DatasetResult
        for key in [(request.dataset_type, request.symbol), (request.dataset_type, None)]:
            if key in self.frames:
                return DatasetResult(request=request, frame=self.frames[key].copy(), cache_hit=False)
        return DatasetResult(request=request, frame=pd.DataFrame(), cache_hit=False)


def test_load_security_etf_data_normalizes_index_columns(monkeypatch, tmp_path):
    sample = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [1.0, 1.1],
            "high": [1.2, 1.3],
            "low": [0.9, 1.0],
            "close": [1.1, 1.2],
            "volume": [1000.0, 1100.0],
            "amount": [0.0, 0.0],
        }
    )

    hub = _LoaderFakeHub()
    hub.feed("etf_daily", sample, symbol="sh512880")
    monkeypatch.setattr(data_loader, "DataHub", lambda *a, **kw: hub)

    df = data_loader.load_security_etf_data("20240101", "20240131")

    assert list(df.columns) == data_loader.INDEX_STANDARD_COLUMNS
    assert df["date"].dt.strftime("%Y%m%d").tolist() == ["20240102", "20240103"]
    assert df["amount"].tolist() == [0.0, 0.0]


def test_load_market_turnover_data_returns_price_like_frame(monkeypatch):
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [140.0, 160.0],
            "high": [140.0, 160.0],
            "low": [140.0, 160.0],
            "close": [140.0, 160.0],
            "volume": [0.0, 0.0],
        }
    )

    hub = _LoaderFakeHub()
    hub.feed("market_turnover", frame)
    monkeypatch.setattr(data_loader, "DataHub", lambda *a, **kw: hub)

    df = data_loader.load_market_turnover_data("20240102", "20240103")

    assert list(df.columns) == data_loader.STANDARD_COLUMNS
    assert df["date"].dt.strftime("%Y%m%d").tolist() == ["20240102", "20240103"]
    assert df["open"].tolist() == [140.0, 160.0]
    assert df["close"].tolist() == [140.0, 160.0]
    assert df["volume"].tolist() == [0.0, 0.0]


def test_load_market_turnover_data_uses_trading_dates_only(monkeypatch):
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-02-08", "2024-02-19"]),
            "open": [100.0, 200.0],
            "high": [100.0, 200.0],
            "low": [100.0, 200.0],
            "close": [100.0, 200.0],
            "volume": [0.0, 0.0],
        }
    )

    hub = _LoaderFakeHub()
    hub.feed("market_turnover", frame)
    monkeypatch.setattr(data_loader, "DataHub", lambda *a, **kw: hub)

    df = data_loader.load_market_turnover_data("20240208", "20240219")

    assert df["date"].dt.strftime("%Y%m%d").tolist() == ["20240208", "20240219"]


def test_read_cached_frame_accepts_equivalent_columns_and_reorders(tmp_path):
    cache_path = tmp_path / "cached.csv"
    pd.DataFrame(
        {
            "close": [3.0],
            "date": ["2024-01-02"],
            "volume": [4.0],
            "low": [2.0],
            "amount": [5.0],
            "high": [6.0],
            "open": [1.0],
        }
    ).to_csv(cache_path, index=False)

    df = data_loader._read_cached_frame(str(cache_path), data_loader.INDEX_STANDARD_COLUMNS)

    assert df is not None
    assert list(df.columns) == data_loader.INDEX_STANDARD_COLUMNS
    assert df.loc[0, "date"].strftime("%Y%m%d") == "20240102"


def test_load_market_turnover_skips_days_with_missing_data(monkeypatch):
    """Loader 返回的 turnover 帧已剔除缺数日，包装函数原样透传。"""
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [140.0, 160.0],
            "high": [140.0, 160.0],
            "low": [140.0, 160.0],
            "close": [140.0, 160.0],
            "volume": [0.0, 0.0],
        }
    )
    hub = _LoaderFakeHub()
    hub.feed("market_turnover", frame)
    monkeypatch.setattr(data_loader, "DataHub", lambda *a, **kw: hub)

    df = data_loader.load_market_turnover_data("20210617", "20240103")

    assert df["date"].dt.strftime("%Y%m%d").tolist() == ["20240102", "20240103"]
    assert df["close"].tolist() == [140.0, 160.0]


def test_fetch_sse_turnover_returns_none_on_empty_akshare_data(monkeypatch):
    """akshare 对空 result 抛 Length mismatch 时，_fetch_sse_turnover 容错返回 None。"""
    def raise_length_mismatch(date):
        raise ValueError("Length mismatch: Expected axis has 1 elements, new values have 6 elements")

    monkeypatch.setattr(data_loader.ak, "stock_sse_deal_daily", raise_length_mismatch)

    assert data_loader._fetch_sse_turnover("20210617") is None


def test_empty_data_error_does_not_retry(monkeypatch):
    """空数据（Length mismatch）是确定性错误，必须立即跳过、不重试，否则早期年份逐日卡 6 秒。"""
    calls = {"n": 0}

    def boom(date):
        calls["n"] += 1
        raise ValueError("Length mismatch: Expected axis has 1 elements, new values have 6 elements")

    monkeypatch.setattr(data_loader.ak, "stock_sse_deal_daily", boom)

    assert data_loader._fetch_sse_turnover("20210617") is None
    assert calls["n"] == 1  # 只调一次，无重试


def test_network_error_does_retry(monkeypatch):
    """SSL/网络类偶发错误应重试（区别于确定性的空数据错误）。"""
    calls = {"n": 0}

    def flaky(date):
        calls["n"] += 1
        raise ConnectionError("SSL: UNEXPECTED_EOF_WHILE_READING")

    monkeypatch.setattr(data_loader.ak, "stock_sse_deal_daily", flaky)
    monkeypatch.setattr(data_loader.time, "sleep", lambda s: None)  # 跳过 sleep 加速测试

    assert data_loader._fetch_sse_turnover("20240102") is None
    assert calls["n"] == 3  # 重试满 3 次


def test_load_market_data_wrapper_matches_datahub_result(monkeypatch, tmp_path):
    from datahub.models import DatasetResult, DatasetRequest

    expected = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [1.0, 2.0],
            "high": [1.5, 2.5],
            "low": [0.5, 1.5],
            "close": [1.2, 2.2],
            "volume": [100.0, 200.0],
        }
    )

    seen = {}

    class FakeHub:
        def __init__(self, *args, **kwargs):
            pass

        def get_dataset(self, request):
            seen["request"] = request
            return DatasetResult(request=request, frame=expected.copy(), cache_hit=False)

    monkeypatch.setattr(data_loader, "DataHub", FakeHub)

    df = data_loader.load_market_data("000001", "20240101", "20240131")

    assert seen["request"] == DatasetRequest(
        dataset_type="stock_daily", symbol="000001", start="20240101", end="20240131",
    )
    assert list(df.columns) == data_loader.STANDARD_COLUMNS
    assert df["date"].dt.strftime("%Y%m%d").tolist() == ["20240102", "20240103"]
    assert df["close"].tolist() == [1.2, 2.2]
