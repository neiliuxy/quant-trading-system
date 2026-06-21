"""风险调整指标 + 基准对比的提取与计算。

入参均为已经 get_analysis() 的普通 dict / list，本模块不碰 backtrader、不碰网络，
纯函数可独立单测。被 backtest/service.py 调用。
"""
from typing import Any


def extract_sharpe(sharpe_analysis: dict) -> float:
    """从 SharpeRatio analyzer 结果取年化夏普；None/缺失 → 0.0。"""
    value = sharpe_analysis.get('sharperatio')
    return float(value) if value is not None else 0.0


def extract_annual_return_pct(returns_analysis: dict) -> float:
    """从 Returns analyzer 取年化收益率（rnorm100，已是百分数）。"""
    return float(returns_analysis.get('rnorm100', 0.0) or 0.0)


def compute_profit_loss_ratio(trade_stats: dict) -> float:
    """盈亏比 = 平均盈利 / 平均亏损绝对值。无亏损交易时返回 0.0。"""
    won_avg = trade_stats.get('won', {}).get('pnl', {}).get('average', 0.0) or 0.0
    lost_avg = trade_stats.get('lost', {}).get('pnl', {}).get('average', 0.0) or 0.0
    if lost_avg == 0:
        return 0.0
    return float(won_avg / abs(lost_avg))


def compute_benchmark_return_pct(index_data: list[dict[str, Any]]) -> float:
    """上证指数买入持有收益%。数据为空或首值为 0 → 0.0。"""
    if not index_data:
        return 0.0
    first_close = index_data[0].get('close', 0.0)
    last_close = index_data[-1].get('close', 0.0)
    if not first_close:
        return 0.0
    return float((last_close / first_close - 1.0) * 100.0)


def compute_excess_return_pct(strategy_return_pct: float, benchmark_return_pct: float) -> float:
    """策略超额收益 = 策略收益 - 基准收益。"""
    return float(strategy_return_pct - benchmark_return_pct)
