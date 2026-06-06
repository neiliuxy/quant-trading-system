"""市场数据加载器，带 CSV 缓存支持。

按 docs/superpowers/specs/2026-05-17-backtest-data-cache-design.md 规范实现。
"""

import os
import re
import glob
import time
from datetime import date, datetime
import pandas as pd
import akshare as ak

# 项目根目录下的缓存路径
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'data')

STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume']
INDEX_STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']

# AkShare 中文列名 → 标准英文列名
_AKSHARE_COLUMN_MAP = {
    '日期': 'date',
    '开盘': 'open',
    '最高': 'high',
    '最低': 'low',
    '收盘': 'close',
    '成交量': 'volume',
    '成交额': 'amount',
}


def _format_date(value):
    """将 date/datetime/字符串日期统一成 YYYYMMDD。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime('%Y%m%d')
    if isinstance(value, date):
        return value.strftime('%Y%m%d')

    text = str(value).strip()
    if re.fullmatch(r'\d{8}', text):
        return text
    return pd.to_datetime(text).strftime('%Y%m%d')


def _shift_years(value, years):
    """按年份平移日期，处理 2 月 29 日落到非闰年的情况。"""
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def get_default_date_range(years=3):
    """返回最近 years 年的默认日期范围，格式为 (YYYYMMDD, YYYYMMDD)。"""
    end_date = date.today()
    start_date = _shift_years(end_date, -years)
    return _format_date(start_date), _format_date(end_date)


def resolve_date_range(start=None, end=None, years=3):
    """解析可选日期边界，未传时默认最近 years 年。"""
    default_start, default_end = get_default_date_range(years)
    if start is None and end is None:
        return default_start, default_end
    if start is None:
        end_text = _format_date(end)
        start_date = _shift_years(pd.to_datetime(end_text).date(), -years)
        return _format_date(start_date), end_text
    if end is None:
        return _format_date(start), default_end
    return _format_date(start), _format_date(end)


def _sanitize_filename_part(value):
    """清理 Windows 文件名非法字符。"""
    text = str(value or 'UNKNOWN').strip() or 'UNKNOWN'
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
    text = re.sub(r'\s+', '', text)
    return text or 'UNKNOWN'


def _get_stock_name(symbol):
    """通过 AkShare 股票列表查询股票名称，失败时返回 UNKNOWN。"""
    try:
        df = ak.stock_info_a_code_name()
        column_sets = [
            ('code', 'name'),
            ('代码', '名称'),
            ('证券代码', '证券简称'),
        ]
        for code_col, name_col in column_sets:
            if code_col not in df.columns or name_col not in df.columns:
                continue
            codes = df[code_col].astype(str).str.zfill(6)
            matched = df.loc[codes == str(symbol).zfill(6), name_col]
            if not matched.empty:
                return _sanitize_filename_part(matched.iloc[0])
    except Exception as e:
        print(f'股票名称查询失败: {e}')
    return 'UNKNOWN'


def _parse_filename(filepath):
    """解析新旧缓存文件名，返回 (symbol, start, end) 或 None。"""
    basename = os.path.basename(filepath)
    m = re.match(r'^(\d+)_(.+)_(\d{8})_(\d{8})\.csv$', basename)
    if m:
        return m.group(1), m.group(3), m.group(4)

    m = re.match(r'^(\d+)_(\d{8})_(\d{8})\.csv$', basename)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None


def _read_cached_frame(cache_path, expected_columns):
    """Read a cached CSV and normalize the date column."""
    if not os.path.exists(cache_path):
        return None
    try:
        df = pd.read_csv(cache_path)
    except Exception:
        return None
    if list(df.columns) != list(expected_columns):
        return None
    df['date'] = pd.to_datetime(df['date'])
    return df


def load_shanghai_composite(start, end):
    """
    加载上证综合指数数据。

    Args:
        start: 开始日期，如 '20200101'
        end:   结束日期，如 '20231231'

    Returns:
        pd.DataFrame，含 date/open/high/low/close/volume 列，date 已转为 datetime。
        加载失败时返回 None。
    """
    start, end = resolve_date_range(start, end)
    os.makedirs(_CACHE_DIR, exist_ok=True)

    # ── 1. 扫描缓存 ──────────────────────────────────────
    pattern = os.path.join(_CACHE_DIR, 'sh000001_*.csv')
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
            if set(df.columns) != set(INDEX_STANDARD_COLUMNS):
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
    print('正在获取上证综合指数历史数据...')

    # 2a. AkShare stock_zh_index_daily（腾讯数据源），重试 3 次
    # 改用此接口的原因：ak.index_zh_a_hist（东方财富）在部分代理环境下
    # 无法连通（80.push2.eastmoney.com 被代理拦截），而腾讯接口稳定可用。
    # 该接口返回全历史 OHLCV（volume 单位为「手」，1 手=100 股），
    # 不含「成交额」，我们用 close*volume*100 作为合理近似（单位：元）。
    last_err = None
    for attempt in range(1, 4):
        try:
            full_df = ak.stock_zh_index_daily(symbol='sh000001')
            full_df['date'] = pd.to_datetime(full_df['date'])
            mask = (full_df['date'] >= pd.to_datetime(start)) & (
                full_df['date'] <= pd.to_datetime(end))
            df = full_df[mask].copy()
            if 'amount' not in df.columns:
                df['amount'] = df['close'] * df['volume'] * 100
            last_err = None
            break
        except Exception as e:
            last_err = e
            print(f'上证指数数据源请求失败(第{attempt}次): {e}')
            if attempt < 3:
                time.sleep(2)
    else:
        print(f'无法获取上证综合指数的历史数据，将使用股票数据作为替代')
        return None

    cache_path = os.path.join(_CACHE_DIR, f'sh000001_上证综合指数_{start}_{end}.csv')
    df.to_csv(cache_path, index=False)
    return df


def load_security_etf_data(start, end, symbol='sh512880'):
    """Load a security ETF series and normalize it to index-style columns."""
    start, end = resolve_date_range(start, end)
    os.makedirs(_CACHE_DIR, exist_ok=True)

    cache_path = os.path.join(_CACHE_DIR, f'{symbol}_{start}_{end}.csv')
    cached_df = _read_cached_frame(cache_path, INDEX_STANDARD_COLUMNS)
    if cached_df is not None:
        return cached_df

    df = ak.fund_etf_hist_sina(symbol=symbol).copy()
    if df.empty:
        return pd.DataFrame(columns=INDEX_STANDARD_COLUMNS)

    df['date'] = pd.to_datetime(df['date'])
    mask = (df['date'] >= pd.to_datetime(start)) & (df['date'] <= pd.to_datetime(end))
    df = df.loc[mask, STANDARD_COLUMNS].copy()
    df['amount'] = 0.0
    df = df[INDEX_STANDARD_COLUMNS]
    df.to_csv(cache_path, index=False)
    return df


def _fetch_sse_turnover(date_text: str) -> float:
    """Fetch SSE stock turnover for one trading day."""
    df = ak.stock_sse_deal_daily(date=date_text)
    row = df.loc[df['单日情况'] == '成交金额']
    if row.empty:
        raise RuntimeError(f'SSE turnover not found for {date_text}')
    if '股票' in row.columns and pd.notna(row['股票'].iloc[0]):
        return float(row['股票'].iloc[0])
    columns = [col for col in ['主板A', '主板B', '科创板'] if col in row.columns]
    return float(row[columns].fillna(0).sum(axis=1).iloc[0])


def _fetch_szse_turnover(date_text: str) -> float:
    """Fetch SZSE stock turnover for one trading day."""
    df = ak.stock_szse_summary(date=date_text)
    exact_row = df.loc[df['证券类别'] == '股票']
    if not exact_row.empty:
        return float(exact_row['成交金额'].iloc[0])
    stock_rows = df[df['证券类别'].astype(str).str.contains('股票|A股|B股', na=False)]
    if stock_rows.empty:
        raise RuntimeError(f'SZSE turnover not found for {date_text}')
    return float(stock_rows['成交金额'].sum())


def load_market_turnover_data(start, end):
    """Load aggregated two-market turnover as a price-like OHLCV frame."""
    start, end = resolve_date_range(start, end)
    os.makedirs(_CACHE_DIR, exist_ok=True)

    cache_path = os.path.join(_CACHE_DIR, f'market_turnover_{start}_{end}.csv')
    cached_df = _read_cached_frame(cache_path, STANDARD_COLUMNS)
    if cached_df is not None:
        return cached_df

    rows = []
    for current in pd.date_range(pd.to_datetime(start), pd.to_datetime(end), freq='B'):
        date_text = current.strftime('%Y%m%d')
        total_turnover = float(_fetch_sse_turnover(date_text)) + float(_fetch_szse_turnover(date_text))
        rows.append(
            {
                'date': current,
                'open': total_turnover,
                'high': total_turnover,
                'low': total_turnover,
                'close': total_turnover,
                'volume': 0.0,
            }
        )

    df = pd.DataFrame(rows, columns=STANDARD_COLUMNS)
    df.to_csv(cache_path, index=False)
    return df


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
    start, end = resolve_date_range(start, end)
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

    stock_name = _get_stock_name(symbol)
    cache_path = os.path.join(_CACHE_DIR, f'{symbol}_{stock_name}_{start}_{end}.csv')
    df.to_csv(cache_path, index=False)

    df['date'] = pd.to_datetime(df['date'])
    return df


def load_data(symbol, start=None, end=None, include_index=False):
    """
    加载股票数据，可选加载上证综合指数。

    Args:
        symbol:        股票代码，如 '000001'
        start:         开始日期，如 '20200101'，默认最近 3 年
        end:           结束日期，如 '20231231'，默认今天
        include_index: 是否加载上证综合指数，默认 False

    Returns:
        如果 include_index=False，返回股票 DataFrame。
        如果 include_index=True，返回 (stock_df, index_df) 元组。
        指数加载失败时 index_df 为 None。

    Raises:
        Exception: 股票数据加载失败时抛出。
    """
    stock_df = load_market_data(symbol, start, end)

    if not include_index:
        return stock_df

    try:
        index_df = load_shanghai_composite(start, end)
    except Exception as e:
        print(f'上证指数加载失败，将继续使用股票数据: {e}')
        index_df = None

    return stock_df, index_df
