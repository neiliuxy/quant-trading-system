import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datahub.cache import CacheStore
from datahub.models import CachePolicy, DatasetRequest, DatasetSpec, OHLCV_COLUMNS


def _spec():
    return DatasetSpec(
        dataset_type="stock_daily",
        label="Stock",
        columns=OHLCV_COLUMNS,
        cache_policy=CachePolicy(ttl_seconds=86400, historical_ttl_seconds=None),
        source_name="fixture",
        symbol_required=True,
    )


def _frame(dates):
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": [1.0] * len(dates),
            "high": [2.0] * len(dates),
            "low": [0.5] * len(dates),
            "close": [1.5] * len(dates),
            "volume": [100.0] * len(dates),
        }
    )


def test_reads_legacy_cache_and_trims_to_requested_range(tmp_path):
    cache = CacheStore(str(tmp_path))
    _frame(["2024-01-01", "2024-01-02", "2024-01-03"]).to_csv(
        tmp_path / "000001_平安银行_20240101_20240103.csv",
        index=False,
    )
    request = DatasetRequest("stock_daily", symbol="000001", start="20240102", end="20240103")

    hit = cache.read(request, _spec())

    assert hit is not None
    assert hit.frame["date"].dt.strftime("%Y%m%d").tolist() == ["20240102", "20240103"]


def test_prefers_narrowest_covering_cache(tmp_path):
    cache = CacheStore(str(tmp_path))
    _frame(["2024-01-01", "2024-01-02", "2024-01-03"]).to_csv(
        tmp_path / "000001_big_20240101_20240103.csv",
        index=False,
    )
    _frame(["2024-01-02", "2024-01-03"]).to_csv(
        tmp_path / "000001_small_20240102_20240103.csv",
        index=False,
    )
    request = DatasetRequest("stock_daily", symbol="000001", start="20240102", end="20240103")

    hit = cache.read(request, _spec())

    assert hit is not None
    assert "small" in hit.cache_path


def test_writes_new_layout_atomically(tmp_path):
    cache = CacheStore(str(tmp_path))
    request = DatasetRequest("stock_daily", symbol="000001", start="20240101", end="20240102")

    path = cache.write(request, _spec(), _frame(["2024-01-01", "2024-01-02"]))

    assert path.endswith("data/cache/stock_daily/000001_20240101_20240102.csv")
    assert os.path.exists(path)
    assert not list((tmp_path / "data" / "cache" / "stock_daily").glob("*.tmp"))


def test_force_refresh_write_extends_to_existing_broader_cache(tmp_path):
    cache = CacheStore(str(tmp_path))
    _frame(["2024-01-01", "2024-01-02", "2024-01-03"]).to_csv(
        tmp_path / "000001_20240101_20240103.csv",
        index=False,
    )
    request = DatasetRequest(
        "stock_daily",
        symbol="000001",
        start="20240102",
        end="20240103",
        force_refresh=True,
    )

    path = cache.path_for_write(request, _spec())

    assert path.endswith("000001_20240101_20240103.csv")
