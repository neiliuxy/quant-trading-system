# DataHub Digital Middle Platform Design

## Goal

Build the first version of a data middle platform for the quant trading prototype. The platform centralizes data acquisition, cache management, schema normalization, metadata tracking, and refresh operations so strategies no longer depend on concrete data loaders.

The first version does not include a Web UI. It provides backend APIs and a Python service boundary that future UI work can reuse.

The current strategy classes already do not call data loaders directly. The main dependency to remove is in the orchestration and utility layers: `backtest/service.py`, `backtest/run_backtest.py`, `backtest/stock_selector.py`, and scripts that currently import `backtest.data_loader`.

## Scope

In scope:

- Add a `datahub/` Python package as the central data platform module.
- Support a generic dataset model that can later represent sectors, industries, fundamentals, and minute bars.
- Implement loaders only for the data currently needed by the system:
  - `stock_daily`
  - `index_daily:sh000001`
  - `etf_daily:sh512880`
  - `market_turnover`
- Add cache TTL plus explicit `force_refresh` behavior.
- Track cache and refresh metadata in the existing SQLite database.
- Add backend data APIs for dataset discovery, cache inspection, refresh creation, and refresh status.
- Refactor backtest service and CLI data loading to go through DataHub.
- Preserve public `backtest.data_loader` functions as compatibility wrappers during migration.

Out of scope:

- A frontend data management page.
- A separate data service process.
- New external storage systems.
- Implementing all future dataset categories.
- Live trading or real-time streaming data.

## Recommended Architecture

Use an in-process DataHub module plus FastAPI management endpoints. This keeps deployment simple for the current single-process prototype while creating a stable boundary that can later move behind a separate service if needed.

```text
StrategySpec.required_data
        |
Backtest Service / CLI
        |
DataHub.resolve_feeds(symbol, start, end, strategy_spec)
        |
Dataset Registry -> Cache Store -> Source Adapter -> Normalizer
        |
Backtrader PandasData feeds
        |
Strategy runtime
```

Strategies do not receive a DataHub client and do not request data directly. They only declare required datasets through `StrategySpec.required_data`. Backtest orchestration resolves those requirements through DataHub and injects Backtrader feeds.

## Package Structure

```text
datahub/
  __init__.py
  models.py
  registry.py
  service.py
  cache.py
  sources.py
  normalize.py
  metadata.py
```

Responsibilities:

- `models.py`: typed request/result models such as `DatasetRequest`, `DatasetSpec`, `DatasetResult`, `CachePolicy`, and refresh status values.
- `registry.py`: the dataset catalog and mapping from strategy feed IDs to dataset requests.
- `service.py`: the main `DataHub` entry point used by backtest services, CLI, and API endpoints.
- `cache.py`: CSV cache lookup, date coverage checks, TTL checks, and force refresh handling.
- `sources.py`: AkShare source adapters, initially wrapping and then replacing logic from `backtest.data_loader`.
- `normalize.py`: date normalization, standard column ordering, required field validation, and schema-specific checks.
- `metadata.py`: SQLite reads/writes for cache records and refresh records.

## Dataset Model

Each dataset request has:

- `dataset_type`: logical type, for example `stock_daily`, `index_daily`, `etf_daily`, or `market_turnover`.
- `symbol`: optional symbol such as `000001`, `sh000001`, or `sh512880`.
- `frequency`: initially `daily`.
- `start` and `end`: normalized `YYYYMMDD` boundaries.
- `fields`: optional requested fields, defaulting to the dataset schema.
- `force_refresh`: explicit cache bypass flag.

Field projection is a model-level extension point only. First-version loaders should return the full standard schema for each dataset and should not add projection plumbing unless it is needed by the implementing code.

Each dataset spec defines:

- Logical ID and label.
- Required fields and standard schema.
- Default cache policy.
- Source adapter.
- Whether `symbol` is required.

First-version schemas:

- OHLCV schema: `date`, `open`, `high`, `low`, `close`, `volume`.
- Index-like schema: `date`, `open`, `high`, `low`, `close`, `volume`, `amount`.

## Cache And Refresh Policy

Use a hybrid cache policy:

- Default behavior reads a valid cache when it covers the requested date range and is not expired.
- Missing cache, insufficient coverage, expired cache, and schema-invalid cache trigger source refresh.
- `force_refresh=True` bypasses cache freshness checks and downloads from the source.
- Refresh success and failure are recorded in SQLite.

This is a behavior change from the current cache, which is effectively fresh forever once a CSV covers the requested range and has the expected columns. To preserve reproducibility and avoid unnecessary AkShare calls, first-version TTL should be trailing-edge aware:

- Fully historical ranges ending before the latest known trading day do not expire by default.
- Ranges that include the latest trading edge use a short daily TTL, initially 24 hours.
- Derived datasets such as `market_turnover` inherit the strictest freshness requirement of their source inputs.
- Manual `force_refresh=True` remains available for all datasets.

The first implementation should keep reading existing CSV names for compatibility. New cache writes can use a normalized directory layout:

```text
data/cache/<dataset_type>/<symbol_or_global>_<start>_<end>.csv
```

This layout avoids mixing stock, index, ETF, and market-derived files in one flat directory.

During migration DataHub must read both existing flat-cache files and new-layout files. Coverage matching must preserve the current behavior:

- Accept files whose cached start is less than or equal to the requested start and cached end is greater than or equal to the requested end.
- Prefer the narrowest covering file when multiple candidates match.
- Trim the returned DataFrame to the requested `[start, end]` range.
- Write new files to the normalized layout, but do not move or delete existing flat-cache files in v1.

Source adapters must preserve current reliability behavior. In particular, `stock_daily` keeps the existing 东方财富 `stock_zh_a_hist` retry path and Tencent `stock_zh_a_hist_tx` fallback path.

## Concurrency And Execution

Refresh execution should not reuse `server.executor.submit_background` as-is because that function is currently hardcoded to execute backtest jobs. First-version implementation should either generalize the executor to accept typed tasks or add a small DataHub-specific refresh executor.

The executor must have bounded concurrency. Use a small `ThreadPoolExecutor` or equivalent limit so slow AkShare calls do not create unbounded threads alongside backtest jobs. SQLite access should use separate short-lived connections per worker operation instead of sharing one long-lived connection across all refresh threads.

Refresh requests are deduplicated by dataset type, symbol, frequency, start date, end date, and force flag:

- If an identical non-force refresh is already running, `POST /api/data/refresh` returns the existing refresh record.
- If a completed non-expired cache already satisfies a non-force refresh, the API records a cache-hit refresh result without downloading.
- If `force_refresh=True` and an identical force refresh is already running, return the existing running force refresh.
- If `force_refresh=True` and only a non-force refresh is running for the same cache key, return a conflict-style response or structured error instead of starting a competing write.

DataHub must also use a per-cache-key lock around download and cache writes. This prevents two refreshes for the same dataset and range from writing the same path concurrently. Cache writes should be atomic: write to a temporary file in the target directory, then replace the final CSV path.

## SQLite Metadata

Extend the existing SQLite database with DataHub tables.

Suggested records:

- Cache record: dataset type, symbol, frequency, start date, end date, file path, row count, schema version, created time, refreshed time, expiry time, source name.
- Refresh record: request payload, status, started time, finished time, cache hit flag, error type, error message, output cache path.

Metadata is used by APIs and future Web pages. It is not the source of truth for market data values; CSV cache files remain the storage for actual bars in the first version.

## Backend APIs

Add DataHub endpoints under the existing FastAPI app:

```text
GET  /api/data/datasets
GET  /api/data/cache
POST /api/data/refresh
GET  /api/data/refresh/{id}
```

API behavior:

- `GET /api/data/datasets`: returns registered datasets, schemas, symbol requirements, and cache policies.
- `GET /api/data/cache`: filters cache records by dataset type, symbol, and date range.
- `POST /api/data/refresh`: creates a refresh request with dataset, symbol, date range, and `force_refresh`.
- `GET /api/data/refresh/{id}`: returns refresh status, error details, and output cache metadata.

The first version creates a refresh record immediately, returns its ID and status, and lets callers poll `GET /api/data/refresh/{id}` for completion. Execution uses the bounded DataHub refresh executor described above. This keeps refresh behavior consistent even when a source request is slow.

## Backtest Integration

Backtest orchestration becomes the only strategy-facing integration point.

`backtest/service.py` should:

- Build a primary stock dataset request from the `BacktestRequest`.
- Convert `StrategySpec.required_data` feed IDs to DataHub dataset requests.
- Ask DataHub for normalized frames.
- Convert frames to `bt.feeds.PandasData`.
- Keep strategy parameter filtering unchanged.

`backtest/run_backtest.py` should use the same DataHub path where practical. Its existing synthetic fallback can remain for CLI demo use when primary stock data cannot be fetched.

`backtest/stock_selector.py` and scripts may keep importing `backtest.data_loader` in v1. They are protected by compatibility wrappers rather than migrated one by one.

`backtest/data_loader.py` should remain as a compatibility layer. Public functions such as `load_market_data`, `load_shanghai_composite`, `load_security_etf_data`, and `load_market_turnover_data` can delegate to DataHub after the new service is in place.

## Error Handling

DataHub should return or raise structured errors with these categories:

- `cache_miss`: no usable cache exists.
- `source_unavailable`: upstream data source failed.
- `schema_invalid`: source or cache data does not match the expected schema.
- `empty_data`: source returned no rows for the request.
- `unsupported_dataset`: unknown dataset type or feed ID.

Backtest Web/API behavior should surface DataHub failures as structured API errors rather than unclassified 500 responses. CLI may keep synthetic fallback for demo workflows when primary stock data fails, but it should print that fallback explicitly. Required-feed failures already raise in the Web/API path and should continue to fail clearly.

## Testing Plan

Add tests for:

- Dataset registry returns the first-version dataset specs.
- Strategy feed IDs resolve to expected dataset requests.
- Cache lookup accepts covering ranges and rejects insufficient ranges.
- TTL expiration and `force_refresh` behavior trigger source calls.
- Normalizer enforces standard columns and date conversion.
- Metadata writes refresh success and failure records.
- `backtest/service.py` obtains all frames through DataHub.
- Data API endpoints return dataset, cache, and refresh status payloads.
- Compatibility wrapper functions still return the expected DataFrames.
- Golden compatibility tests compare wrapper outputs against the pre-migration loader behavior for columns, date dtype, date range trimming, row order, and representative values.

Existing tests around backtest results and strategy feeds should continue to pass.

## Migration Sequence

1. Add DataHub models, registry, normalization, cache, and metadata modules with tests.
2. Adapt existing AkShare loading logic into DataHub source adapters.
3. Add DataHub service orchestration.
4. Add backend API endpoints and API tests.
5. Refactor `backtest/service.py` to use DataHub.
6. Refactor CLI where safe and keep explicit synthetic fallback.
7. Turn `backtest.data_loader` public functions into compatibility wrappers. Existing scripts and `backtest/stock_selector.py` keep working through those wrappers and are not directly migrated to DataHub in v1.

## Acceptance Criteria

- Backtest orchestration resolves primary and required feeds through DataHub instead of concrete loader functions.
- Strategy classes remain pure trading logic and continue to declare data dependencies through `StrategySpec.required_data`.
- Supported datasets can be listed and refreshed through API endpoints.
- Cache metadata records are visible through API.
- TTL and `force_refresh` behavior are covered by tests.
- Refresh execution has bounded concurrency, per-cache-key locking, and deterministic deduplication behavior.
- Existing backtest, strategy, and server tests continue to pass.
