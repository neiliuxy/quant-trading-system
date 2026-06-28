"""Screener configuration dataclasses.

Kept as plain dataclasses (not pydantic) to avoid coupling to server layer;
the server pydantic model wraps these for HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScreenerFilterConfig:
    """Thresholds for the 4-layer filter funnel. Disabled flags bypass that filter."""

    min_listing_days: int = 180
    min_avg_turnover: float = 1e8
    turnover_window: int = 20
    min_data_completeness: float = 0.9
    data_window: int = 60

    require_close_gt_ma20: bool = True
    require_ma20_gt_ma60: bool = True
    require_ma60_slope_up: bool = True
    require_outperform_index: bool = True

    benchmark: str = "000300"
    return_window: int = 60
    lookback_days: int = 250  # how much daily history to load per stock


@dataclass
class ScreenerScoreConfig:
    """Weights for the 5-dimension scoring model. Must sum roughly to 1.0."""

    w_relative_strength: float = 0.30
    w_trend_quality: float = 0.25
    w_drawdown: float = 0.15
    w_vol_price: float = 0.15
    w_liquidity: float = 0.15


@dataclass
class ScreenerRequest:
    """Top-level screener input."""

    date: str  # YYYYMMDD
    universe_mode: str = "predefined"  # 'predefined' | 'custom' | 'full_market'
    universe_symbol: str | None = "000300"  # for 'predefined': 000300 / 000905
    custom_list: list[str] | None = None

    filter_config: ScreenerFilterConfig = field(default_factory=ScreenerFilterConfig)
    score_config: ScreenerScoreConfig = field(default_factory=ScreenerScoreConfig)

    top_n: int = 30
    market_gate_mode: str = "hard"  # 'hard' | 'soft' | 'off'
    market_gate_threshold: float = 0.4

    def config_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "universe_mode": self.universe_mode,
            "universe_symbol": self.universe_symbol,
            "custom_list": self.custom_list,
            "filter_config": self.filter_config.__dict__,
            "score_config": self.score_config.__dict__,
            "top_n": self.top_n,
            "market_gate_mode": self.market_gate_mode,
            "market_gate_threshold": self.market_gate_threshold,
        }


@dataclass
class CandidateScore:
    relative_strength: float
    trend_quality: float
    drawdown: float
    vol_price: float
    liquidity: float


@dataclass
class CandidateResult:
    code: str
    name: str
    universe: str
    filters: dict[str, bool]  # each filter layer's pass/fail
    scores: CandidateScore
    total_score: float
    rank: int
    reason: str


@dataclass
class MarketScoreSnapshot:
    total: float
    trend: float
    sentiment: float
    volume: float


@dataclass
class ScreenerResult:
    date: str
    universe_mode: str
    universe: str
    market_score: MarketScoreSnapshot
    market_gate_passed: bool
    total_in_universe: int
    total_passed_filters: int
    filter_config: dict[str, Any]
    score_config: dict[str, Any]
    top_n: int
    candidates: list[CandidateResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "universe_mode": self.universe_mode,
            "universe": self.universe,
            "market_score": {
                "total": self.market_score.total,
                "trend": self.market_score.trend,
                "sentiment": self.market_score.sentiment,
                "volume": self.market_score.volume,
            },
            "market_gate_passed": self.market_gate_passed,
            "total_in_universe": self.total_in_universe,
            "total_passed_filters": self.total_passed_filters,
            "filter_config": self.filter_config,
            "score_config": self.score_config,
            "top_n": self.top_n,
            "candidates": [
                {
                    "code": c.code,
                    "name": c.name,
                    "universe": c.universe,
                    "filters": c.filters,
                    "scores": c.scores.__dict__,
                    "total_score": c.total_score,
                    "rank": c.rank,
                    "reason": c.reason,
                }
                for c in self.candidates
            ],
        }