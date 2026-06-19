from __future__ import annotations

from datahub.models import CachePolicy, DatasetRequest, DatasetSpec, DataHubError, INDEX_COLUMNS, OHLCV_COLUMNS


_SPECS = {
    "stock_daily": DatasetSpec(
        dataset_type="stock_daily",
        label="A-share daily bars",
        columns=OHLCV_COLUMNS,
        cache_policy=CachePolicy(ttl_seconds=86400, historical_ttl_seconds=None),
        source_name="akshare",
        symbol_required=True,
    ),
    "index_daily": DatasetSpec(
        dataset_type="index_daily",
        label="Index daily bars",
        columns=INDEX_COLUMNS,
        cache_policy=CachePolicy(ttl_seconds=86400, historical_ttl_seconds=None),
        source_name="akshare",
        symbol_required=True,
    ),
    "etf_daily": DatasetSpec(
        dataset_type="etf_daily",
        label="ETF daily bars",
        columns=INDEX_COLUMNS,
        cache_policy=CachePolicy(ttl_seconds=86400, historical_ttl_seconds=None),
        source_name="akshare",
        symbol_required=True,
    ),
    "market_turnover": DatasetSpec(
        dataset_type="market_turnover",
        label="Two-market turnover",
        columns=OHLCV_COLUMNS,
        cache_policy=CachePolicy(ttl_seconds=86400, historical_ttl_seconds=None),
        source_name="akshare",
        symbol_required=False,
    ),
}

_FEED_MAP = {
    "shanghai_index": ("index_daily", "sh000001"),
    "security_etf": ("etf_daily", "sh512880"),
    "market_turnover": ("market_turnover", None),
}


def list_dataset_specs() -> list[DatasetSpec]:
    return list(_SPECS.values())


def get_dataset_spec(dataset_type: str) -> DatasetSpec:
    try:
        return _SPECS[dataset_type]
    except KeyError as exc:
        raise DataHubError("unsupported_dataset", f"Unknown dataset type: {dataset_type}") from exc


def request_for_feed_id(feed_id: str, start: str, end: str) -> DatasetRequest:
    if feed_id not in _FEED_MAP:
        raise DataHubError("unsupported_dataset", f"Unknown required feed: {feed_id}")
    dataset_type, symbol = _FEED_MAP[feed_id]
    return DatasetRequest(dataset_type=dataset_type, symbol=symbol, start=start, end=end)
