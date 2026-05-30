# market/indicators.py
import numpy as np
import pandas as pd


def _rolling_percentile(series: pd.Series, lookback_years: int) -> pd.Series:
    """计算每个点在过去 lookback_years 窗口内的分位 (0.0~1.0)."""
    window = int(lookback_years * 252)
    result = pd.Series(np.nan, index=series.index)
    for i in range(len(series)):
        if i < 1:
            result.iloc[i] = 0.5
            continue
        start = max(0, i - window + 1)
        window_data = series.iloc[start:i + 1].dropna()
        if len(window_data) == 0:
            result.iloc[i] = 0.5
            continue
        less = (window_data < series.iloc[i]).sum()
        equal = (window_data == series.iloc[i]).sum()
        result.iloc[i] = (less + 0.5 * equal) / len(window_data)
    return result.fillna(0.5).clip(0.0, 1.0)


def calc_trend_score(df_index: pd.DataFrame, config) -> pd.Series:
    """
    A 维度 — 上证趋势评分 (0 / 0.25 / 0.5 / 0.75 / 1.0).

    df_index 需含 close 列, index 为连续交易日。
    """
    close = df_index['close']
    ma_fast = close.rolling(config.trend_ma_fast).mean()
    ma_slow = close.rolling(config.trend_ma_slow).mean()
    ma_slow_prev = ma_slow.shift(config.trend_direction_lookback)

    ma60_change = (ma_slow - ma_slow_prev) / ma_slow_prev.abs()
    ma60_up = ma60_change > config.trend_flat_threshold
    ma60_down = ma60_change < -config.trend_flat_threshold

    scores = pd.Series(0.5, index=df_index.index)

    # 多头: MA60↑ + MA20>MA60 + price>MA20
    bull = ma60_up & (ma_fast > ma_slow) & (close > ma_fast)
    scores[bull] = 1.00

    # 偏多: MA60↑ + MA20>MA60, 但 price <= MA20
    mild_bull = ma60_up & (ma_fast > ma_slow) & ~bull
    scores[mild_bull] = 0.75

    # 偏空: MA60↓ + MA20<MA60, 但 price >= MA20
    mild_bear = ma60_down & (ma_fast < ma_slow) & (close >= ma_fast)
    scores[mild_bear] = 0.25

    # 空头: MA60↓ + MA20<MA60 + price<MA20
    bear = ma60_down & (ma_fast < ma_slow) & (close < ma_fast)
    scores[bear] = 0.00

    return scores.fillna(0.5).clip(0.0, 1.0)


def calc_sentiment_score(df_index: pd.DataFrame, config) -> pd.Series:
    """
    B 维度 — 情绪评分 (0~1)。

    两子指标等权: (1) 日内强度 (2) 短期涨跌惯性
    均取滚动分位后等权合成。
    """
    close = df_index['close']
    open_ = df_index['open']
    high = df_index['high']
    low = df_index['low']

    # 日内强度: (close - open) / (high - low)
    price_range = high - low
    price_range = price_range.replace(0, np.nan)
    intraday = ((close - open_) / price_range).fillna(0.5)

    # 短期涨跌惯性: 过去 N 日上涨占比
    up_days = (close > close.shift(1)).astype(float)
    bias = up_days.rolling(config.sentiment_short_term_window).mean()

    intraday_pct = _rolling_percentile(intraday, config.sentiment_lookback_years)
    bias_pct = _rolling_percentile(bias, config.sentiment_lookback_years)

    return ((intraday_pct + bias_pct) / 2.0).clip(0.0, 1.0)


def calc_volume_score(df_sh: pd.DataFrame, df_sz: pd.DataFrame, config) -> pd.Series:
    """
    C 维度 — 量能评分 (0~1)。

    df_sh, df_sz 均需含 amount 列, index 对齐。
    两市成交额合计 → 滚动分位 → 梯形映射。
    """
    total_amount = df_sh['amount'] + df_sz['amount']
    pct = _rolling_percentile(total_amount, config.volume_lookback_years)

    low = config.volume_trapezoid_low
    rise = config.volume_trapezoid_rise
    peak = config.volume_trapezoid_peak
    fall = config.volume_trapezoid_fall

    score = pd.Series(0.5, index=pct.index)

    # 活跃区 40%-80% → 1.0
    score[(pct >= rise) & (pct <= peak)] = 1.0

    # 上升段 20%-40% → 0.5→1.0 线性
    mask = (pct >= low) & (pct < rise)
    score[mask] = 0.5 + 0.5 * (pct[mask] - low) / (rise - low)

    # 过热段 80%-90% → 1.0→0.4 线性
    mask = (pct > peak) & (pct <= fall)
    score[mask] = 1.0 - 0.6 * (pct[mask] - peak) / (fall - peak)

    # 尾部分
    score[pct < low] = config.volume_trapezoid_low_score
    score[pct > fall] = config.volume_trapezoid_high_score

    return score.fillna(0.5).clip(0.0, 1.0)
