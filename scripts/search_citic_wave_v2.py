"""Focused search after discovering that ATR trailing actively hurts the
2024-09 big winner. This search keeps O1 (ATR stop) + O2 (bottom signal) +
O3 (top filter) but disables trailing, and searches a wider breakout/hold grid.
"""

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.data_loader import (  # noqa: E402
    load_market_data,
    load_market_turnover_data,
    load_security_etf_data,
    load_shanghai_composite,
)
from backtest.service import BacktestRequest, run_backtest_service  # noqa: E402


TRAIN_END = '20241231'
VALID_START = '20250101'
SYMBOL = '600030'
START = '20210531'
END = '20260529'
CASH = 100000.0
RISK_PERCENT = 0.95

# Trailing intentionally disabled (very wide + late activation) so the
# 2024-09 bull move is not clipped.
TRAILING_ATR_MULT = 99.0
TRAILING_START_BARS = 999

# O3 + O1 grid
BREAKOUT_WINDOWS = [40, 60]
ATR_MULTIPLIERS = [1.5]
MAX_EXTENSION_PCTS = [0.20, 0.30]
MAX_HOLD_DAYS = [30, 60, 90]

# O2 grid (bottom signal)
BOTTOM_J_THRESHOLDS = [5, 20]
BOTTOM_VOL_MULTS = [1.5, 2.5]

PARAM_ORDER = (
    'breakout_window',
    'atr_multiplier',
    'max_extension_pct',
    'max_hold_days',
    'bottom_j_threshold',
    'bottom_vol_mult',
)

SEARCH_OUTPUT = ROOT / 'data' / 'results' / 'citic_wave_search_v2.txt'


def _format_pct(value: float) -> str:
    return f'{value:.2f}%'


def _format_params(params: dict[str, float | int]) -> str:
    return ', '.join(f'{name}={params[name]}' for name in PARAM_ORDER)


def _ensure_turnover_available(start: str, end: str) -> None:
    df = load_market_turnover_data(start, end)
    if df is None or df.empty:
        raise RuntimeError(f'Unable to load market turnover data for {start}..{end}.')


def _validate_inputs() -> None:
    stock_df = load_market_data(SYMBOL, START, END)
    if stock_df is None or stock_df.empty:
        raise RuntimeError(f'No market data available for {SYMBOL} in {START}..{END}.')

    sh_df = load_shanghai_composite(START, END)
    if sh_df is None or sh_df.empty:
        raise RuntimeError('Shanghai composite data is required for citic_wave evaluation.')

    etf_df = load_security_etf_data(START, END)
    if etf_df is None or etf_df.empty:
        raise RuntimeError('Security ETF data is required for citic_wave evaluation.')

    _ensure_turnover_available(START, TRAIN_END)
    _ensure_turnover_available(VALID_START, END)
    _ensure_turnover_available(START, END)


def _run_once(start: str, end: str, params: dict[str, float | int]):
    request = BacktestRequest(
        symbol=SYMBOL,
        start=start,
        end=end,
        cash=CASH,
        use_market_filter=False,
        risk_percent=RISK_PERCENT,
        strategy_id='citic_wave',
        strategy_params=params,
    )
    return run_backtest_service(request)


def _rank_key(row: dict) -> tuple:
    params = row['params']
    return (
        -row['valid_return_pct'],
        row['valid_max_drawdown_pct'],
        -row['full_return_pct'],
        row['full_max_drawdown_pct'],
        params['breakout_window'],
        params['atr_multiplier'],
        params['max_extension_pct'],
        params['max_hold_days'],
        params['bottom_j_threshold'],
        params['bottom_vol_mult'],
    )


def _meets_target(row: dict) -> bool:
    return (
        row['full_return_pct'] > 20.0
        and row['valid_return_pct'] > 10.0
        and row['full_max_drawdown_pct'] <= 20.0
    )


def _write_report(rows: list[dict]) -> None:
    SEARCH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    header = [
        'citic_wave focused search (trailing disabled)',
        f'symbol: {SYMBOL}',
        f'full_sample: {START}..{END}',
        f'train: {START}..{TRAIN_END}',
        f'validation: {VALID_START}..{END}',
        f'service_market_filter: False',
        f'risk_percent: {RISK_PERCENT}',
        f'trailing_atr_mult: {TRAILING_ATR_MULT} (effectively disabled)',
        f'trailing_start_bars: {TRAILING_START_BARS} (effectively disabled)',
        'ranking: valid_return desc, valid_max_drawdown asc, full_return desc, full_max_drawdown asc',
        f'grid: breakout_window={BREAKOUT_WINDOWS}, atr_multiplier={ATR_MULTIPLIERS}, '
        f'max_extension_pct={MAX_EXTENSION_PCTS}, max_hold_days={MAX_HOLD_DAYS}, '
        f'bottom_j_threshold={BOTTOM_J_THRESHOLDS}, bottom_vol_mult={BOTTOM_VOL_MULTS}',
        f'combinations: {len(rows)}',
        'target: full_return > 20%, valid_return > 10%, full_max_drawdown <= 20%',
        '',
        'rank | bw | atr | ext | mh | bj | bvm | train_ret | valid_ret | valid_dd | full_ret | full_dd | valid_n | full_n',
        '--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---:',
    ]

    body = []
    for index, row in enumerate(rows, start=1):
        params = row['params']
        marker = ' *' if _meets_target(row) else '  '
        body.append(
            f"{index}{marker}| {params['breakout_window']} | {params['atr_multiplier']:.1f} | "
            f"{params['max_extension_pct']:.2f} | {params['max_hold_days']} | "
            f"{params['bottom_j_threshold']} | {params['bottom_vol_mult']:.1f} | "
            f"{_format_pct(row['train_return_pct'])} | {_format_pct(row['valid_return_pct'])} | "
            f"{_format_pct(row['valid_max_drawdown_pct'])} | "
            f"{_format_pct(row['full_return_pct'])} | {_format_pct(row['full_max_drawdown_pct'])} | "
            f"{row['valid_trade_count']} | {row['full_trade_count']}"
        )

    target_hits = [row for row in rows if _meets_target(row)]
    summary = [
        '',
        f'target_hits: {len(target_hits)}/{len(rows)}',
    ]
    if target_hits:
        best = target_hits[0]
        summary.append(
            f"best_target: params={_format_params(best['params'])} "
            f"valid={_format_pct(best['valid_return_pct'])} "
            f"full={_format_pct(best['full_return_pct'])} "
            f"full_dd={_format_pct(best['full_max_drawdown_pct'])}"
        )
    else:
        summary.append('best_target: none')

    # Also surface the top by full_return_pct regardless of validation,
    # so the caller can see the "training-friendly" best.
    by_full = sorted(rows, key=lambda r: -r['full_return_pct'])
    best_full = by_full[0]
    summary.append(
        f"best_full_only: params={_format_params(best_full['params'])} "
        f"valid={_format_pct(best_full['valid_return_pct'])} "
        f"full={_format_pct(best_full['full_return_pct'])} "
        f"full_dd={_format_pct(best_full['full_max_drawdown_pct'])}"
    )

    SEARCH_OUTPUT.write_text(
        '\n'.join(header + body + summary) + '\n',
        encoding='utf-8',
    )


def main() -> None:
    _validate_inputs()
    rows = []
    grid = list(itertools.product(
        BREAKOUT_WINDOWS,
        ATR_MULTIPLIERS,
        MAX_EXTENSION_PCTS,
        MAX_HOLD_DAYS,
        BOTTOM_J_THRESHOLDS,
        BOTTOM_VOL_MULTS,
    ))
    total = len(grid)
    print(f'Running {total} combinations...')

    for index, (bw, atr, ext, mh, bj, bvm) in enumerate(grid, start=1):
        params = {
            'breakout_window': bw,
            'atr_multiplier': atr,
            'max_extension_pct': ext,
            'max_hold_days': mh,
            'bottom_j_threshold': bj,
            'bottom_vol_mult': bvm,
            'trailing_atr_mult': TRAILING_ATR_MULT,
            'trailing_start_bars': TRAILING_START_BARS,
        }
        if index % 20 == 0 or index == 1:
            print(f'[{index}/{total}] {_format_params(params)}')
        train = _run_once(START, TRAIN_END, params)
        valid = _run_once(VALID_START, END, params)
        full = _run_once(START, END, params)
        rows.append({
            'params': params,
            'train_return_pct': float(train.total_return_pct),
            'valid_return_pct': float(valid.total_return_pct),
            'valid_max_drawdown_pct': float(valid.max_drawdown_pct),
            'valid_trade_count': int(valid.trade_count),
            'full_return_pct': float(full.total_return_pct),
            'full_max_drawdown_pct': float(full.max_drawdown_pct),
            'full_trade_count': int(full.trade_count),
        })

    rows.sort(key=_rank_key)
    _write_report(rows)

    best = rows[0]
    target_hits = [row for row in rows if _meets_target(row)]
    print('Best by rank:')
    print(f"  params={_format_params(best['params'])}")
    print(f"  valid_return={_format_pct(best['valid_return_pct'])}")
    print(f"  full_return={_format_pct(best['full_return_pct'])}")
    print(f"  full_max_drawdown={_format_pct(best['full_max_drawdown_pct'])}")
    print(f"  target_hits: {len(target_hits)}/{len(rows)}")
    print(f"  output={SEARCH_OUTPUT}")


if __name__ == '__main__':
    main()
