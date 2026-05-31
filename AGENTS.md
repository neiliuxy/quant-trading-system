# Repository Guidelines

## Project Structure & Module Organization

This repository contains a compact Python quant trading prototype. Strategy logic lives in `strategies/`, with a multi-strategy registry (`strategies/registry.py`) and three strategies: `swing_ma_boll.py` (Swing MA + Bollinger), `bollinger_reversal.py` (Bollinger Reversal), and `b1_strategy.py` (B1). Each strategy defines a `StrategySpec` with typed parameters. Backtest entry points live in `backtest/`, with `run_backtest.py` for CLI and `service.py` for programmatic/Web usage; both load market data and fall back to synthetic data when network fetches fail. An optional market scoring system lives under `market/`. A FastAPI + React/Vite web dashboard lives under `server/` and `web/`. Generated CSVs go in `data/` and logs in `logs/`, both gitignored.

## Build, Test, and Development Commands

- `pip install -r requirements.txt`: install all runtime dependencies.
- `python backtest/run_backtest.py`: run the default CLI backtest for symbol `000001` from `20200101` to `20231231`.
- `python backtest/run_backtest.py --symbol 600519 --start 20210101 --end 20231231 --cash 200000`: run a parameterized CLI backtest.
- `python -m pytest -q tests/`: run the test suite.
- `python server/main.py`: start the Web backend (FastAPI, port 8000).
- `cd web && npm run dev`: start the Web frontend (Vite, port 5173).

There is no build step. Use a virtual environment such as `.venv/` for local work; it is ignored by git.

## Coding Style & Naming Conventions

Use standard Python 3 style with 4-space indentation. Prefer `snake_case` for functions, variables, and module names, and `PascalCase` for strategy classes such as `SwingStrategy`. Keep strategy parameters in Backtrader `params` tuples and make command-line options explicit in `argparse`. Avoid committing generated data, cache files, or local environment folders.

## Testing Guidelines

A pytest test suite exists under `tests/` with coverage on strategy signal generation, market scoring indicators, backtest service, API endpoints, and integration flows. Run `python -m pytest -q tests/` to verify. When adding tests, use `pytest`, place tests under `tests/`, and name files `test_*.py`. Focus coverage on signal generation, data normalization, CLI argument handling, and API endpoints.

## Commit & Pull Request Guidelines

The current history uses Conventional Commit prefixes, for example `feat:` and `fix:`. Continue with short, imperative subjects such as `fix: handle empty market data` or `feat: add RSI strategy`. Pull requests should explain the strategy or backtest behavior changed, list commands run, mention data sources used, and include before/after performance output when behavior changes.

## Security & Configuration Tips

Do not commit API keys, broker credentials, downloaded datasets, or private research outputs. Keep machine-specific configuration outside tracked files or in a future ignored `config/local.*` pattern.
