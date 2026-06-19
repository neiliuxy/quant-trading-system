import os
import sys
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datahub.models import OHLCV_COLUMNS, CachePolicy, DatasetRequest, DatasetSpec
from datahub.service import DataHub
from server.db import init_db


def _frame():
    return pd.DataFrame(
        {
            "date": ["2024-01-02"],
            "open": [1.0],
            "high": [2.0],
            "low": [0.5],
            "close": [1.5],
            "volume": [100.0],
        }
    )


class FixtureSource:
    name = "fixture"

    def __init__(self):
        self.calls = 0

    def fetch(self, request):
        self.calls += 1
        return _frame()


def test_get_dataset_fetches_then_reads_cache(tmp_path):
    conn = init_db(str(tmp_path / "quantx.sqlite"))
    source = FixtureSource()
    hub = DataHub(root_dir=str(tmp_path), conn=conn, source=source)
    request = DatasetRequest("stock_daily", symbol="000001", start="20240101", end="20240131")

    first = hub.get_dataset(request)
    second = hub.get_dataset(request)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert source.calls == 1


def test_create_refresh_returns_cache_hit_for_existing_cache(tmp_path):
    conn = init_db(str(tmp_path / "quantx.sqlite"))
    source = FixtureSource()
    hub = DataHub(root_dir=str(tmp_path), conn=conn, source=source)
    request = DatasetRequest("stock_daily", symbol="000001", start="20240101", end="20240131")
    hub.get_dataset(request)

    refresh = hub.create_refresh(request)

    assert refresh["status"] == "completed"
    assert refresh["cache_hit"] == 1


def test_historical_cache_record_has_no_expires_at(tmp_path):
    conn = init_db(str(tmp_path / "quantx.sqlite"))
    source = FixtureSource()
    hub = DataHub(root_dir=str(tmp_path), conn=conn, source=source)
    request = DatasetRequest("stock_daily", symbol="000001", start="20240101", end="20240131")
    hub.get_dataset(request)

    rows = hub.list_cache(dataset_type="stock_daily", symbol="000001")
    assert len(rows) == 1
    assert rows[0]["expires_at"] is None


def test_compute_expires_at_honors_historical_ttl_policy():
    historical_request = DatasetRequest(
        "stock_daily", symbol="000001", start="20240101", end="20240131"
    )
    future_request = DatasetRequest(
        "stock_daily", symbol="000001", start="20991201", end="20991231"
    )

    spec_default = DatasetSpec(
        dataset_type="stock_daily",
        label="Stock",
        columns=OHLCV_COLUMNS,
        cache_policy=CachePolicy(ttl_seconds=3600, historical_ttl_seconds=None),
        source_name="fixture",
        symbol_required=True,
    )
    assert DataHub._compute_expires_at(historical_request, spec_default) is None
    assert DataHub._compute_expires_at(future_request, spec_default) is not None

    spec_with_historical = DatasetSpec(
        dataset_type="stock_daily",
        label="Stock",
        columns=OHLCV_COLUMNS,
        cache_policy=CachePolicy(ttl_seconds=3600, historical_ttl_seconds=7200),
        source_name="fixture",
        symbol_required=True,
    )
    historical_expires = DataHub._compute_expires_at(
        historical_request, spec_with_historical
    )
    assert historical_expires is not None
    parsed = datetime.strptime(historical_expires, "%Y-%m-%dT%H:%M:%S")
    delta = parsed - datetime.now()
    assert timedelta(seconds=7100) <= delta <= timedelta(seconds=7300)
