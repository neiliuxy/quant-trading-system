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
