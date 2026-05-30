# market/market_analyzer.py
import hashlib
import json
import os
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'data')


@dataclass
class MarketConfig:
    # ── trend ──
    trend_weight: float = 0.50
    trend_ma_fast: int = 20
    trend_ma_slow: int = 60
    trend_direction_lookback: int = 5
    trend_flat_threshold: float = 0.003

    # ── sentiment ──
    sentiment_weight: float = 0.30
    sentiment_lookback_years: int = 3
    sentiment_short_term_window: int = 20

    # ── volume ──
    volume_weight: float = 0.20
    volume_lookback_years: int = 3
    volume_trapezoid_low: float = 0.20
    volume_trapezoid_rise: float = 0.40
    volume_trapezoid_peak: float = 0.80
    volume_trapezoid_fall: float = 0.90
    volume_trapezoid_low_score: float = 0.2
    volume_trapezoid_high_score: float = 0.2

    @property
    def max_lookback_years(self) -> int:
        return max(self.sentiment_lookback_years, self.volume_lookback_years)

    def hash(self) -> str:
        """SHA256 前 8 位, 用于缓存文件名."""
        data = json.dumps({
            'tw': self.trend_weight,
            'tmaf': self.trend_ma_fast,
            'tmas': self.trend_ma_slow,
            'tdl': self.trend_direction_lookback,
            'tft': self.trend_flat_threshold,
            'sw': self.sentiment_weight,
            'sly': self.sentiment_lookback_years,
            'sstw': self.sentiment_short_term_window,
            'vw': self.volume_weight,
            'vly': self.volume_lookback_years,
            'vtl': self.volume_trapezoid_low,
            'vtr': self.volume_trapezoid_rise,
            'vtp': self.volume_trapezoid_peak,
            'vtf': self.volume_trapezoid_fall,
            'vtls': self.volume_trapezoid_low_score,
            'vths': self.volume_trapezoid_high_score,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:8]


def _shift_years(date_val, years):
    """按年份平移日期, 处理 2 月 29 日。"""
    try:
        return date_val.replace(year=date_val.year + years)
    except ValueError:
        return date_val.replace(year=date_val.year + years, day=28)


def _fetch_index_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    通过 AkShare 获取指数日线, 带降级。

    Args:
        symbol: 'sh000001' 或 'sz399001'
        start:  YYYYMMDD
        end:    YYYYMMDD

    Returns:
        DataFrame with columns date, open, close, high, low, volume, amount
        date 列为 datetime64。

    Raises:
        RuntimeError: 所有数据源均失败。
    """
    import akshare as ak

    last_err = None

    # 主源: 东方财富
    for attempt in range(1, 4):
        try:
            df = ak.stock_zh_index_daily_em(
                symbol=symbol, start_date=start, end_date=end
            )
            df['date'] = pd.to_datetime(df['date'])
            return df[['date', 'open', 'close', 'high', 'low', 'volume', 'amount']].copy()
        except Exception as e:
            last_err = e
            if attempt < 3:
                time.sleep(2)

    # 备用: 腾讯
    for attempt in range(1, 3):
        try:
            df = ak.stock_zh_index_daily_tx(
                symbol=symbol, start_date=start, end_date=end
            )
            df['date'] = pd.to_datetime(df['date'])
            return df[['date', 'open', 'close', 'high', 'low', 'volume', 'amount']].copy()
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(1)

    raise RuntimeError(f'无法获取 {symbol} 的指数数据') from last_err


def _cache_path(start: str, end: str, config: MarketConfig) -> str:
    """缓存文件完整路径。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    fname = f'market_score_{start}_{end}_{config.hash()}.csv'
    return os.path.join(DATA_DIR, fname)


def _read_cache(start: str, end: str, config: MarketConfig) -> pd.DataFrame | None:
    """读取缓存，校验列结构。不一致返回 None。"""
    path = _cache_path(start, end, config)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        expected_cols = ['date', 'trend_score', 'sentiment_score', 'volume_score', 'total_score']
        if df.columns.tolist() != expected_cols:
            return None
        return df
    except Exception:
        return None


def _write_cache(df: pd.DataFrame, start: str, end: str, config: MarketConfig):
    """写入缓存, date 列存为 YYYYMMDD 字符串。"""
    path = _cache_path(start, end, config)
    out = df.copy()
    out['date'] = out['date'].dt.strftime('%Y%m%d')
    out.to_csv(path, index=False)


def _forward_fill(df: pd.DataFrame, start_dt, end_dt) -> pd.DataFrame:
    """
    按交易日历前向填充。

    Args:
        df: 含 date(datetime64) 和评分列
        start_dt: 回测起始 datetime
        end_dt:   回测结束 datetime

    Returns:
        从 start_dt 到 end_dt 的完整 DataFrame,
        缺失日向前填充 (max gap 5), 超窗口填 0.5。
    """
    df = df.set_index('date').sort_index()
    # 生成完整交易日历 (工作日)
    full_idx = pd.date_range(start_dt, end_dt, freq='B')
    df = df.reindex(full_idx)

    # 前向填充, limit=5
    score_cols = ['trend_score', 'sentiment_score', 'volume_score', 'total_score']
    df[score_cols] = df[score_cols].ffill(limit=5)

    # 仍未填充的 → 0.5
    df[score_cols] = df[score_cols].fillna(0.5)

    df.index.name = 'date'
    return df.reset_index()


def get_market_score(
    start: str,
    end: str,
    config: MarketConfig = None,
) -> pd.DataFrame:
    """
    获取市场评分 DataFrame。

    实际拉取区间为 start - max_lookback_years 到 end,
    计算完成后裁剪输出 start~end。

    Args:
        start:  回测起始, YYYYMMDD
        end:    回测结束, YYYYMMDD
        config: 参数配置, None 用默认值

    Returns:
        date | trend_score | sentiment_score | volume_score | total_score
        已前向填充, date 为 datetime64 列。
    """
    if config is None:
        config = MarketConfig()

    start_dt = pd.to_datetime(start, format='%Y%m%d')
    end_dt = pd.to_datetime(end, format='%Y%m%d')
    fetch_start = _shift_years(start_dt, -config.max_lookback_years)
    fetch_start_str = fetch_start.strftime('%Y%m%d')

    # 1. 读缓存
    cached = _read_cache(start, end, config)
    if cached is not None:
        print(f'从缓存读取市场评分: {os.path.basename(_cache_path(start, end, config))}')
        cached['date'] = pd.to_datetime(cached['date'], format='%Y%m%d')
        return cached

    # 2. 拉取数据
    from market.indicators import calc_trend_score, calc_sentiment_score, calc_volume_score

    print(f'正在拉取市场数据 ({fetch_start_str} ~ {end})...')

    df_sh = _fetch_index_data('sh000001', fetch_start_str, end)
    df_sz = _fetch_index_data('sz399001', fetch_start_str, end)

    # 对齐两市日期
    common_idx = df_sh.set_index('date').index.intersection(
        df_sz.set_index('date').index
    )
    df_sh = df_sh.set_index('date').loc[common_idx].reset_index()
    df_sz = df_sz.set_index('date').loc[common_idx].reset_index()

    # 3. 计算子分
    trend = calc_trend_score(df_sh, config)
    sentiment = calc_sentiment_score(df_sh, config)
    volume = calc_volume_score(df_sh, df_sz, config)

    total = (
        trend * config.trend_weight
        + sentiment * config.sentiment_weight
        + volume * config.volume_weight
    )

    result = pd.DataFrame({
        'date': df_sh['date'],
        'trend_score': trend.values,
        'sentiment_score': sentiment.values,
        'volume_score': volume.values,
        'total_score': total.values.clip(0.0, 1.0),
    })

    # 4. 裁剪 + 前向填充
    result = result[(result['date'] >= start_dt) & (result['date'] <= end_dt)]
    result = result.copy()
    result = _forward_fill(result, start_dt, end_dt)

    # 5. 写缓存
    _write_cache(result, start, end, config)

    return result
