import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datahub.models import DatasetRequest, DataHubError
from datahub.normalize import normalize_frame
from datahub.registry import (
    get_dataset_spec,
    list_dataset_specs,
    request_for_feed_id,
)


def test_registry_lists_first_version_datasets():
    specs = {spec.dataset_type: spec for spec in list_dataset_specs()}

    assert set(specs) == {"stock_daily", "index_daily", "etf_daily", "market_turnover"}
    assert specs["stock_daily"].symbol_required is True
    assert specs["market_turnover"].symbol_required is False


def test_feed_ids_resolve_to_dataset_requests():
    assert request_for_feed_id("shanghai_index", "20240101", "20240131") == DatasetRequest(
        dataset_type="index_daily",
        symbol="sh000001",
        start="20240101",
        end="20240131",
    )
    assert request_for_feed_id("security_etf", "20240101", "20240131").symbol == "sh512880"
    assert request_for_feed_id("market_turnover", "20240101", "20240131").dataset_type == "market_turnover"


def test_unknown_feed_id_raises_structured_error():
    with pytest.raises(DataHubError) as excinfo:
        request_for_feed_id("unknown_feed", "20240101", "20240131")

    assert excinfo.value.error_type == "unsupported_dataset"


def test_normalize_frame_orders_columns_and_dates():
    raw = pd.DataFrame(
        {
            "close": [3.0],
            "date": ["2024-01-02"],
            "volume": [100.0],
            "low": [2.0],
            "high": [4.0],
            "open": [1.0],
        }
    )

    df = normalize_frame(raw, ["date", "open", "high", "low", "close", "volume"])

    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert df.loc[0, "date"].strftime("%Y%m%d") == "20240102"


def test_normalize_frame_rejects_missing_columns():
    raw = pd.DataFrame({"date": ["2024-01-02"], "close": [3.0]})

    with pytest.raises(DataHubError) as excinfo:
        normalize_frame(raw, ["date", "open", "high", "low", "close", "volume"])

    assert excinfo.value.error_type == "schema_invalid"
