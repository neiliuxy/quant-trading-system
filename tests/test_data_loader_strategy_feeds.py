import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import data_loader


def test_load_security_etf_data_normalizes_index_columns(monkeypatch, tmp_path):
    monkeypatch.setattr(data_loader, "_CACHE_DIR", str(tmp_path))

    sample = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "open": [1.0, 1.1],
            "high": [1.2, 1.3],
            "low": [0.9, 1.0],
            "close": [1.1, 1.2],
            "volume": [1000.0, 1100.0],
        }
    )

    monkeypatch.setattr(data_loader.ak, "fund_etf_hist_sina", lambda symbol: sample.copy())

    assert hasattr(data_loader, "load_security_etf_data")

    df = data_loader.load_security_etf_data("20240101", "20240131")

    assert list(df.columns) == data_loader.INDEX_STANDARD_COLUMNS
    assert df["date"].dt.strftime("%Y%m%d").tolist() == ["20240102", "20240103"]
    assert df["amount"].tolist() == [0.0, 0.0]
    assert len(list(tmp_path.glob("sh512880_*.csv"))) == 1


def test_load_market_turnover_data_returns_price_like_frame(monkeypatch, tmp_path):
    monkeypatch.setattr(data_loader, "_CACHE_DIR", str(tmp_path))
    sse_values = {"20240102": 100.0, "20240103": 110.0}
    szse_values = {"20240102": 40.0, "20240103": 50.0}
    trading_dates = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [1.0, 1.0],
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
            "volume": [1.0, 1.0],
            "amount": [1.0, 1.0],
        }
    )

    monkeypatch.setattr(data_loader, "load_shanghai_composite", lambda start, end: trading_dates.copy())

    monkeypatch.setattr(
        data_loader,
        "_fetch_sse_turnover",
        lambda date_text: sse_values[date_text],
        raising=False,
    )
    monkeypatch.setattr(
        data_loader,
        "_fetch_szse_turnover",
        lambda date_text: szse_values[date_text],
        raising=False,
    )

    assert hasattr(data_loader, "load_market_turnover_data")

    df = data_loader.load_market_turnover_data("20240102", "20240103")

    assert list(df.columns) == data_loader.STANDARD_COLUMNS
    assert df["date"].dt.strftime("%Y%m%d").tolist() == ["20240102", "20240103"]
    assert df["open"].tolist() == [140.0, 160.0]
    assert df["high"].tolist() == [140.0, 160.0]
    assert df["low"].tolist() == [140.0, 160.0]
    assert df["close"].tolist() == [140.0, 160.0]
    assert df["volume"].tolist() == [0.0, 0.0]
    assert len(list(tmp_path.glob("market_turnover_*.csv"))) == 1


def test_load_market_turnover_data_uses_trading_dates_only(monkeypatch, tmp_path):
    monkeypatch.setattr(data_loader, "_CACHE_DIR", str(tmp_path))
    trading_dates = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-02-08", "2024-02-19"]),
            "open": [1.0, 1.0],
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
            "volume": [1.0, 1.0],
            "amount": [1.0, 1.0],
        }
    )
    requested_sse_dates = []
    requested_szse_dates = []

    monkeypatch.setattr(data_loader, "load_shanghai_composite", lambda start, end: trading_dates.copy())
    monkeypatch.setattr(
        data_loader,
        "_fetch_sse_turnover",
        lambda date_text: requested_sse_dates.append(date_text) or 100.0,
    )
    monkeypatch.setattr(
        data_loader,
        "_fetch_szse_turnover",
        lambda date_text: requested_szse_dates.append(date_text) or 50.0,
    )

    df = data_loader.load_market_turnover_data("20240208", "20240219")

    assert requested_sse_dates == ["20240208", "20240219"]
    assert requested_szse_dates == ["20240208", "20240219"]
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
