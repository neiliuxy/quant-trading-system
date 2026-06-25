"""市场数据加载器。

公共 load_* 函数是 DataHub 的薄包装，委托 datahub.service.DataHub 取数。
date helper（resolve_date_range 等）仍供 backtest 服务层、选股器、脚本与 CLI 复用。
"""

import os
import re
from datetime import date, datetime

import pandas as pd

from datahub.models import DatasetRequest
from datahub.service import DataHub
from server.db import DEFAULT_DB_PATH, init_db

STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume']
INDEX_STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']


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


def _make_datahub() -> DataHub:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return DataHub(root_dir=project_root, conn=init_db(DEFAULT_DB_PATH))


def load_market_data(symbol, start, end):
    """DataHub 包装：加载股票日线数据（保留原签名）。"""
    start, end = resolve_date_range(start, end)
    result = _make_datahub().get_dataset(
        DatasetRequest(
            dataset_type='stock_daily',
            symbol=str(symbol).zfill(6),
            start=start,
            end=end,
        )
    )
    return result.frame


def load_shanghai_composite(start, end):
    """DataHub 包装：加载上证综合指数。获取失败时返回 None 保持向后兼容。"""
    start, end = resolve_date_range(start, end)
    try:
        result = _make_datahub().get_dataset(
            DatasetRequest(
                dataset_type='index_daily',
                symbol='sh000001',
                start=start,
                end=end,
            )
        )
        return result.frame
    except Exception as exc:
        print(f'无法获取上证综合指数的历史数据: {exc}')
        return None


def load_security_etf_data(start, end, symbol='sh512880'):
    """DataHub 包装：加载证券 ETF 数据。"""
    start, end = resolve_date_range(start, end)
    result = _make_datahub().get_dataset(
        DatasetRequest(
            dataset_type='etf_daily',
            symbol=symbol,
            start=start,
            end=end,
        )
    )
    return result.frame


def load_market_turnover_data(start, end):
    """DataHub 包装：加载两市成交额数据。"""
    start, end = resolve_date_range(start, end)
    result = _make_datahub().get_dataset(
        DatasetRequest(
            dataset_type='market_turnover',
            start=start,
            end=end,
        )
    )
    return result.frame


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

    index_df = load_shanghai_composite(start, end)

    return stock_df, index_df


def default_trading_calendar(symbol: str, start: str, end: str) -> list[str]:
    """WFO 引擎 trading_calendar 的默认实现:走 DataHub 取 stock_daily 日期索引。

    返回 [start, end] 区间内按交易日排序的 YYYYMMDD 字符串列表;数据为空返回空列表。
    """
    from datahub.service import DataHub
    from datahub.models import DatasetRequest
    from server.db import init_db, DEFAULT_DB_PATH

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hub = DataHub(root_dir=project_root, conn=init_db(DEFAULT_DB_PATH))
    df = hub.get_dataset(DatasetRequest(
        dataset_type='stock_daily', symbol=symbol, start=start, end=end,
    )).frame
    if df is None or df.empty:
        return []
    return sorted(df['date'].dt.strftime('%Y%m%d').tolist())
