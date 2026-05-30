# Multi-Strategy Backtest Design

## Goal

Support multiple backtest strategies instead of the current single hard-coded strategy.
Users must be able to choose the strategy from a dropdown in the web UI before starting a backtest.
Each strategy must be implemented as a module and must declare its own parameters.

The first two strategies in scope are:

1. Existing MA + Bollinger trend strategy
2. New Bollinger reversal strategy

## Scope

### In scope

- Strategy abstraction layer in Python
- Strategy registry with metadata and parameter schema
- Web UI strategy dropdown
- Dynamic rendering of strategy-specific parameters
- API payload changes for strategy selection and strategy params
- Job cache-key changes so different strategies do not reuse the same result
- Job history/result display includes the selected strategy
- Tests for registry, request plumbing, and cache-key behavior

### Out of scope

- Strategy optimization UI
- Strategy comparison UI beyond what already exists
- Multi-strategy portfolio execution in one run
- Live trading

## Current State

The backtest path is currently fixed to `SwingStrategy` in `backtest/service.py`.
The web form sends a single set of trading inputs.
`server/jobs.py` builds the run key from the normalized request, market config hash, and code version.
That means strategy selection must flow through:

`web/src/App.tsx -> web/src/api.ts -> server/api.py -> server/models.py -> backtest/service.py -> server/jobs.py`

## Design

### Strategy abstraction

Add a small strategy contract and a registry.

Each strategy module must provide:

- `id`: stable string, used by API and run key
- `name`: human-readable label for the UI
- `strategy_class`: the Backtrader class
- `params`: ordered parameter metadata for the UI and API
- `defaults`: default values for missing params

The registry is the single source of truth for available strategies.
Adding a new strategy should mainly mean adding a module and registering it.

Recommended file layout:

```text
strategies/
  base.py
  registry.py
  swing_ma_boll.py
  bollinger_reversal.py
```

### Strategy parameters

Split request fields into two groups:

1. Common backtest fields
   - `symbol`
   - `start`
   - `end`
   - `cash`
   - `use_market_filter`
   - `risk_percent`

2. Strategy-specific fields
   - `strategy_id`
   - `strategy_params`

`strategy_params` should be a plain JSON object from the UI.
The backtest service resolves missing values using the selected strategy's defaults.

This keeps the API stable when new strategies are added and avoids hard-coding one parameter list into the whole app.

### Strategy behavior

#### Existing trend strategy

Keep the current MA + Bollinger behavior in a module, but move it behind the registry.
No behavior change is required for the first version beyond accepting its params through the new strategy interface.

#### New Bollinger reversal strategy

Add a mean-reversion strategy with this rule:

- Buy when price moves back above the lower Bollinger band after having been below it
- Sell when price reaches the middle band or upper band

Keep the first implementation simple:

- Bollinger period is configurable
- Bollinger deviation factor is configurable
- Entry/exit logic stays fixed

### API changes

Add an endpoint to expose available strategies and their parameter metadata.

Suggested endpoint:

- `GET /api/strategies`

Returned data should include:

- `id`
- `name`
- `description`
- ordered parameter metadata
- default values

Update job creation payload:

- `strategy_id: string`
- `strategy_params: object`

Existing job endpoints should continue to work, but they must store and return the selected strategy fields.

### Job and cache key changes

The `run_key` must include:

- normalized common request fields
- `strategy_id`
- normalized `strategy_params`
- market config hash
- code version

This prevents a trend-strategy result from being reused for the reversal strategy, or vice versa.

The SQLite jobs table must store:

- `strategy_id`
- `strategy_params_json`

Because existing local databases may already have a `jobs` table, `init_db()` must perform a lightweight schema migration:

- add `strategy_id` with a default value for the current trend strategy
- add `strategy_params_json` with defaults matching the current trend strategy
- keep old completed jobs readable after startup

Historical jobs and result artifacts should show which strategy was used.

### Web UI changes

The web form should work like this:

1. Load the available strategies from the API
2. Default to the current trend strategy
3. When the user changes strategy, render only that strategy's parameters
4. Submit the selected strategy id plus its params with the rest of the backtest form

The strategy dropdown should be part of the main run form.
Existing charts, job history, and result panels should remain unchanged except for showing the strategy name where useful.

## Validation Rules

- Unknown `strategy_id` returns a 400-level error
- Strategy params are merged with defaults before execution
- Unknown extra params should be rejected rather than silently ignored
- Missing params fall back to strategy defaults

## Testing

Add focused tests for:

- registry returns both strategies
- run key changes when only strategy changes
- run key changes when strategy params change
- backtest service can execute each registered strategy
- API can create a job with strategy fields
- frontend request types compile with the new payload shape

Keep test coverage narrow and behavior-based.

## Implementation Order

1. Add strategy contract and registry
2. Move existing strategy behind registry
3. Add Bollinger reversal strategy
4. Extend request, API, and DB storage
5. Add strategy dropdown and dynamic params in the web UI
6. Update tests

## Open Assumptions

- The first version only needs a small, explicit parameter schema rather than a generic nested form builder.
- Strategy params can be represented as JSON objects in the API and database.
- Historical jobs only need the lightweight column-add migration described above; no separate migration framework is required.
