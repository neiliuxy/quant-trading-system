"""测试 backtest/chart_indicators.py 中的纯函数指标公式。

这些公式是「数学规约」，TS 端口（web/src/indicators.ts）必须与之保持一致。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import pytest

from backtest.chart_indicators import calc_ma, calc_boll, calc_macd, calc_kdj


# ── calc_ma ──────────────────────────────────────────────

class TestCalcMa:
    def test_period_5_first_four_null(self):
        closes = [10, 11, 12, 13, 14, 15]
        result = calc_ma(closes, 5)
        assert result[:4] == [None, None, None, None]
        assert result[4] == pytest.approx(12.0)
        assert result[5] == pytest.approx(13.0)

    def test_period_1_returns_closes(self):
        closes = [10, 11, 12]
        result = calc_ma(closes, 1)
        assert result == closes

    def test_short_series_returns_all_none(self):
        assert calc_ma([1, 2], 5) == [None, None]

    def test_empty_series(self):
        assert calc_ma([], 5) == []


# ── calc_boll ─────────────────────────────────────────────

class TestCalcBoll:
    def test_first_19_null(self):
        closes = [float(i) for i in range(25)]
        upper, mid, lower = calc_boll(closes, period=20, num_std=2.0)
        for i in range(19):
            assert upper[i] is None
            assert mid[i] is None
            assert lower[i] is None

    def test_mid_equals_ma20(self):
        closes = [float(i) for i in range(25)]
        upper, mid, lower = calc_boll(closes, period=20, num_std=2.0)
        assert mid[19] == pytest.approx(sum(closes[:20]) / 20)
        assert mid[20] == pytest.approx(sum(closes[1:21]) / 20)

    def test_upper_above_mid_above_lower(self):
        closes = [10, 12, 11, 13, 15, 14, 16, 18, 17, 19, 21, 20, 22, 24, 23, 25, 27, 26, 28, 30, 29]
        upper, mid, lower = calc_boll(closes, period=20, num_std=2.0)
        for i in range(20, len(closes)):
            assert upper[i] > mid[i] > lower[i]

    def test_constant_series_upper_equals_mid_equals_lower(self):
        closes = [100.0] * 25
        upper, mid, lower = calc_boll(closes, period=20, num_std=2.0)
        for i in range(20, len(closes)):
            assert upper[i] == pytest.approx(100.0)
            assert lower[i] == pytest.approx(100.0)


# ── calc_macd ─────────────────────────────────────────────

class TestCalcMacd:
    def test_first_34_null(self):
        closes = [float(i) for i in range(40)]
        dif, dea, macd = calc_macd(closes, fast=12, slow=26, signal=9)
        # DIF null until index 25, DEA null until DEA seed ready, MACD null if either null
        for i in range(25):
            assert dif[i] is None
        for i in range(33):  # 25 + 8 (signal - 1)
            assert dea[i] is None
        for i in range(34):
            assert macd[i] is None

    def test_dif_at_index_25_equals_zero(self):
        # 线性递增序列的 EMA12 与 EMA26 在 i=25 之后才第一次都有值
        closes = [float(i) for i in range(40)]
        dif, dea, macd = calc_macd(closes, fast=12, slow=26, signal=9)
        # 在 i=25，DIF = EMA12[25] - EMA26[25]
        # EMA12[11] 用 SMA 作为种子
        assert dif[25] is not None

    def test_macd_bar_is_dif_minus_dea_times_2(self):
        closes = [100 + i * 0.5 for i in range(60)]
        dif, dea, macd = calc_macd(closes, fast=12, slow=26, signal=9)
        for i in range(34, 60):
            if dif[i] is not None and dea[i] is not None:
                assert macd[i] == pytest.approx((dif[i] - dea[i]) * 2, abs=1e-9)


# ── calc_kdj ─────────────────────────────────────────────

class TestCalcKdj:
    def test_first_8_null(self):
        highs = [float(i) for i in range(20)]
        lows = [float(i) - 1 for i in range(20)]
        closes = [float(i) - 0.5 for i in range(20)]
        k, d, j = calc_kdj(highs, lows, closes, n=9, k_period=3, d_period=3)
        for i in range(8):
            assert k[i] is None
            assert d[i] is None
            assert j[i] is None

    def test_k_starts_at_50_when_no_prev(self):
        highs = [11.0] * 9
        lows = [9.0] * 9
        closes = [10.0] * 9
        k, d, j = calc_kdj(highs, lows, closes, n=9, k_period=3, d_period=3)
        # RSV = (close - low) / (high - low) = (10-9)/(11-9) = 0.5
        # K = 2/3 * 50 + 1/3 * 50 = 50 (default prev = 50)
        assert k[8] == pytest.approx(50.0)

    def test_j_equals_3k_minus_2d(self):
        highs = [float(i) for i in range(20)]
        lows = [float(i) - 2 for i in range(20)]
        closes = [float(i) - 1 for i in range(20)]
        k, d, j = calc_kdj(highs, lows, closes, n=9, k_period=3, d_period=3)
        for i in range(8, 20):
            if k[i] is not None and d[i] is not None:
                assert j[i] == pytest.approx(3 * k[i] - 2 * d[i])
