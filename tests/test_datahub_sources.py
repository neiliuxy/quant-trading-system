import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datahub.models import DatasetRequest
from datahub.sources import AkshareSource, _AKSHARE_COLUMN_MAP, _fetch_sse_turnover


def test_stock_daily_uses_tencent_fallback_when_eastmoney_fails(monkeypatch):
    source = AkshareSource()
    calls = {"eastmoney": 0, "tencent": 0}

    def fail_eastmoney(**kwargs):
        calls["eastmoney"] += 1
        raise RuntimeError("eastmoney down")

    def tencent(**kwargs):
        calls["tencent"] += 1
        return pd.DataFrame(
            {
                "date": ["2024-01-02"],
                "open": [1.0],
                "high": [2.0],
                "low": [0.5],
                "close": [1.5],
                "amount": [100.0],
            }
        )

    monkeypatch.setattr("datahub.sources.ak.stock_zh_a_hist", fail_eastmoney)
    monkeypatch.setattr("datahub.sources.ak.stock_zh_a_hist_tx", tencent)
    monkeypatch.setattr("datahub.sources.time.sleep", lambda seconds: None)

    df = source.fetch(DatasetRequest("stock_daily", symbol="000001", start="20240101", end="20240131"))

    assert calls == {"eastmoney": 3, "tencent": 1}
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert df.loc[0, "volume"] == 100.0


def test_index_daily_adds_amount_when_missing(monkeypatch):
    source = AkshareSource()
    monkeypatch.setattr(
        "datahub.sources.ak.stock_zh_index_daily",
        lambda symbol: pd.DataFrame(
            {
                "date": ["2024-01-02"],
                "open": [3000.0],
                "high": [3010.0],
                "low": [2990.0],
                "close": [3005.0],
                "volume": [10.0],
            }
        ),
    )

    df = source.fetch(DatasetRequest("index_daily", symbol="sh000001", start="20240101", end="20240131"))

    assert "amount" in df.columns
    assert df.loc[0, "amount"] == 3005.0 * 10.0 * 100


def test_market_turnover_skips_days_with_missing_turnover(monkeypatch):
    """Preserves existing behavior: days where turnover is unavailable are skipped."""
    source = AkshareSource()
    index_df = pd.DataFrame(
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
    monkeypatch.setattr(
        "datahub.sources.ak.stock_zh_index_daily",
        lambda symbol: index_df.copy(),
    )
    # 20240102 has both; 20240103 has no SSE turnover -> skipped
    sse = {"20240102": 100.0, "20240103": None}
    szse = {"20240102": 40.0, "20240103": 50.0}
    monkeypatch.setattr(
        "datahub.sources._fetch_sse_turnover",
        lambda date_text: sse[date_text],
    )
    monkeypatch.setattr(
        "datahub.sources._fetch_szse_turnover",
        lambda date_text: szse[date_text],
    )
    monkeypatch.setattr("datahub.sources.time.sleep", lambda seconds: None)

    df = source.fetch(DatasetRequest("market_turnover", start="20240101", end="20240131"))

    assert df["date"].dt.strftime("%Y%m%d").tolist() == ["20240102"]
    assert df.loc[0, "close"] == 140.0


def test_fetch_sse_turnover_returns_none_on_empty_akshare_data(monkeypatch):
    """akshare 对空 result 抛 Length mismatch 时，_fetch_sse_turnover 容错返回 None。"""
    def raise_length_mismatch(date):
        raise ValueError("Length mismatch: Expected axis has 1 elements, new values have 6 elements")

    monkeypatch.setattr("datahub.sources.ak.stock_sse_deal_daily", raise_length_mismatch)

    assert _fetch_sse_turnover("20210617") is None


def test_empty_data_error_does_not_retry(monkeypatch):
    """空数据（Length mismatch）是确定性错误，必须立即跳过、不重试。"""
    calls = {"n": 0}

    def boom(date):
        calls["n"] += 1
        raise ValueError("Length mismatch: Expected axis has 1 elements, new values have 6 elements")

    monkeypatch.setattr("datahub.sources.ak.stock_sse_deal_daily", boom)

    assert _fetch_sse_turnover("20210617") is None
    assert calls["n"] == 1  # 只调一次，无重试


def test_network_error_does_retry(monkeypatch):
    """SSL/网络类偶发错误应重试（区别于确定性的空数据错误）。"""
    calls = {"n": 0}

    def flaky(date):
        calls["n"] += 1
        raise ConnectionError("SSL: UNEXPECTED_EOF_WHILE_READING")

    monkeypatch.setattr("datahub.sources.ak.stock_sse_deal_daily", flaky)
    monkeypatch.setattr("datahub.sources.time.sleep", lambda s: None)  # 跳过 sleep 加速测试

    assert _fetch_sse_turnover("20240102") is None
    assert calls["n"] == 3  # 重试满 3 次


def test_akshare_amount_mapping_exists():
    assert _AKSHARE_COLUMN_MAP["成交额"] == "amount"
