import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.data_loader import (  # noqa: E402
    load_market_data,
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

BREAKOUT_WINDOWS = [40, 60]
STOP_LOSS_PCTS = [0.05, 0.06, 0.08]
ATR_MULTIPLIERS = [1.5, 2.0, 2.5]
MAX_HOLD_DAYS = [20, 30, 40]
PARAM_ORDER = ('breakout_window', 'stop_loss_pct', 'atr_multiplier', 'max_hold_days')

SEARCH_OUTPUT = ROOT / 'data' / 'results' / 'citic_wave_search.txt'
DATA_DIR = ROOT / 'data'


def _format_pct(value: float) -> str:
    return f'{value:.2f}%'


def _format_params(params: dict[str, float | int]) -> str:
    return ', '.join(f'{name}={params[name]}' for name in PARAM_ORDER)


def _require_turnover_cache(start: str, end: str) -> None:
    cache_path = DATA_DIR / f'market_turnover_{start}_{end}.csv'
    if cache_path.exists():
        return
    raise RuntimeError(
        f'Missing required turnover cache: {cache_path}. '
        'This script uses a fixed evaluation window and expects the exact market_turnover cache files to already exist.'
    )


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

    _require_turnover_cache(START, TRAIN_END)
    _require_turnover_cache(VALID_START, END)
    _require_turnover_cache(START, END)


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
        params['stop_loss_pct'],
        params['atr_multiplier'],
        params['max_hold_days'],
    )


def _write_report(rows: list[dict]) -> None:
    SEARCH_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    header = [
        'citic_wave parameter search',
        f'symbol: {SYMBOL}',
        f'full_sample: {START}..{END}',
        f'train: {START}..{TRAIN_END}',
        f'validation: {VALID_START}..{END}',
        f'service_market_filter: False',
        f'risk_percent: {RISK_PERCENT}',
        'ranking: valid_return desc, valid_max_drawdown asc, full_return desc, full_max_drawdown asc',
        f'grid: breakout_window={BREAKOUT_WINDOWS}, stop_loss_pct={STOP_LOSS_PCTS}, atr_multiplier={ATR_MULTIPLIERS}, max_hold_days={MAX_HOLD_DAYS}',
        f'combinations: {len(rows)}',
        '',
        'rank | breakout_window | stop_loss_pct | atr_multiplier | max_hold_days | train_return | valid_return | valid_max_dd | full_return | full_max_dd | valid_trades | full_trades',
        '--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---:',
    ]

    body = []
    for index, row in enumerate(rows, start=1):
        params = row['params']
        body.append(
            f"{index} | {params['breakout_window']} | {params['stop_loss_pct']:.2f} | {params['atr_multiplier']:.1f} | {params['max_hold_days']} | "
            f"{_format_pct(row['train_return_pct'])} | {_format_pct(row['valid_return_pct'])} | {_format_pct(row['valid_max_drawdown_pct'])} | "
            f"{_format_pct(row['full_return_pct'])} | {_format_pct(row['full_max_drawdown_pct'])} | {row['valid_trade_count']} | {row['full_trade_count']}"
        )

    SEARCH_OUTPUT.write_text('\n'.join(header + body) + '\n', encoding='utf-8')


def main() -> None:
    _validate_inputs()
    rows = []
    grid = list(itertools.product(
        BREAKOUT_WINDOWS,
        STOP_LOSS_PCTS,
        ATR_MULTIPLIERS,
        MAX_HOLD_DAYS,
    ))
    total = len(grid)

    for index, (breakout_window, stop_loss_pct, atr_multiplier, max_hold_days) in enumerate(grid, start=1):
        params = {
            'breakout_window': breakout_window,
            'stop_loss_pct': stop_loss_pct,
            'atr_multiplier': atr_multiplier,
            'max_hold_days': max_hold_days,
        }
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
    print('Best result:')
    print(f'  end={END}')
    print(f"  params={_format_params(best['params'])}")
    print(f"  valid_return={_format_pct(best['valid_return_pct'])}")
    print(f"  full_return={_format_pct(best['full_return_pct'])}")
    print(f"  full_max_drawdown={_format_pct(best['full_max_drawdown_pct'])}")
    print(f'  output={SEARCH_OUTPUT}')


if __name__ == '__main__':
    main()
