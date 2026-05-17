"""市场数据加载器，带 CSV 缓存支持。

按 docs/superpowers/specs/2026-05-17-backtest-data-cache-design.md 规范实现。
"""

import os
import re
import glob
import time
import pandas as pd
import akshare as ak

# 项目根目录下的缓存路径
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'data')

STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume']

# AkShare 中文列名 → 标准英文列名
_AKSHARE_COLUMN_MAP = {
    '日期': 'date',
    '开盘': 'open',
    '最高': 'high',
    '最低': 'low',
    '收盘': 'close',
    '成交量': 'volume',
}


def _parse_filename(filepath):
    """解析 data/{symbol}_{start(8)}_{end(8)}.csv，返回 (symbol, start, end) 或 None。"""
    basename = os.path.basename(filepath)
    m = re.match(r'^(\d+)_(\d{8})_(\d{8})\.csv$', basename)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None


def load_market_data(symbol, start, end):
    """
    加载市场数据，优先使用本地 CSV 缓存。

    Args:
        symbol: 股票代码，如 '000001'
        start:  开始日期，如 '20200101'
        end:    结束日期，如 '20231231'

    Returns:
        pd.DataFrame，含 date/open/high/low/close/volume 列，date 已转为 datetime。

    Raises:
        Exception: AkShare 下载失败且无可用缓存时抛出。
    """
    os.makedirs(_CACHE_DIR, exist_ok=True)

    # ── 1. 扫描缓存 ──────────────────────────────────────
    pattern = os.path.join(_CACHE_DIR, f'{symbol}_*.csv')
    candidates = []
    for filepath in glob.glob(pattern):
        parsed = _parse_filename(filepath)
        if parsed is None:
            continue
        _, cached_start, cached_end = parsed
        if cached_start <= start and cached_end >= end:
            candidates.append((filepath, cached_start, cached_end))

    # 按覆盖范围宽度升序（窄优先）
    candidates.sort(key=lambda x: int(x[2]) - int(x[1]))

    for filepath, _, _ in candidates:
        try:
            df = pd.read_csv(filepath)
            if set(df.columns) != set(STANDARD_COLUMNS):
                continue
            df['date'] = pd.to_datetime(df['date'])
            mask = (df['date'] >= pd.to_datetime(start)) & (
                df['date'] <= pd.to_datetime(end))
            df = df[mask].copy()
            if not df.empty:
                print(f'从缓存读取: {os.path.basename(filepath)}')
                return df
        except Exception:
            continue  # 文件损坏，尝试下一个

    # ── 2. 下载并缓存 ────────────────────────────────────
    print(f'正在获取 {symbol} 历史数据...')

    # 2a. 东方财富 (stock_zh_a_hist)，重试 3 次
    last_err = None
    for attempt in range(1, 4):
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol, period='daily',
                start_date=start, end_date=end)
            df = df[list(_AKSHARE_COLUMN_MAP.keys())]
            df.columns = STANDARD_COLUMNS
            last_err = None
            break
        except Exception as e:
            last_err = e
            print(f'东方财富数据源请求失败(第{attempt}次): {e}')
            if attempt < 3:
                time.sleep(2)

    if last_err is not None:
        # 2b. 腾讯备用 (stock_zh_a_hist_tx)，重试 2 次
        print('切换至腾讯数据源...')
        prefix = 'sh' if symbol.startswith('6') else 'sz'
        for attempt in range(1, 3):
            try:
                df = ak.stock_zh_a_hist_tx(
                    symbol=f'{prefix}{symbol}',
                    start_date=start, end_date=end)
                df = df.rename(columns={'amount': 'volume'})
                df = df[STANDARD_COLUMNS]
                break
            except Exception as e:
                print(f'腾讯数据源请求失败(第{attempt}次): {e}')
                if attempt < 2:
                    time.sleep(1)
        else:
            raise RuntimeError(
                f'所有数据源均无法获取 {symbol} 的历史数据') from last_err

    cache_path = os.path.join(_CACHE_DIR, f'{symbol}_{start}_{end}.csv')
    df.to_csv(cache_path, index=False)

    df['date'] = pd.to_datetime(df['date'])
    return df
