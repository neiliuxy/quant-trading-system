# Backtest Data Cache Design

## Purpose

Backtests should download A-share daily data only when needed. If a local CSV already covers the requested symbol and date range, the backtest should read from that file and slice the requested dates instead of calling AkShare again.

## Scope

This design implements coverage-based CSV reuse. It does not implement incremental updates. If no cached file fully covers the requested range, the system downloads the full requested range and saves it as a new CSV.

It also changes the default backtest date range. `backtest/run_backtest.py` and `backtest/stock_selector.py` should default to the most recent three years relative to the run date instead of hard-coded `20200101` to `20231231`.

## Default Date Range

Add a shared helper such as `get_default_date_range(years=3)`.

When `start` or `end` is omitted:

1. `end` defaults to the current local date formatted as `YYYYMMDD`.
2. `start` defaults to the date three years before `end`, also formatted as `YYYYMMDD`.
3. If the user supplies only `start`, keep it and default `end` to the current local date.
4. If the user supplies only `end`, keep it and default `start` to three years before that `end` date.

The CLI keeps optional `--start` and `--end` arguments. Help text should state that omitted dates default to the most recent three years.

## Cache Layout

Cached market data will live under `data/`, which is already ignored by git for CSV files.

New file naming pattern:

```text
data/{symbol}_{stock_name}_{start}_{end}.csv
```

Example:

```text
data/601318_中国平安_20230517_20260517.csv
```

The dates in the filename represent the full coverage range of the file. `stock_name` is a human-readable label only; cache matching should use `symbol`, `start`, and `end`.

Keep backward compatibility with existing cache files that use the old pattern:

```text
data/{symbol}_{start}_{end}.csv
```

Stock names should be sanitized for Windows filenames by removing characters that are not allowed in paths.

## Data Flow

`backtest/run_backtest.py` will delegate market-data loading to a small helper. The helper will:

1. Ensure `data/` exists.
2. Scan `data/{symbol}_*.csv`.
3. Parse each filename for either `symbol`, `stock_name`, `start`, and `end`, or the legacy `symbol`, `start`, and `end`.
4. Select a cached file where `cached_start <= requested_start` and `cached_end >= requested_end`.
5. If one or more files match, read the best match and filter rows to the requested date range.
6. If none match, download data from AkShare, normalize columns, query the stock name, save the CSV, then return it.

When multiple files cover the range, choose the narrowest covering file so smaller reads are preferred.

## Stock Name Lookup

Only query the stock name when writing a new cache file. A cache hit should not call AkShare for either market data or stock-name lookup.

Use an AkShare stock list endpoint to map `symbol` to its display name. If name lookup fails, continue the backtest and save the cache with a fallback label such as `UNKNOWN`.

## Error Handling

If AkShare download fails and no covering cache exists, keep the current behavior: log the failure and fall back to synthetic data. If a cache file exists but cannot be read or does not contain required columns, ignore that file and continue scanning other candidates.

## Public Interface

The CLI remains compatible:

```bash
python backtest/run_backtest.py --symbol 600519 --start 20210101 --end 20231231 --cash 200000
```

No new required arguments are introduced. Running without `--start` or `--end` uses the most recent three years. The same default-date behavior applies to `backtest/stock_selector.py`.

## Verification

Manual verification should cover:

- First run for a range creates `data/{symbol}_{stock_name}_{start}_{end}.csv`.
- Re-running the same range reads from cache.
- Running a smaller range covered by an existing CSV reads from cache and filters rows.
- Running a non-covered range downloads and saves a new CSV.
- Network failure with no cache still falls back to synthetic data.
- Running `python backtest/run_backtest.py` without dates uses the current date and the date three years earlier.
- Running `backtest/stock_selector.py` uses the same default three-year range.
- New cache filenames include the stock name, while legacy cache filenames remain readable.
