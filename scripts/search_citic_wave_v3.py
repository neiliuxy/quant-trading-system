"""Search around the breakthrough configuration (shock_vol_mult=3.0-3.5,
shock_intraday_pct=0.04, shock_near_low_pct=0.15) to find a stable set
that passes both full-sample > 20% and validation > 10% targets."""
import itertools
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import backtrader as bt

from backtest.data_loader import (
    load_market_data,
    load_market_turnover_data,
    load_security_etf_data,
    load_shanghai_composite,
)
from backtest.service import BacktestRequest, run_backtest_service


SYMBOL = '600030'
TRAIN_END = '20241231'
VALID_START = '20250101'
START = '20210531'
END = '20260529'
CASH = 100000.0
RISK_PERCENT = 0.95
TRAILING_ATR_MULT = 99.0
TRAILING_START_BARS = 999

BREAKOUT_WINDOWS = [60]
ATR_MULTIPLIERS = [1.5]
MAX_EXTENSION_PCTS = [0.20, 0.30]
MAX_HOLD_DAYS = [30]
SHOCK_VOL_MULTS = [3.0, 3.5]
SHOCK_INTRADAY_PCTS = [0.04]
SHOCK_NEAR_LOW_PCTS = [0.15]

OUTPUT = os.path.join(ROOT, 'data', 'results', 'citic_wave_search_v3.txt')


def _format_pct(value):
    return f'{value:.2f}%'


def _run(start, end, params):
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


def main():
    grid = list(itertools.product(
        BREAKOUT_WINDOWS, ATR_MULTIPLIERS, MAX_EXTENSION_PCTS,
        MAX_HOLD_DAYS, SHOCK_VOL_MULTS, SHOCK_INTRADAY_PCTS, SHOCK_NEAR_LOW_PCTS,
    ))
    rows = []
    for bw, atr, ext, mh, svm, sip, nlp in grid:
        params = {
            'breakout_window': bw,
            'atr_multiplier': atr,
            'max_extension_pct': ext,
            'max_hold_days': mh,
            'shock_vol_mult': svm,
            'shock_intraday_pct': sip,
            'shock_near_low_pct': nlp,
            'trailing_atr_mult': TRAILING_ATR_MULT,
            'trailing_start_bars': TRAILING_START_BARS,
        }
        train = _run(START, TRAIN_END, params)
        valid = _run(VALID_START, END, params)
        full = _run(START, END, params)
        rows.append({
            'params': params,
            'train_return_pct': float(train.total_return_pct),
            'valid_return_pct': float(valid.total_return_pct),
            'valid_max_dd_pct': float(valid.max_drawdown_pct),
            'full_return_pct': float(full.total_return_pct),
            'full_max_dd_pct': float(full.max_drawdown_pct),
        })

    rows.sort(key=lambda r: (-r['valid_return_pct'], r['valid_max_dd_pct'],
                             -r['full_return_pct'], r['full_max_dd_pct']))

    lines = [
        'citic_wave v3 search (shock signal enabled, trailing disabled)',
        f'grid: bw={BREAKOUT_WINDOWS} atr={ATR_MULTIPLIERS} ext={MAX_EXTENSION_PCTS} '
        f'mh={MAX_HOLD_DAYS} svm={SHOCK_VOL_MULTS} sip={SHOCK_INTRADAY_PCTS} nlp={SHOCK_NEAR_LOW_PCTS}',
        f'combinations: {len(rows)}',
        'target: full_return > 20% AND valid_return > 10%',
        '',
        'rank | svm | sip | nlp | bw | ext | mh | atr | full_ret | train_ret | valid_ret | full_dd | valid_dd | target',
        '--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---',
    ]
    for idx, row in enumerate(rows, 1):
        p = row['params']
        target = row['full_return_pct'] > 20 and row['valid_return_pct'] > 10
        lines.append(
            f"{idx} | {p['shock_vol_mult']} | {p['shock_intraday_pct']:.2f} | {p['shock_near_low_pct']:.2f} | "
            f"{p['breakout_window']} | {p['max_extension_pct']:.2f} | {p['max_hold_days']} | {p['atr_multiplier']} | "
            f"{_format_pct(row['full_return_pct'])} | {_format_pct(row['train_return_pct'])} | "
            f"{_format_pct(row['valid_return_pct'])} | {_format_pct(row['full_max_dd_pct'])} | "
            f"{_format_pct(row['valid_max_dd_pct'])} | {'YES' if target else 'no'}"
        )
    hits = [r for r in rows if r['full_return_pct'] > 20 and r['valid_return_pct'] > 10]
    lines.extend([
        '',
        f'target_hits: {len(hits)}/{len(rows)}',
    ])
    if hits:
        best = hits[0]
        p = best['params']
        lines.append(
            f"best_target: svm={p['shock_vol_mult']} sip={p['shock_intraday_pct']} nlp={p['shock_near_low_pct']} "
            f"bw={p['breakout_window']} ext={p['max_extension_pct']} mh={p['max_hold_days']} atr={p['atr_multiplier']} "
            f"full={_format_pct(best['full_return_pct'])} valid={_format_pct(best['valid_return_pct'])}"
        )
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
