# Repository Guidelines

## Project Structure & Module Organization

This repository contains a compact Python quant trading prototype. Strategy logic lives in `strategies/`, currently `strategies/swing_ma_boll.py`, which defines the Backtrader strategy and related data helper. Backtest entry points live in `backtest/`, currently `backtest/run_backtest.py`, which loads market data, falls back to synthetic data when network fetches fail, and runs the strategy through Backtrader. The README documents planned directories such as `data/`, `config/`, `docs/`, and `logs/`; create those only when they are needed. Keep generated CSVs under `data/` and logs under `logs/` so `.gitignore` excludes them.

## Build, Test, and Development Commands

- `pip install akshare backtrader pandas numpy`: install the runtime dependencies used by the backtest and synthetic data generator.
- `python backtest/run_backtest.py`: run the default backtest for symbol `000001` from `20200101` to `20231231`.
- `python backtest/run_backtest.py --symbol 600519 --start 20210101 --end 20231231 --cash 200000`: run a parameterized backtest.

There is no build step. Use a virtual environment such as `.venv/` for local work; it is ignored by git.

## Coding Style & Naming Conventions

Use standard Python 3 style with 4-space indentation. Prefer `snake_case` for functions, variables, and module names, and `PascalCase` for strategy classes such as `SwingStrategy`. Keep strategy parameters in Backtrader `params` tuples and make command-line options explicit in `argparse`. Avoid committing generated data, cache files, or local environment folders.

## Testing Guidelines

No automated test suite is present yet. For changes, at minimum run `python backtest/run_backtest.py` and verify it completes with either fetched AkShare data or synthetic fallback data. If adding tests, use `pytest`, place tests under `tests/`, and name files `test_*.py`. Focus coverage on signal generation, data normalization, and CLI argument handling.

## Commit & Pull Request Guidelines

The current history uses Conventional Commit prefixes, for example `feat:` and `fix:`. Continue with short, imperative subjects such as `fix: handle empty market data` or `feat: add RSI strategy`. Pull requests should explain the strategy or backtest behavior changed, list commands run, mention data sources used, and include before/after performance output when behavior changes.

## Security & Configuration Tips

Do not commit API keys, broker credentials, downloaded datasets, or private research outputs. Keep machine-specific configuration outside tracked files or in a future ignored `config/local.*` pattern.
