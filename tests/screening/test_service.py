"""End-to-end test for screening.service.run_screening.

Uses a stub DataHub that responds to get_dataset() with synthetic frames.
Asserts the funnel layers behave correctly and that no future data leaks in.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from datahub.models import DatasetRequest
from screening.config import ScreenerFilterConfig, ScreenerRequest, ScreenerScoreConfig
from screening.service import run_screening


def _uptrend(code: str, n: int = 120, amount: float = 2e8) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("20240101", periods=n),
        "open": [10.0 + i * 0.1 for i in range(n)],
        "high": [10.0 + i * 0.1 + 0.5 for i in range(n)],
        "low": [10.0 + i * 0.1 - 0.5 for i in range(n)],
        "close": [10.0 + i * 0.1 for i in range(n)],
        "volume": [1_000_000] * n,
        "amount": [amount] * n,
    })


def _downtrend(code: str, n: int = 120) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("20240101", periods=n),
        "open": [20.0 - i * 0.1 for i in range(n)],
        "high": [20.0 - i * 0.1 + 0.2 for i in range(n)],
        "low": [20.0 - i * 0.1 - 0.2 for i in range(n)],
        "close": [20.0 - i * 0.1 for i in range(n)],
        "volume": [1_000_000] * n,
        "amount": [2e8] * n,
    })


class StubHub:
    """Minimal DataHub replacement for service tests."""

    def __init__(self, universe=("600519", "000001"), profile_names=None):
        self.universe = list(universe)
        self.profile_names = profile_names or {c: c for c in universe}
        # capture every (dataset_type, symbol, start, end) tuple requested
        self.calls = []

    def get_dataset(self, request: DatasetRequest):
        self.calls.append(
            (request.dataset_type, request.symbol, request.start, request.end)
        )

        # Universe / constituents
        if request.dataset_type == "index_constituents":
            df = pd.DataFrame({
                "date": [pd.to_datetime(request.start)] * len(self.universe),
                "code": self.universe,
                "weight": [1.0] * len(self.universe),
            })
            return SimpleNamespace(frame=df, cache_hit=True)

        if request.dataset_type == "stock_profile":
            df = pd.DataFrame({
                "date": [pd.to_datetime(request.start)] * len(self.profile_names),
                "code": list(self.profile_names.keys()),
                "name": list(self.profile_names.values()),
                "is_st": [n.startswith(("ST", "*ST")) for n in self.profile_names.values()],
            })
            return SimpleNamespace(frame=df, cache_hit=True)

        if request.dataset_type == "stock_daily":
            code = request.symbol
            if code in {"600519", "000002"}:
                return SimpleNamespace(frame=_uptrend(code), cache_hit=False)
            if code == "000001":
                return SimpleNamespace(frame=_downtrend(code), cache_hit=False)
            # *ST stock — high amount so it would pass numerical filters, fail on name
            if code.startswith("*ST") or code.startswith("ST"):
                return SimpleNamespace(frame=_uptrend(code, amount=5e9), cache_hit=False)
            # default: pass numerical filters (used by top_n / universe-scale tests)
            return SimpleNamespace(frame=_uptrend(code), cache_hit=False)

        if request.dataset_type == "index_daily":
            # benchmark index going down → 600519 (uptrend) will outperform
            return SimpleNamespace(frame=_downtrend("idx"), cache_hit=False)

        raise ValueError(f"unmocked dataset_type {request.dataset_type}")


def test_screening_happy_path_produces_ranked_candidates():
    hub = StubHub(universe=("600519", "000002"), profile_names={
        "600519": "贵州茅台", "000002": "万科A",
    })
    req = ScreenerRequest(
        date="20260628",
        universe_mode="predefined",
        universe_symbol="000300",
        market_gate_mode="off",
    )
    result = run_screening(hub, req)

    assert result.market_gate_passed
    assert result.universe == "000300"
    assert result.total_in_universe == 2
    # Both stocks: 600519 (up) and 000002 (up) both pass trend; benchmark is down
    assert result.total_passed_filters == 2
    assert len(result.candidates) == 2
    # Rank assigned
    assert [c.rank for c in result.candidates] == [1, 2]
    # Ordered by total_score desc
    scores = [c.total_score for c in result.candidates]
    assert scores == sorted(scores, reverse=True)


def test_screening_excludes_st_stocks():
    hub = StubHub(universe=("600519", "*ST测试"), profile_names={
        "600519": "贵州茅台", "*ST测试": "*ST测试",
    })
    req = ScreenerRequest(
        date="20260628",
        universe_mode="predefined",
        market_gate_mode="off",
    )
    result = run_screening(hub, req)
    assert result.total_passed_filters == 1
    assert result.candidates[0].code == "600519"
    # The ST stock never made it past filter; not in candidates
    assert all(c.code != "*ST测试" for c in result.candidates)


def test_screening_respects_top_n():
    codes = [f"{i:06d}" for i in range(10, 20)]
    hub = StubHub(universe=codes, profile_names={c: c for c in codes})
    req = ScreenerRequest(
        date="20260628",
        universe_mode="predefined",
        top_n=3,
        market_gate_mode="off",
    )
    result = run_screening(hub, req)
    assert len(result.candidates) == 3
    assert result.candidates[-1].rank == 3


def test_screening_no_future_leak_in_stock_window():
    """All stock_daily requests must end <= screening_date."""
    hub = StubHub()
    req = ScreenerRequest(date="20260628", market_gate_mode="off")
    run_screening(hub, req)
    for dt, sym, start, end in hub.calls:
        if dt == "stock_daily":
            assert int(end) <= 20260628, f"future leak: {dt} {sym} end={end}"
            # And start should be in the past
            assert int(start) < int(end)


def test_screening_no_future_leak_in_index_window():
    hub = StubHub()
    req = ScreenerRequest(date="20260628", market_gate_mode="off")
    run_screening(hub, req)
    for dt, sym, start, end in hub.calls:
        if dt == "index_daily":
            assert int(end) <= 20260628


def test_screening_artifact_to_dict_has_required_keys():
    hub = StubHub()
    req = ScreenerRequest(date="20260628", market_gate_mode="off", top_n=5)
    result = run_screening(hub, req)
    payload = result.to_dict()
    assert payload["date"] == "20260628"
    assert "market_score" in payload
    assert "candidates" in payload
    assert payload["top_n"] == 5
    if payload["candidates"]:
        c0 = payload["candidates"][0]
        assert {"code", "name", "scores", "total_score", "rank", "reason"}.issubset(c0.keys())
        assert "relative_strength" in c0["scores"]


def test_screening_market_gate_hard_low_market_returns_empty():
    """If market score below threshold, gate fails → empty candidates.

    Force this by patching get_market_score at module level.
    """
    import screening.service as svc
    from screening.config import MarketScoreSnapshot

    class FakeRow:
        def __getitem__(self, k):
            return {
                "total_score": 0.1,
                "trend_score": 0.1,
                "sentiment_score": 0.1,
                "volume_score": 0.1,
            }[k]

    class FakeMarketDF:
        def __init__(self):
            self._row = FakeRow()
        def __getitem__(self, k):
            if k == "total_score":
                return pd.Series([0.1])
            return pd.Series([0.1])
        @property
        def iloc(self):
            return [self._row]

    # Simpler: monkeypatch _gate_market_score to force hard-fail
    orig_gate = svc._gate_market_score
    svc._gate_market_score = lambda req: (MarketScoreSnapshot(0.1, 0.1, 0.1, 0.1), False)

    try:
        hub = StubHub()
        req = ScreenerRequest(date="20260628", market_gate_mode="hard")
        result = run_screening(hub, req)
        assert not result.market_gate_passed
        assert result.candidates == []
    finally:
        svc._gate_market_score = orig_gate