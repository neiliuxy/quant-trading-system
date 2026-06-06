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
