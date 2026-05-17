# Backtest Data Cache Design

## Purpose

Backtests should download A-share daily data only when needed. If a local CSV already covers the requested symbol and date range, the backtest should read from that file and slice the requested dates instead of calling AkShare again.

## Scope

This design implements coverage-based CSV reuse. It does not implement incremental updates. If no cached file fully covers the requested range, the system downloads the full requested range and saves it as a new CSV.

## Cache Layout

Cached market data will live under `data/`, which is already ignored by git for CSV files.

File naming pattern:

```text
data/{symbol}_{start}_{end}.csv
```

Example:

```text
data/000001_20200101_20231231.csv
```

The dates in the filename represent the full coverage range of the file.

## Data Flow

`backtest/run_backtest.py` will delegate market-data loading to a small helper. The helper will:

1. Ensure `data/` exists.
2. Scan `data/{symbol}_*.csv`.
3. Parse each filename for `symbol`, `start`, and `end`.
4. Select a cached file where `cached_start <= requested_start` and `cached_end >= requested_end`.
5. If one or more files match, read the best match and filter rows to the requested date range.
6. If none match, download data from AkShare, normalize columns, save the CSV, then return it.

When multiple files cover the range, choose the narrowest covering file so smaller reads are preferred.

## Error Handling

If AkShare download fails and no covering cache exists, keep the current behavior: log the failure and fall back to synthetic data. If a cache file exists but cannot be read or does not contain required columns, ignore that file and continue scanning other candidates.

## Public Interface

The CLI remains unchanged:

```bash
python backtest/run_backtest.py --symbol 600519 --start 20210101 --end 20231231 --cash 200000
```

No new required arguments are introduced.

## Verification

Manual verification should cover:

- First run for a range creates `data/{symbol}_{start}_{end}.csv`.
- Re-running the same range reads from cache.
- Running a smaller range covered by an existing CSV reads from cache and filters rows.
- Running a non-covered range downloads and saves a new CSV.
- Network failure with no cache still falls back to synthetic data.
