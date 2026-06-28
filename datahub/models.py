from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


OHLCV_COLUMNS = ("date", "open", "high", "low", "close", "volume")
INDEX_COLUMNS = ("date", "open", "high", "low", "close", "volume", "amount")
STOCK_DAILY_COLUMNS = OHLCV_COLUMNS + ("amount",)
STOCK_PROFILE_COLUMNS = ("date", "code", "name", "is_st")
INDEX_CONSTITUENT_COLUMNS = ("date", "code", "weight")


class DataHubError(Exception):
    def __init__(self, error_type: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        payload = {"error_type": self.error_type, "message": self.message}
        payload.update(self.details)
        return payload


@dataclass(frozen=True)
class CachePolicy:
    ttl_seconds: int | None = 86400
    historical_ttl_seconds: int | None = None


@dataclass(frozen=True)
class DatasetRequest:
    dataset_type: str
    start: str
    end: str
    symbol: str | None = None
    frequency: str = "daily"
    force_refresh: bool = False

    @property
    def cache_key(self) -> str:
        force = "true" if self.force_refresh else "false"
        symbol = self.symbol or "global"
        return f"{self.dataset_type}:{symbol}:{self.frequency}:{self.start}:{self.end}:{force}"

    @property
    def data_key(self) -> str:
        symbol = self.symbol or "global"
        return f"{self.dataset_type}:{symbol}:{self.frequency}:{self.start}:{self.end}"


@dataclass(frozen=True)
class DatasetSpec:
    dataset_type: str
    label: str
    columns: tuple[str, ...]
    cache_policy: CachePolicy
    source_name: str
    symbol_required: bool = False


@dataclass
class DatasetResult:
    request: DatasetRequest
    frame: pd.DataFrame
    cache_hit: bool
    cache_path: str | None = None
    source_name: str | None = None
