import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datahub.models import DatasetRequest
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
