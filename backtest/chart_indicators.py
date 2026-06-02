"""K 线图技术指标纯函数（参考实现）。

本模块是「数学规约」，生产环境用 web/src/indicators.ts 的 TypeScript 端口。
公式必须保持一致 —— 改这里要同步改 TS 文件。
"""

from __future__ import annotations

from typing import Sequence


def calc_ma(closes: Sequence[float], period: int) -> list[float | None]:
    """简单移动平均。不足 period 时返回 None。"""
    if period <= 0:
        raise ValueError(f'period must be positive, got {period}')
    if not closes:
        return []
    result: list[float | None] = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            s = sum(closes[i - period + 1 : i + 1])
            result.append(s / period)
    return result


def _ema(values: Sequence[float], period: int) -> list[float | None]:
    """EMA。前 period-1 个返回 None，第 period 个用 SMA 作为种子。"""
    if period <= 0:
        raise ValueError(f'period must be positive, got {period}')
    if not values:
        return []
    k = 2.0 / (period + 1)
    result: list[float | None] = []
    prev_sma: float | None = None
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
            continue
        if prev_sma is None:
            s = sum(values[i - period + 1 : i + 1])
            prev_sma = s / period
        else:
            prev_sma = values[i] * k + prev_sma * (1 - k)
        result.append(prev_sma)
    return result


def calc_boll(
    closes: Sequence[float], period: int = 20, num_std: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """布林带：返回 (上轨, 中轨, 下轨)。中轨=MA。"""
    if period <= 0:
        raise ValueError(f'period must be positive, got {period}')
    if not closes:
        return [], [], []
    mid = calc_ma(closes, period)
    upper: list[float | None] = []
    lower: list[float | None] = []
    for i in range(len(closes)):
        if i < period - 1 or mid[i] is None:
            upper.append(None)
            lower.append(None)
            continue
        window = closes[i - period + 1 : i + 1]
        mean = mid[i]
        var = sum((x - mean) ** 2 for x in window) / period
        std = var ** 0.5
        upper.append(mean + num_std * std)
        lower.append(mean - num_std * std)
    return upper, mid, lower


def calc_macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """MACD：DIF=EMA12-EMA26, DEA=DIF的9日EMA, MACD柱=(DIF-DEA)*2。"""
    if not closes:
        return [], [], []
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif: list[float | None] = [
        (ef - es) if ef is not None and es is not None else None
        for ef, es in zip(ema_fast, ema_slow)
    ]
    # DEA 是 DIF 的 EMA，但只在 DIF 有值时计算（无值的位置用 0 占位让 EMA 走，但最终输出 null）
    dif_for_ema = [d if d is not None else 0.0 for d in dif]
    dea_raw = _ema(dif_for_ema, signal)
    dea: list[float | None] = [
        dea_raw[i] if dif[i] is not None and i >= slow - 1 + signal - 1 else None
        for i in range(len(closes))
    ]
    # MACD 柱比 DEA 晚一格 —— DEA 在 slow-1+signal-1 是 SMA 种子，
    # 真正的 EMA 序列从 slow-1+signal 开始；MACD 因此从该点之后才有意义。
    macd: list[float | None] = [
        (d - e) * 2
        if d is not None and e is not None and i >= slow - 1 + signal
        else None
        for i, (d, e) in enumerate(zip(dif, dea))
    ]
    return dif, dea, macd


def calc_kdj(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    n: int = 9,
    k_period: int = 3,
    d_period: int = 3,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """KDJ。默认 K/D 周期=3（即 K_t = 2/3 * K_{t-1} + 1/3 * RSV_t）。"""
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError('highs, lows, closes must have equal length')
    if not closes:
        return [], [], []
    rsv: list[float | None] = []
    for i in range(len(closes)):
        if i < n - 1:
            rsv.append(None)
            continue
        hh = max(highs[i - n + 1 : i + 1])
        ll = min(lows[i - n + 1 : i + 1])
        rng = hh - ll
        rsv.append((closes[i] - ll) / rng * 100 if rng != 0 else 50.0)
    k_alpha = 1.0 / k_period
    d_alpha = 1.0 / d_period
    k: list[float | None] = []
    d: list[float | None] = []
    prev_k = 50.0
    prev_d = 50.0
    for i in range(len(closes)):
        if rsv[i] is None:
            k.append(None)
            d.append(None)
            continue
        prev_k = prev_k * (1 - k_alpha) + rsv[i] * k_alpha
        prev_d = prev_d * (1 - d_alpha) + prev_k * d_alpha
        k.append(prev_k)
        d.append(prev_d)
    j: list[float | None] = [
        (3 * kk - 2 * dd) if kk is not None and dd is not None else None
        for kk, dd in zip(k, d)
    ]
    return k, d, j
