"""RSRS (Resistance Support Relative Strength) timing indicator.

Originally proposed by Guangda Securities quantitative research. The right-
side standardised variant (slope / std(residuals)) is what we use here.

Signal rule of thumb:
    RSRS > 0.7  -> bull market, allow long entries
    -0.7 < RSRS < 0.7 -> neutral, optional
    RSRS < -0.7 -> bear market, stay in cash

References:
    https://github.com/hugo2046/QuantsPlaybook (reproduction of
    the original securities-firm research note).
"""

from __future__ import annotations

import backtrader as bt


class RsrsIndicator(bt.Indicator):
    """Right-side standardised RSRS.

    For each bar, regress the past N daily highs on the past N daily lows:
        high_i = alpha + beta * low_i + epsilon_i
    and report beta / std(epsilon) as the indicator value.

    Lines:
        rsrs - the standardised slope.
    """

    lines = ('rsrs',)
    params = (
        ('period', 18),
    )

    def __init__(self):
        self.addminperiod(self.p.period)
        # Source: high regressed on low. Use High and Low directly.
        self._lows = self.data.low(-self.p.period + 1)
        self._highs = self.data.high(-self.p.period + 1)

    def next(self):
        n = self.p.period
        if n < 2:
            self.lines.rsrs[0] = 0.0
            return
        sum_x = 0.0
        sum_y = 0.0
        sum_xx = 0.0
        sum_xy = 0.0
        for i in range(n):
            x = self.data.low[-i]
            y = self.data.high[-i]
            sum_x += x
            sum_y += y
            sum_xx += x * x
            sum_xy += x * y
        denom = n * sum_xx - sum_x * sum_x
        if abs(denom) < 1e-12:
            self.lines.rsrs[0] = 0.0
            return
        beta = (n * sum_xy - sum_x * sum_y) / denom
        # std of residuals (using slope and intercept on the same window)
        alpha = (sum_y - beta * sum_x) / n
        var = 0.0
        for i in range(n):
            pred = alpha + beta * self.data.low[-i]
            r = self.data.high[-i] - pred
            var += r * r
        var /= max(n - 2, 1)
        std = var ** 0.5
        if std < 1e-12:
            self.lines.rsrs[0] = 0.0
            return
        self.lines.rsrs[0] = beta / std
