# DataHub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first DataHub version so backtest orchestration and compatibility loaders resolve market data through a central data platform with cache metadata, refresh APIs, and bounded refresh execution.

**Architecture:** Add an in-process `datahub/` package with typed dataset specs, normalization, dual-layout CSV cache lookup, AkShare source adapters, SQLite metadata, and a bounded refresh executor. FastAPI exposes management endpoints; backtest orchestration uses `DataHub` for primary and required feeds while legacy `backtest.data_loader` functions remain as wrappers for scripts.

**Tech Stack:** Python 3, pandas, AkShare, SQLite, FastAPI, Backtrader, pytest.

---

## File Map

- Create `datahub/__init__.py`: package exports.
- Create `datahub/models.py`: dataclasses and error types.
- Create `datahub/registry.py`: dataset specs and feed-ID resolution.
- Create `datahub/normalize.py`: date and schema normalization.
- Create `datahub/cache.py`: dual-layout cache discovery, TTL checks, per-key locks, atomic writes.
- Create `datahub/sources.py`: AkShare source adapters preserving retry/fallback behavior.
- Create `datahub/metadata.py`: SQLite refresh/cache metadata helpers.
- Create `datahub/executor.py`: bounded refresh executor using worker-owned DB connections.
- Create `datahub/service.py`: DataHub orchestration and refresh workflow.
- Modify `server/db.py`: add `busy_timeout` and DataHub tables.
- Modify `server/models.py`: add DataHub API request/response models.
- Modify `server/api.py`: add `/api/data/*` endpoints.
- Modify `backtest/service.py`: route primary and required feeds through DataHub.
- Modify `backtest/run_backtest.py`: use DataHub path where safe while preserving CLI synthetic fallback.
- Modify `backtest/data_loader.py`: turn public loader functions into compatibility wrappers.
- Test `tests/test_datahub_*.py`: unit tests for registry, normalization, cache, metadata, service, executor.
- Modify `tests/test_server_api.py`: DataHub endpoint tests.
- Modify `tests/test_backtest_service.py`: DataHub orchestration tests.
- Modify `tests/test_data_loader_strategy_feeds.py`: compatibility wrapper golden tests.

---

### Task 1: SQLite Metadata Foundation

**Files:**
- Modify: `server/db.py`
- Create: `datahub/metadata.py`
- Test: `tests/test_datahub_metadata.py`

- [ ] **Step 1: Write failing metadata tests**

Create `tests/test_datahub_metadata.py`:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.db import init_db
from datahub.metadata import (
    create_cache_record,
    create_refresh_record,
    get_refresh_record,
    list_cache_records,
    mark_refresh_completed,
    mark_refresh_failed,
)


def test_init_db_creates_datahub_tables_and_busy_timeout(tmp_path):
    conn = init_db(str(tmp_path / "quantx.sqlite"))

    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert "datahub_cache" in tables
    assert "datahub_refreshes" in tables
    assert busy_timeout >= 5000


def test_cache_and_refresh_metadata_roundtrip(tmp_path):
    conn = init_db(str(tmp_path / "quantx.sqlite"))

    cache = create_cache_record(
        conn,
        dataset_type="stock_daily",
        symbol="000001",
        frequency="daily",
        start_date="20240101",
        end_date="20240131",
        file_path="/tmp/000001.csv",
        row_count=22,
        schema_version="ohlcv-v1",
        source_name="fixture",
        expires_at=None,
    )
    refresh = create_refresh_record(
        conn,
        request_key="stock_daily:000001:daily:20240101:20240131:false",
        dataset_type="stock_daily",
        symbol="000001",
        frequency="daily",
        start_date="20240101",
        end_date="20240131",
        force_refresh=False,
        status="queued",
    )
    mark_refresh_completed(
        conn,
        refresh["id"],
        cache_hit=False,
        output_cache_path="/tmp/000001.csv",
    )

    rows = list_cache_records(conn, dataset_type="stock_daily", symbol="000001")
    saved_refresh = get_refresh_record(conn, refresh["id"])

    assert rows[0]["id"] == cache["id"]
    assert saved_refresh["status"] == "completed"
    assert saved_refresh["cache_hit"] == 0


def test_mark_refresh_failed_records_error(tmp_path):
    conn = init_db(str(tmp_path / "quantx.sqlite"))
    refresh = create_refresh_record(
        conn,
        request_key="index_daily:sh000001:daily:20240101:20240131:false",
        dataset_type="index_daily",
        symbol="sh000001",
        frequency="daily",
        start_date="20240101",
        end_date="20240131",
        force_refresh=False,
        status="running",
    )

    mark_refresh_failed(
        conn,
        refresh["id"],
        error_type="source_unavailable",
        error_message="fixture failure",
    )

    saved = get_refresh_record(conn, refresh["id"])
    assert saved["status"] == "failed"
    assert saved["error_type"] == "source_unavailable"
    assert saved["error_message"] == "fixture failure"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest -q tests/test_datahub_metadata.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'datahub'` or missing metadata functions.

- [ ] **Step 3: Add SQLite schema and busy timeout**

Modify `server/db.py`:

```python
def connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn
```

Add these tables to the `init_db` executescript after `job_results`:

```sql
CREATE TABLE IF NOT EXISTS datahub_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_type TEXT NOT NULL,
    symbol TEXT,
    frequency TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    file_path TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    schema_version TEXT NOT NULL,
    source_name TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    refreshed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_datahub_cache_lookup
ON datahub_cache(dataset_type, symbol, frequency, start_date, end_date);

CREATE TABLE IF NOT EXISTS datahub_refreshes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_key TEXT NOT NULL,
    dataset_type TEXT NOT NULL,
    symbol TEXT,
    frequency TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    force_refresh INTEGER NOT NULL,
    status TEXT NOT NULL,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    error_type TEXT,
    error_message TEXT,
    output_cache_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_datahub_refreshes_request_status
ON datahub_refreshes(request_key, status);
```

- [ ] **Step 4: Implement metadata helpers**

Create `datahub/metadata.py`:

```python
from __future__ import annotations

from typing import Any


def _row_to_dict(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def create_cache_record(
    conn,
    *,
    dataset_type: str,
    symbol: str | None,
    frequency: str,
    start_date: str,
    end_date: str,
    file_path: str,
    row_count: int,
    schema_version: str,
    source_name: str,
    expires_at: str | None,
) -> dict[str, Any]:
    cur = conn.execute(
        """
        INSERT INTO datahub_cache (
            dataset_type, symbol, frequency, start_date, end_date, file_path,
            row_count, schema_version, source_name, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset_type,
            symbol,
            frequency,
            start_date,
            end_date,
            file_path,
            row_count,
            schema_version,
            source_name,
            expires_at,
        ),
    )
    conn.commit()
    return get_cache_record(conn, cur.lastrowid)


def get_cache_record(conn, cache_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM datahub_cache WHERE id = ?", (cache_id,)).fetchone()
    return _row_to_dict(row)


def list_cache_records(
    conn,
    *,
    dataset_type: str | None = None,
    symbol: str | None = None,
    frequency: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM datahub_cache WHERE 1 = 1"
    params: list[Any] = []
    if dataset_type is not None:
        sql += " AND dataset_type = ?"
        params.append(dataset_type)
    if symbol is not None:
        sql += " AND symbol = ?"
        params.append(symbol)
    if frequency is not None:
        sql += " AND frequency = ?"
        params.append(frequency)
    sql += " ORDER BY refreshed_at DESC, id DESC"
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def create_refresh_record(
    conn,
    *,
    request_key: str,
    dataset_type: str,
    symbol: str | None,
    frequency: str,
    start_date: str,
    end_date: str,
    force_refresh: bool,
    status: str,
) -> dict[str, Any]:
    cur = conn.execute(
        """
        INSERT INTO datahub_refreshes (
            request_key, dataset_type, symbol, frequency, start_date, end_date,
            force_refresh, status, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'running' THEN CURRENT_TIMESTAMP ELSE NULL END)
        """,
        (
            request_key,
            dataset_type,
            symbol,
            frequency,
            start_date,
            end_date,
            int(force_refresh),
            status,
            status,
        ),
    )
    conn.commit()
    return get_refresh_record(conn, cur.lastrowid)


def get_refresh_record(conn, refresh_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM datahub_refreshes WHERE id = ?",
        (refresh_id,),
    ).fetchone()
    return _row_to_dict(row)


def find_running_refresh(conn, request_key: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM datahub_refreshes
        WHERE request_key = ? AND status IN ('queued', 'running')
        ORDER BY id DESC LIMIT 1
        """,
        (request_key,),
    ).fetchone()
    return _row_to_dict(row)


def mark_refresh_running(conn, refresh_id: int) -> None:
    conn.execute(
        """
        UPDATE datahub_refreshes
        SET status = 'running', started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (refresh_id,),
    )
    conn.commit()


def mark_refresh_completed(
    conn,
    refresh_id: int,
    *,
    cache_hit: bool,
    output_cache_path: str | None,
) -> None:
    conn.execute(
        """
        UPDATE datahub_refreshes
        SET status = 'completed', cache_hit = ?, output_cache_path = ?,
            finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (int(cache_hit), output_cache_path, refresh_id),
    )
    conn.commit()


def mark_refresh_failed(
    conn,
    refresh_id: int,
    *,
    error_type: str,
    error_message: str,
) -> None:
    conn.execute(
        """
        UPDATE datahub_refreshes
        SET status = 'failed', error_type = ?, error_message = ?,
            finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (error_type, error_message, refresh_id),
    )
    conn.commit()
```

Create `datahub/__init__.py` with package exports left minimal:

```python
"""Central market data platform for QuantX."""
```

- [ ] **Step 5: Run metadata tests**

Run: `python -m pytest -q tests/test_datahub_metadata.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/db.py datahub/__init__.py datahub/metadata.py tests/test_datahub_metadata.py
git commit -m "feat(datahub): add metadata schema"
```

---

### Task 2: Core Models, Registry, And Normalization

**Files:**
- Create: `datahub/models.py`
- Create: `datahub/registry.py`
- Create: `datahub/normalize.py`
- Modify: `datahub/__init__.py`
- Test: `tests/test_datahub_core.py`

- [ ] **Step 1: Write failing core tests**

Create `tests/test_datahub_core.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest -q tests/test_datahub_core.py`

Expected: FAIL because modules/functions are missing.

- [ ] **Step 3: Implement models**

Create `datahub/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd


OHLCV_COLUMNS = ("date", "open", "high", "low", "close", "volume")
INDEX_COLUMNS = ("date", "open", "high", "low", "close", "volume", "amount")


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
```

- [ ] **Step 4: Implement registry**

Create `datahub/registry.py`:

```python
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
```

- [ ] **Step 5: Implement normalization**

Create `datahub/normalize.py`:

```python
from __future__ import annotations

from datetime import date, datetime
import re

import pandas as pd

from datahub.models import DataHubError


def format_date(value) -> str:
    if value is None:
        raise DataHubError("schema_invalid", "date value cannot be None")
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        return text
    return pd.to_datetime(text).strftime("%Y%m%d")


def normalize_frame(frame: pd.DataFrame, columns: list[str] | tuple[str, ...]) -> pd.DataFrame:
    missing = [col for col in columns if col not in frame.columns]
    if missing:
        raise DataHubError("schema_invalid", f"Missing columns: {', '.join(missing)}")
    df = frame[list(columns)].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    if df.empty:
        raise DataHubError("empty_data", "Dataset returned no rows")
    return df


def trim_frame(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    df = frame[(frame["date"] >= start_dt) & (frame["date"] <= end_dt)].copy()
    if df.empty:
        raise DataHubError("empty_data", f"No rows in requested range {start}-{end}")
    return df.reset_index(drop=True)
```

Update `datahub/__init__.py`:

```python
"""Central market data platform for QuantX."""

from datahub.models import DatasetRequest, DatasetResult, DatasetSpec, DataHubError

__all__ = ["DatasetRequest", "DatasetResult", "DatasetSpec", "DataHubError"]
```

- [ ] **Step 6: Run core tests**

Run: `python -m pytest -q tests/test_datahub_core.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add datahub/__init__.py datahub/models.py datahub/registry.py datahub/normalize.py tests/test_datahub_core.py
git commit -m "feat(datahub): add dataset registry"
```

---

### Task 3: Dual-Layout Cache With TTL And Locks

**Files:**
- Create: `datahub/cache.py`
- Test: `tests/test_datahub_cache.py`

- [ ] **Step 1: Write failing cache tests**

Create `tests/test_datahub_cache.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest -q tests/test_datahub_cache.py`

Expected: FAIL because `datahub.cache` is missing.

- [ ] **Step 3: Implement cache store**

Create `datahub/cache.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import glob
import os
import re
import threading

import pandas as pd

from datahub.models import DatasetRequest, DatasetSpec
from datahub.normalize import normalize_frame, trim_frame


@dataclass
class CacheHit:
    frame: pd.DataFrame
    cache_path: str


class CacheStore:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def lock_for(self, request: DatasetRequest) -> threading.Lock:
        with self._locks_guard:
            if request.data_key not in self._locks:
                self._locks[request.data_key] = threading.Lock()
            return self._locks[request.data_key]

    def read(self, request: DatasetRequest, spec: DatasetSpec) -> CacheHit | None:
        candidates = self._covering_candidates(request, spec)
        candidates.sort(key=lambda item: int(item[2]) - int(item[1]))
        for path, _, _ in candidates:
            try:
                df = pd.read_csv(path)
                df = normalize_frame(df, spec.columns)
                df = trim_frame(df, request.start, request.end)
                return CacheHit(frame=df, cache_path=path)
            except Exception:
                continue
        return None

    def write(self, request: DatasetRequest, spec: DatasetSpec, frame: pd.DataFrame) -> str:
        path = self.path_for_write(request, spec)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = f"{path}.tmp"
        frame.to_csv(tmp_path, index=False)
        os.replace(tmp_path, path)
        return path

    def path_for_write(self, request: DatasetRequest, spec: DatasetSpec) -> str:
        covering = self._covering_candidates(request, spec)
        if request.force_refresh and covering:
            covering.sort(key=lambda item: int(item[2]) - int(item[1]), reverse=True)
            return covering[0][0]
        symbol = request.symbol or "global"
        return os.path.join(
            self.root_dir,
            "data",
            "cache",
            spec.dataset_type,
            f"{symbol}_{request.start}_{request.end}.csv",
        )

    def _covering_candidates(self, request: DatasetRequest, spec: DatasetSpec) -> list[tuple[str, str, str]]:
        candidates = []
        for path in self._candidate_paths(request, spec):
            parsed = _parse_cache_filename(path, request, spec)
            if parsed is None:
                continue
            start, end = parsed
            if start <= request.start and end >= request.end:
                candidates.append((path, start, end))
        return candidates

    def _candidate_paths(self, request: DatasetRequest, spec: DatasetSpec) -> list[str]:
        symbol = request.symbol or "global"
        legacy_pattern = os.path.join(self.root_dir, f"{symbol}_*.csv")
        new_pattern = os.path.join(self.root_dir, "data", "cache", spec.dataset_type, f"{symbol}_*.csv")
        if request.symbol is None:
            legacy_pattern = os.path.join(self.root_dir, f"{spec.dataset_type}_*.csv")
        return glob.glob(legacy_pattern) + glob.glob(new_pattern)


def _parse_cache_filename(path: str, request: DatasetRequest, spec: DatasetSpec) -> tuple[str, str] | None:
    name = os.path.basename(path)
    symbol = request.symbol or "global"
    patterns = [
        rf"^{re.escape(symbol)}_.+_(\d{{8}})_(\d{{8}})\.csv$",
        rf"^{re.escape(symbol)}_(\d{{8}})_(\d{{8}})\.csv$",
        rf"^{re.escape(spec.dataset_type)}_(\d{{8}})_(\d{{8}})\.csv$",
    ]
    for pattern in patterns:
        match = re.match(pattern, name)
        if match:
            return match.group(1), match.group(2)
    return None


def is_cache_expired(path: str, request: DatasetRequest, spec: DatasetSpec, now: datetime | None = None) -> bool:
    if spec.cache_policy.ttl_seconds is None:
        return False
    if spec.cache_policy.historical_ttl_seconds is None and request.end < datetime.today().strftime("%Y%m%d"):
        return False
    current = now or datetime.now()
    modified = datetime.fromtimestamp(os.path.getmtime(path))
    return current - modified > timedelta(seconds=spec.cache_policy.ttl_seconds)
```

- [ ] **Step 4: Run cache tests**

Run: `python -m pytest -q tests/test_datahub_cache.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add datahub/cache.py tests/test_datahub_cache.py
git commit -m "feat(datahub): add csv cache store"
```

---

### Task 4: Source Adapters Preserving Existing Fallbacks

**Files:**
- Create: `datahub/sources.py`
- Test: `tests/test_datahub_sources.py`

- [ ] **Step 1: Write failing source tests**

Create `tests/test_datahub_sources.py`:

```python
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datahub.models import DatasetRequest
from datahub.sources import AkshareSource


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
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest -q tests/test_datahub_sources.py`

Expected: FAIL because source adapter does not exist.

- [ ] **Step 3: Implement AkShare source adapter**

Create `datahub/sources.py` by moving current AkShare behavior behind `AkshareSource`:

```python
from __future__ import annotations

import time

import akshare as ak
import pandas as pd

from datahub.models import DataHubError, DatasetRequest


_AKSHARE_COLUMN_MAP = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
}


class AkshareSource:
    name = "akshare"

    def fetch(self, request: DatasetRequest) -> pd.DataFrame:
        if request.dataset_type == "stock_daily":
            return self.fetch_stock_daily(request)
        if request.dataset_type == "index_daily":
            return self.fetch_index_daily(request)
        if request.dataset_type == "etf_daily":
            return self.fetch_etf_daily(request)
        if request.dataset_type == "market_turnover":
            return self.fetch_market_turnover(request)
        raise DataHubError("unsupported_dataset", f"Unsupported dataset type: {request.dataset_type}")

    def fetch_stock_daily(self, request: DatasetRequest) -> pd.DataFrame:
        last_err = None
        for attempt in range(1, 4):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=request.symbol,
                    period="daily",
                    start_date=request.start,
                    end_date=request.end,
                )
                df = df[list(_AKSHARE_COLUMN_MAP.keys())]
                df.columns = ["date", "open", "high", "low", "close", "volume"]
                return df
            except Exception as exc:
                last_err = exc
                if attempt < 3:
                    time.sleep(2)

        prefix = "sh" if str(request.symbol).startswith("6") else "sz"
        for attempt in range(1, 3):
            try:
                df = ak.stock_zh_a_hist_tx(
                    symbol=f"{prefix}{request.symbol}",
                    start_date=request.start,
                    end_date=request.end,
                )
                df = df.rename(columns={"amount": "volume"})
                return df[["date", "open", "high", "low", "close", "volume"]]
            except Exception:
                if attempt < 2:
                    time.sleep(1)
        raise DataHubError("source_unavailable", f"All stock sources failed for {request.symbol}") from last_err

    def fetch_index_daily(self, request: DatasetRequest) -> pd.DataFrame:
        try:
            full_df = ak.stock_zh_index_daily(symbol=request.symbol)
        except Exception as exc:
            raise DataHubError("source_unavailable", f"Index source failed for {request.symbol}") from exc
        full_df["date"] = pd.to_datetime(full_df["date"])
        mask = (full_df["date"] >= pd.to_datetime(request.start)) & (full_df["date"] <= pd.to_datetime(request.end))
        df = full_df.loc[mask].copy()
        if "amount" not in df.columns:
            df["amount"] = df["close"] * df["volume"] * 100
        return df[["date", "open", "high", "low", "close", "volume", "amount"]]

    def fetch_etf_daily(self, request: DatasetRequest) -> pd.DataFrame:
        try:
            df = ak.fund_etf_hist_sina(symbol=request.symbol).copy()
        except Exception as exc:
            raise DataHubError("source_unavailable", f"ETF source failed for {request.symbol}") from exc
        df["date"] = pd.to_datetime(df["date"])
        mask = (df["date"] >= pd.to_datetime(request.start)) & (df["date"] <= pd.to_datetime(request.end))
        df = df.loc[mask, ["date", "open", "high", "low", "close", "volume"]].copy()
        df["amount"] = 0.0
        return df[["date", "open", "high", "low", "close", "volume", "amount"]]

    def fetch_market_turnover(self, request: DatasetRequest) -> pd.DataFrame:
        index_df = self.fetch_index_daily(
            DatasetRequest("index_daily", symbol="sh000001", start=request.start, end=request.end)
        )
        rows = []
        for current in pd.to_datetime(index_df["date"]).drop_duplicates().sort_values():
            date_text = current.strftime("%Y%m%d")
            total = float(_fetch_sse_turnover(date_text)) + float(_fetch_szse_turnover(date_text))
            rows.append(
                {
                    "date": current,
                    "open": total,
                    "high": total,
                    "low": total,
                    "close": total,
                    "volume": 0.0,
                }
            )
        return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])


def _fetch_sse_turnover(date_text: str) -> float:
    df = ak.stock_sse_deal_daily(date=date_text)
    row = df.loc[df["单日情况"] == "成交金额"]
    if row.empty:
        raise DataHubError("empty_data", f"SSE turnover not found for {date_text}")
    if "股票" in row.columns and pd.notna(row["股票"].iloc[0]):
        return float(row["股票"].iloc[0])
    columns = [col for col in ["主板A", "主板B", "科创板"] if col in row.columns]
    return float(row[columns].fillna(0).sum(axis=1).iloc[0])


def _fetch_szse_turnover(date_text: str) -> float:
    df = ak.stock_szse_summary(date=date_text)
    exact_row = df.loc[df["证券类别"] == "股票"]
    if not exact_row.empty:
        return float(exact_row["成交金额"].iloc[0])
    stock_rows = df[df["证券类别"].astype(str).str.contains("股票|A股|B股", na=False)]
    if stock_rows.empty:
        raise DataHubError("empty_data", f"SZSE turnover not found for {date_text}")
    return float(stock_rows["成交金额"].sum())
```

- [ ] **Step 4: Run source tests**

Run: `python -m pytest -q tests/test_datahub_sources.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add datahub/sources.py tests/test_datahub_sources.py
git commit -m "feat(datahub): add akshare source adapters"
```

---

### Task 5: DataHub Service And Refresh Executor

**Files:**
- Create: `datahub/service.py`
- Create: `datahub/executor.py`
- Test: `tests/test_datahub_service.py`
- Test: `tests/test_datahub_executor.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_datahub_service.py`:

```python
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
```

Create `tests/test_datahub_executor.py`:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datahub.executor import DataHubRefreshExecutor
from datahub.metadata import create_refresh_record, get_refresh_record
from datahub.models import DatasetRequest
from server.db import init_db


def test_refresh_executor_opens_worker_connection(tmp_path):
    db_path = str(tmp_path / "quantx.sqlite")
    conn = init_db(db_path)
    refresh = create_refresh_record(
        conn,
        request_key="stock_daily:000001:daily:20240101:20240131:true",
        dataset_type="stock_daily",
        symbol="000001",
        frequency="daily",
        start_date="20240101",
        end_date="20240131",
        force_refresh=True,
        status="queued",
    )
    seen = {}

    def worker(conn, request, refresh_id):
        seen["same_connection"] = conn is not None
        from datahub.metadata import mark_refresh_completed
        mark_refresh_completed(conn, refresh_id, cache_hit=False, output_cache_path="/tmp/cache.csv")

    executor = DataHubRefreshExecutor(db_path=db_path, worker=worker, max_workers=1)
    executor.submit(DatasetRequest("stock_daily", symbol="000001", start="20240101", end="20240131", force_refresh=True), refresh["id"]).result(timeout=5)

    saved = get_refresh_record(conn, refresh["id"])
    assert seen["same_connection"] is True
    assert saved["status"] == "completed"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest -q tests/test_datahub_service.py tests/test_datahub_executor.py`

Expected: FAIL because service/executor are missing.

- [ ] **Step 3: Implement DataHub service**

Create `datahub/service.py`:

```python
from __future__ import annotations

from typing import Iterable

from datahub.cache import CacheStore
from datahub.metadata import (
    create_cache_record,
    create_refresh_record,
    find_running_refresh,
    list_cache_records,
    mark_refresh_completed,
    mark_refresh_failed,
)
from datahub.models import DataHubError, DatasetRequest, DatasetResult
from datahub.normalize import normalize_frame
from datahub.registry import get_dataset_spec, list_dataset_specs, request_for_feed_id
from datahub.sources import AkshareSource


class DataHub:
    def __init__(self, *, root_dir: str, conn, source=None, executor=None):
        self.root_dir = root_dir
        self.conn = conn
        self.source = source or AkshareSource()
        self.cache = CacheStore(root_dir)
        self.executor = executor

    def list_datasets(self):
        return list_dataset_specs()

    def list_cache(self, *, dataset_type: str | None = None, symbol: str | None = None):
        return list_cache_records(self.conn, dataset_type=dataset_type, symbol=symbol)

    def get_dataset(self, request: DatasetRequest) -> DatasetResult:
        spec = get_dataset_spec(request.dataset_type)
        if spec.symbol_required and not request.symbol:
            raise DataHubError("unsupported_dataset", f"{request.dataset_type} requires symbol")

        with self.cache.lock_for(request):
            if not request.force_refresh:
                hit = self.cache.read(request, spec)
                if hit is not None:
                    return DatasetResult(request=request, frame=hit.frame, cache_hit=True, cache_path=hit.cache_path)

            raw = self.source.fetch(request)
            frame = normalize_frame(raw, spec.columns)
            cache_path = self.cache.write(request, spec, frame)
            create_cache_record(
                self.conn,
                dataset_type=request.dataset_type,
                symbol=request.symbol,
                frequency=request.frequency,
                start_date=request.start,
                end_date=request.end,
                file_path=cache_path,
                row_count=len(frame),
                schema_version="-".join(spec.columns),
                source_name=getattr(self.source, "name", spec.source_name),
                expires_at=None,
            )
            return DatasetResult(
                request=request,
                frame=frame,
                cache_hit=False,
                cache_path=cache_path,
                source_name=getattr(self.source, "name", spec.source_name),
            )

    def resolve_feed_requests(self, feed_ids: Iterable[str], start: str, end: str) -> list[DatasetRequest]:
        return [request_for_feed_id(feed_id, start, end) for feed_id in feed_ids]

    def create_refresh(self, request: DatasetRequest) -> dict:
        non_force = DatasetRequest(
            dataset_type=request.dataset_type,
            symbol=request.symbol,
            start=request.start,
            end=request.end,
            frequency=request.frequency,
            force_refresh=False,
        )
        if request.force_refresh:
            running_non_force = find_running_refresh(self.conn, non_force.cache_key)
            if running_non_force is not None:
                raise DataHubError(
                    "refresh_in_progress",
                    f"Refresh already running: {running_non_force['id']}",
                    {"refresh_id": running_non_force["id"]},
                )

        running = find_running_refresh(self.conn, request.cache_key)
        if running is not None:
            return running

        if not request.force_refresh:
            hit = self.cache.read(request, get_dataset_spec(request.dataset_type))
            if hit is not None:
                record = create_refresh_record(
                    self.conn,
                    request_key=request.cache_key,
                    dataset_type=request.dataset_type,
                    symbol=request.symbol,
                    frequency=request.frequency,
                    start_date=request.start,
                    end_date=request.end,
                    force_refresh=request.force_refresh,
                    status="completed",
                )
                mark_refresh_completed(self.conn, record["id"], cache_hit=True, output_cache_path=hit.cache_path)
                return self.get_refresh(record["id"])

        record = create_refresh_record(
            self.conn,
            request_key=request.cache_key,
            dataset_type=request.dataset_type,
            symbol=request.symbol,
            frequency=request.frequency,
            start_date=request.start,
            end_date=request.end,
            force_refresh=request.force_refresh,
            status="queued",
        )
        if self.executor is not None:
            self.executor.submit(request, record["id"])
        return self.get_refresh(record["id"])

    def execute_refresh_once(self, request: DatasetRequest, refresh_id: int, conn=None) -> None:
        target_conn = conn or self.conn
        try:
            result = self.get_dataset(request)
            mark_refresh_completed(
                target_conn,
                refresh_id,
                cache_hit=result.cache_hit,
                output_cache_path=result.cache_path,
            )
        except DataHubError as exc:
            mark_refresh_failed(target_conn, refresh_id, error_type=exc.error_type, error_message=exc.message)
        except Exception as exc:
            mark_refresh_failed(target_conn, refresh_id, error_type="source_unavailable", error_message=str(exc))

    def get_refresh(self, refresh_id: int) -> dict | None:
        from datahub.metadata import get_refresh_record

        return get_refresh_record(self.conn, refresh_id)
```

- [ ] **Step 4: Implement bounded executor with worker-owned connections**

Create `datahub/executor.py`:

```python
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from datahub.models import DatasetRequest
from server.db import init_db


class DataHubRefreshExecutor:
    def __init__(self, *, db_path: str, worker: Callable, max_workers: int = 2):
        self.db_path = db_path
        self.worker = worker
        self.pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="datahub-refresh")

    def submit(self, request: DatasetRequest, refresh_id: int) -> Future:
        return self.pool.submit(self._run, request, refresh_id)

    def _run(self, request: DatasetRequest, refresh_id: int) -> None:
        conn = init_db(self.db_path)
        try:
            self.worker(conn, request, refresh_id)
        finally:
            conn.close()
```

- [ ] **Step 5: Run service and executor tests**

Run: `python -m pytest -q tests/test_datahub_service.py tests/test_datahub_executor.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add datahub/service.py datahub/executor.py tests/test_datahub_service.py tests/test_datahub_executor.py
git commit -m "feat(datahub): add service and refresh executor"
```

---

### Task 6: FastAPI DataHub Endpoints

**Files:**
- Modify: `server/models.py`
- Modify: `server/api.py`
- Test: `tests/test_server_api.py`

- [ ] **Step 1: Write failing API tests**

Append to `tests/test_server_api.py`:

```python
def test_datahub_datasets_endpoint(tmp_path):
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)

    response = client.get('/api/data/datasets')

    assert response.status_code == 200
    body = response.json()
    assert {item['dataset_type'] for item in body} >= {'stock_daily', 'index_daily', 'etf_daily', 'market_turnover'}


def test_datahub_refresh_endpoint_returns_record(tmp_path, monkeypatch):
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)

    def fake_refresh(self, request):
        return {
            'id': 5,
            'request_key': request.cache_key,
            'dataset_type': request.dataset_type,
            'symbol': request.symbol,
            'frequency': request.frequency,
            'start_date': request.start,
            'end_date': request.end,
            'force_refresh': int(request.force_refresh),
            'status': 'queued',
            'cache_hit': 0,
            'error_type': None,
            'error_message': None,
            'output_cache_path': None,
        }

    monkeypatch.setattr('server.api.DataHub.create_refresh', fake_refresh)

    response = client.post('/api/data/refresh', json={
        'dataset_type': 'stock_daily',
        'symbol': '000001',
        'start': '20240101',
        'end': '20240131',
        'force_refresh': False,
    })

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == 5
    assert body['status'] == 'queued'


def test_force_refresh_conflict_returns_409_with_running_refresh_id(tmp_path, monkeypatch):
    app = create_app(db_path=str(tmp_path / 'jobs.sqlite'))
    client = TestClient(app)

    def raise_conflict(*args, **kwargs):
        from datahub.models import DataHubError
        raise DataHubError('refresh_in_progress', 'Refresh already running: 7', {'refresh_id': 7})

    monkeypatch.setattr('server.api.DataHub.create_refresh', raise_conflict)

    response = client.post('/api/data/refresh', json={
        'dataset_type': 'stock_daily',
        'symbol': '000001',
        'start': '20240101',
        'end': '20240131',
        'force_refresh': True,
    })

    assert response.status_code == 409
    assert response.json()['detail']['error_type'] == 'refresh_in_progress'
    assert response.json()['detail']['refresh_id'] == 7
```

- [ ] **Step 2: Run API tests and verify failure**

Run: `python -m pytest -q tests/test_server_api.py::test_datahub_datasets_endpoint tests/test_server_api.py::test_datahub_refresh_endpoint_returns_record tests/test_server_api.py::test_force_refresh_conflict_returns_409_with_running_refresh_id`

Expected: FAIL with 404 or import errors.

- [ ] **Step 3: Add API models**

Modify `server/models.py`:

```python
class DataRefreshRequest(BaseModel):
    dataset_type: str = Field(min_length=1)
    symbol: str | None = None
    start: str
    end: str
    frequency: str = 'daily'
    force_refresh: bool = False
```

- [ ] **Step 4: Add DataHub endpoints**

Modify imports in `server/api.py`:

```python
import os

from datahub.executor import DataHubRefreshExecutor
from datahub.models import DataHubError, DatasetRequest
from datahub.service import DataHub
from server.models import DataRefreshRequest, JobCreateRequest
```

Inside `create_app`, after `app.state.db = conn`, add:

```python
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _make_datahub(executor=None):
        return DataHub(root_dir=project_root, conn=conn, executor=executor)

    def _datahub_worker(worker_conn, request, refresh_id):
        worker_hub = DataHub(root_dir=project_root, conn=worker_conn)
        worker_hub.execute_refresh_once(request, refresh_id, conn=worker_conn)

    app.state.datahub_executor = DataHubRefreshExecutor(
        db_path=db_path,
        worker=_datahub_worker,
        max_workers=2,
    )
```

Add routes before `return app`:

```python
    @app.get('/api/data/datasets')
    def datahub_datasets():
        hub = _make_datahub()
        return [
            {
                'dataset_type': spec.dataset_type,
                'label': spec.label,
                'columns': list(spec.columns),
                'symbol_required': spec.symbol_required,
                'source_name': spec.source_name,
                'ttl_seconds': spec.cache_policy.ttl_seconds,
                'historical_ttl_seconds': spec.cache_policy.historical_ttl_seconds,
            }
            for spec in hub.list_datasets()
        ]

    @app.get('/api/data/cache')
    def datahub_cache(dataset_type: str | None = None, symbol: str | None = None):
        return _make_datahub().list_cache(dataset_type=dataset_type, symbol=symbol)

    @app.post('/api/data/refresh')
    def datahub_refresh(payload: DataRefreshRequest):
        hub = _make_datahub(executor=app.state.datahub_executor)
        request = DatasetRequest(
            dataset_type=payload.dataset_type,
            symbol=payload.symbol,
            start=payload.start,
            end=payload.end,
            frequency=payload.frequency,
            force_refresh=payload.force_refresh,
        )
        try:
            refresh = hub.create_refresh(request)
        except DataHubError as exc:
            if exc.error_type == 'refresh_in_progress':
                raise HTTPException(status_code=409, detail=exc.to_dict()) from exc
            raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
        return refresh

    @app.get('/api/data/refresh/{refresh_id}')
    def datahub_refresh_detail(refresh_id: int):
        refresh = _make_datahub().get_refresh(refresh_id)
        if refresh is None:
            raise HTTPException(status_code=404, detail='refresh not found')
        return refresh
```

- [ ] **Step 5: Run API tests**

Run: `python -m pytest -q tests/test_server_api.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/models.py server/api.py tests/test_server_api.py
git commit -m "feat(datahub): add data management api"
```

---

### Task 7: Backtest Service Uses DataHub

**Files:**
- Modify: `backtest/service.py`
- Test: `tests/test_backtest_service.py`

- [ ] **Step 1: Write failing orchestration test**

Append to `tests/test_backtest_service.py`:

```python
def test_run_backtest_service_loads_primary_feed_through_datahub(monkeypatch):
    import backtest.service as service

    stock_df = generate_synthetic_data(start='20240101', end='20240630')
    calls = []

    class FakeHub:
        def __init__(self, *args, **kwargs):
            pass

        def get_dataset(self, request):
            calls.append(request)
            from datahub.models import DatasetResult
            return DatasetResult(request=request, frame=stock_df.copy(), cache_hit=False)

        def resolve_feed_requests(self, feed_ids, start, end):
            return []

    monkeypatch.setattr(service, 'DataHub', FakeHub)
    monkeypatch.setattr(service, 'get_market_score', lambda *args, **kwargs: None)

    result = run_backtest_service(BacktestRequest(
        symbol='000001',
        start='20240101',
        end='20240630',
        use_market_filter=False,
    ))

    assert result.symbol == '000001'
    assert calls[0].dataset_type == 'stock_daily'
    assert calls[0].symbol == '000001'
```

- [ ] **Step 2: Run test and verify failure**

Run: `python -m pytest -q tests/test_backtest_service.py::test_run_backtest_service_loads_primary_feed_through_datahub`

Expected: FAIL because `backtest.service` still imports and calls concrete loaders.

- [ ] **Step 3: Refactor service imports and feed loading**

Modify `backtest/service.py` imports:

```python
import os

from datahub.models import DatasetRequest
from datahub.service import DataHub
from server.db import DEFAULT_DB_PATH, init_db
```

Add helper:

```python
def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_datahub():
    return DataHub(root_dir=_project_root(), conn=init_db(DEFAULT_DB_PATH))
```

Replace `_load_required_feed_frames` with:

```python
def _load_required_feed_frames(datahub: DataHub, required_data: tuple[str, ...], start: str, end: str) -> list[pd.DataFrame]:
    frames = []
    for request in datahub.resolve_feed_requests(required_data, start, end):
        result = datahub.get_dataset(request)
        if result.frame is None or result.frame.empty:
            raise ValueError(f"Required feed '{request.dataset_type}' returned no data")
        frames.append(result.frame)
    return frames
```

In `run_backtest_service`, replace primary stock and index loading:

```python
    datahub = _make_datahub()
    stock_result = datahub.get_dataset(
        DatasetRequest(
            dataset_type='stock_daily',
            symbol=req.symbol,
            start=req.start,
            end=req.end,
        )
    )
    df = stock_result.frame
    data = bt.feeds.PandasData(dataname=df, datetime=0)

    index_data: list[dict[str, Any]] = []
    try:
        index_result = datahub.get_dataset(
            DatasetRequest(
                dataset_type='index_daily',
                symbol='sh000001',
                start=req.start,
                end=req.end,
            )
        )
        index_df = index_result.frame
    except Exception:
        index_df = None
```

Replace required feed loop:

```python
    for frame in _load_required_feed_frames(datahub, spec.required_data, req.start, req.end):
        cerebro.adddata(bt.feeds.PandasData(dataname=frame, datetime=0))
```

- [ ] **Step 4: Run backtest service tests**

Run: `python -m pytest -q tests/test_backtest_service.py`

Expected: PASS. If tests monkeypatch old loader names, update those tests to monkeypatch `DataHub` or `_make_datahub` instead.

- [ ] **Step 5: Commit**

```bash
git add backtest/service.py tests/test_backtest_service.py
git commit -m "feat(datahub): route backtests through datahub"
```

---

### Task 8: Compatibility Wrappers And CLI

**Files:**
- Modify: `backtest/data_loader.py`
- Modify: `backtest/run_backtest.py`
- Test: `tests/test_data_loader_strategy_feeds.py`
- Test: `tests/test_backtest_service.py`

- [ ] **Step 1: Write golden wrapper tests**

Append to `tests/test_data_loader_strategy_feeds.py`:

```python
def test_load_market_data_wrapper_matches_datahub_result(monkeypatch, tmp_path):
    from datahub.models import DatasetResult, DatasetRequest

    monkeypatch.setattr(data_loader, "_CACHE_DIR", str(tmp_path))
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

    class FakeHub:
        def __init__(self, *args, **kwargs):
            pass

        def get_dataset(self, request):
            assert request == DatasetRequest("stock_daily", symbol="000001", start="20240101", end="20240131")
            return DatasetResult(request=request, frame=expected.copy(), cache_hit=False)

    monkeypatch.setattr(data_loader, "DataHub", FakeHub)

    df = data_loader.load_market_data("000001", "20240101", "20240131")

    assert list(df.columns) == data_loader.STANDARD_COLUMNS
    assert df["date"].dt.strftime("%Y%m%d").tolist() == ["20240102", "20240103"]
    assert df["close"].tolist() == [1.2, 2.2]
```

- [ ] **Step 2: Run wrapper test and verify failure**

Run: `python -m pytest -q tests/test_data_loader_strategy_feeds.py::test_load_market_data_wrapper_matches_datahub_result`

Expected: FAIL because `backtest.data_loader` does not expose/use `DataHub`.

- [ ] **Step 3: Convert public loader functions to DataHub wrappers**

At top of `backtest/data_loader.py`, add:

```python
from datahub.models import DatasetRequest
from datahub.service import DataHub
from server.db import DEFAULT_DB_PATH, init_db
```

Add helper:

```python
def _make_datahub():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return DataHub(root_dir=project_root, conn=init_db(DEFAULT_DB_PATH))
```

Replace public functions while preserving signatures:

```python
def load_market_data(symbol, start, end):
    start, end = resolve_date_range(start, end)
    result = _make_datahub().get_dataset(
        DatasetRequest("stock_daily", symbol=str(symbol).zfill(6), start=start, end=end)
    )
    return result.frame


def load_shanghai_composite(start, end):
    start, end = resolve_date_range(start, end)
    try:
        result = _make_datahub().get_dataset(
            DatasetRequest("index_daily", symbol="sh000001", start=start, end=end)
        )
        return result.frame
    except Exception as exc:
        print(f"无法获取上证综合指数的历史数据: {exc}")
        return None


def load_security_etf_data(start, end, symbol='sh512880'):
    start, end = resolve_date_range(start, end)
    result = _make_datahub().get_dataset(
        DatasetRequest("etf_daily", symbol=symbol, start=start, end=end)
    )
    return result.frame


def load_market_turnover_data(start, end):
    start, end = resolve_date_range(start, end)
    result = _make_datahub().get_dataset(
        DatasetRequest("market_turnover", start=start, end=end)
    )
    return result.frame
```

Keep date helpers such as `resolve_date_range` and `get_default_date_range` because callers still use them. Private turnover helpers can remain for backward compatibility, but DataHub source adapters should use their own copies to avoid circular imports after wrappers delegate to DataHub.

- [ ] **Step 4: Update CLI to use DataHub where practical**

In `backtest/run_backtest.py`, prefer the wrapper path for now because it now delegates to DataHub and preserves existing synthetic fallback:

```python
try:
    stock_df = load_market_data(symbol, start, end)
except Exception as exc:
    print(f'Data load failed ({exc}), using synthetic data for demo backtest')
    stock_df = generate_synthetic_data(start=start, end=end)
    stock_df['date'] = pd.to_datetime(stock_df['date'])
```

No further CLI change is required in v1.

- [ ] **Step 5: Run compatibility and CLI-related tests**

Run: `python -m pytest -q tests/test_data_loader_strategy_feeds.py tests/test_backtest_service.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backtest/data_loader.py backtest/run_backtest.py tests/test_data_loader_strategy_feeds.py tests/test_backtest_service.py
git commit -m "feat(datahub): preserve loader compatibility"
```

---

### Task 9: Final Verification And Documentation Touches

**Files:**
- Modify: `README.md` only if endpoint documentation is needed.
- Verify: full test suite.

- [ ] **Step 1: Run DataHub-focused tests**

Run:

```bash
python -m pytest -q \
  tests/test_datahub_core.py \
  tests/test_datahub_cache.py \
  tests/test_datahub_metadata.py \
  tests/test_datahub_sources.py \
  tests/test_datahub_service.py \
  tests/test_datahub_executor.py
```

Expected: PASS.

- [ ] **Step 2: Run server and backtest tests**

Run:

```bash
python -m pytest -q \
  tests/test_server_api.py \
  tests/test_backtest_service.py \
  tests/test_data_loader_strategy_feeds.py
```

Expected: PASS.

- [ ] **Step 3: Run full Python test suite**

Run: `python -m pytest -q tests/`

Expected: PASS.

- [ ] **Step 4: Smoke-test dataset endpoint without network**

Run:

```bash
python - <<'PY'
from fastapi.testclient import TestClient
from server.api import create_app

app = create_app()
client = TestClient(app)
response = client.get('/api/data/datasets')
print(response.status_code)
print([item['dataset_type'] for item in response.json()])
PY
```

Expected output includes status `200` and dataset types `stock_daily`, `index_daily`, `etf_daily`, `market_turnover`.

- [ ] **Step 5: Check git status**

Run: `git status --short`

Expected: only intentional code/test/doc changes are present. Do not stage `node_modules/` or generated `data/` files.

- [ ] **Step 6: Commit final docs if changed**

If `README.md` was updated:

```bash
git add README.md
git commit -m "docs: document datahub endpoints"
```

If no docs changed, skip this commit.

---

## Self-Review Checklist

- Spec coverage: DataHub package, four dataset specs, TTL/force refresh, dual cache layout, source fallback, SQLite metadata, bounded executor, API endpoints, backtest integration, compatibility wrappers, and tests are each covered by at least one task.
- Review clarifications: worker-owned DB connections, `busy_timeout`, 409 refresh conflict, force-refresh cache shadowing, market-turnover freshness, and executor-before-API ordering are included.
- Placeholder scan: no task uses TBD/TODO/fill-in wording; implementation snippets define the expected signatures.
- Type consistency: `DatasetRequest`, `DatasetSpec`, `DatasetResult`, `DataHubError`, `DataHub`, `CacheStore`, and `DataHubRefreshExecutor` names are consistent across tasks.

---

## Known Limitations

- **In-process cache-key locks only.** `CacheStore.lock_for` returns a `threading.Lock` scoped to the current process. Within the current single-process FastAPI design this is sufficient to prevent concurrent refreshes of the same dataset. Separate processes (multiple FastAPI workers, independent scripts, or future horizontal deployment) can still race on the same CSV path. Mitigations in place:
  - SQLite partial unique index on `datahub_refreshes(request_key, status)` for `queued`/`running` statuses prevents duplicate active refresh records.
  - `CacheStore.write` uses temp-file + atomic `os.replace`, so readers see either the old or the new file, never a partial write.
  - If cross-process locking becomes a requirement, introduce a file-based lock (e.g. `filelock` on a per-key lock file under `data/cache/locks/`) or a distributed lock.
