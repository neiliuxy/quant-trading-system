"""6-layer funnel orchestrator. Glues universe/filter/scoring together.

No network calls of its own — all data flows through the DataHub instance
the caller passes in (real or stubbed for tests).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from datahub.models import DatasetRequest, DataHubError

from screening.config import (
    CandidateResult,
    CandidateScore,
    MarketScoreSnapshot,
    ScreenerRequest,
    ScreenerResult,
)
from screening.filters import apply_filters
from screening.indicators import slice_to_date
from screening.scoring_aggregate import aggregate_and_rank
from screening.scoring import compute_total_score, score_stock
from screening.universe import enrich_names, load_universe


def _gate_market_score(request: ScreenerRequest) -> tuple[MarketScoreSnapshot, bool]:
    """Layer 1 — market gate. Returns (snapshot, gate_passed)."""
    if request.market_gate_mode == "off":
        snap = MarketScoreSnapshot(0.5, 0.5, 0.5, 0.5)
        return snap, True
    try:
        from market.market_analyzer import MarketConfig, get_market_score
        df = get_market_score(request.date, request.date, MarketConfig())
        if df is None or df.empty:
            raise RuntimeError(f"market score empty for {request.date}")
        row = df.iloc[-1]
        snap = MarketScoreSnapshot(
            total=float(row["total_score"]),
            trend=float(row["trend_score"]),
            sentiment=float(row["sentiment_score"]),
            volume=float(row["volume_score"]),
        )
    except Exception:
        snap = MarketScoreSnapshot(0.5, 0.5, 0.5, 0.5)
        if request.market_gate_mode == "hard":
            return snap, False
        return snap, True
    if request.market_gate_mode == "hard":
        return snap, snap.total >= request.market_gate_threshold
    return snap, True  # soft: pass through, weight applied downstream


def _lookup_earliest_date(hub, code: str, screening_date: pd.Timestamp) -> pd.Timestamp | None:
    """Estimate listing date from earliest cached bar. Returns None on failure."""
    start = (screening_date - timedelta(days=365 * 20)).strftime("%Y%m%d")
    end = screening_date.strftime("%Y%m%d")
    try:
        df = hub.get_dataset(
            DatasetRequest(dataset_type="stock_daily", symbol=code, start=start, end=end)
        ).frame
    except DataHubError:
        return None
    if df is None or df.empty:
        return None
    earliest = pd.to_datetime(df["date"]).min()
    return earliest


def _load_index_for_screening(hub, benchmark: str, date: str) -> pd.DataFrame | None:
    """Map benchmark code ('000300') to DataHub index_daily symbol ('sh000300')."""
    sym = benchmark
    if sym.startswith("000") and not sym.startswith("sh") and not sym.startswith("sz"):
        sym = "sh" + sym
    start = (pd.to_datetime(date) - timedelta(days=400)).strftime("%Y%m%d")
    end = date
    try:
        df = hub.get_dataset(
            DatasetRequest(dataset_type="index_daily", symbol=sym, start=start, end=end)
        ).frame
    except DataHubError:
        return None
    if df is None or df.empty:
        return None
    return slice_to_date(df, pd.to_datetime(date))


def _load_stock_window(
    hub, code: str, screening_date: pd.Timestamp, lookback_days: int
) -> pd.DataFrame | None:
    """Load per-stock daily bars sliced to <= screening_date."""
    start = (screening_date - timedelta(days=lookback_days)).strftime("%Y%m%d")
    end = screening_date.strftime("%Y%m%d")
    try:
        df = hub.get_dataset(
            DatasetRequest(dataset_type="stock_daily", symbol=code, start=start, end=end)
        ).frame
    except DataHubError:
        return None
    if df is None or df.empty:
        return None
    return slice_to_date(df, screening_date)


def _build_reason(name: str, filters: dict[str, bool], score: CandidateScore) -> str:
    bits = []
    if filters.get("outperform_index"):
        bits.append("跑赢基准")
    if filters.get("ma20_gt_ma60") and filters.get("close_gt_ma20"):
        bits.append("均线多头")
    if filters.get("ma60_slope_up"):
        bits.append("趋势向上")
    if filters.get("turnover"):
        bits.append("流动性达标")
    if score.liquidity > 0.8:
        bits.append("高流动性")
    if score.drawdown > 0.85:
        bits.append("回撤可控")
    return " / ".join(bits) if bits else "通过基础筛选"


def run_screening(hub, request: ScreenerRequest) -> ScreenerResult:
    """Run the 6-layer funnel. `hub` must expose get_dataset()."""
    screening_date = pd.to_datetime(request.date)

    # Layer 1: market gate
    market_snap, gate_passed = _gate_market_score(request)
    if not gate_passed:
        return ScreenerResult(
            date=request.date,
            universe_mode=request.universe_mode,
            universe=request.universe_symbol or "custom",
            market_score=market_snap,
            market_gate_passed=False,
            total_in_universe=0,
            total_passed_filters=0,
            filter_config=request.filter_config.__dict__,
            score_config=request.score_config.__dict__,
            top_n=request.top_n,
            candidates=[],
        )

    # Layer 2: universe
    codes, universe_names, universe_label = load_universe(hub, request)
    if request.universe_mode != "full_market":
        universe_names = enrich_names(hub, codes, request.date)
    if not codes:
        return ScreenerResult(
            date=request.date,
            universe_mode=request.universe_mode,
            universe=universe_label,
            market_score=market_snap,
            market_gate_passed=True,
            total_in_universe=0,
            total_passed_filters=0,
            filter_config=request.filter_config.__dict__,
            score_config=request.score_config.__dict__,
            top_n=request.top_n,
            candidates=[],
        )

    # Layer 2.5: load benchmark index once
    index_df = _load_index_for_screening(
        hub, request.filter_config.benchmark, request.date
    )
    if index_df is None:
        index_df = pd.DataFrame(columns=["date", "close"])

    # Layers 3-5: per stock
    candidates: list[CandidateResult] = []
    total_passed_filters = 0
    for code in codes:
        name = universe_names.get(code, "")
        frame = _load_stock_window(hub, code, screening_date, request.filter_config.lookback_days)
        if frame is None or len(frame) < 60:
            continue

        earliest = _lookup_earliest_date(hub, code, screening_date)
        flags = apply_filters(
            frame, name, earliest, index_df, screening_date, request.filter_config
        )
        if not all(flags.values()):
            continue
        total_passed_filters += 1

        sub = score_stock(
            frame, index_df, request.score_config,
            return_window=request.filter_config.return_window,
            trend_window=request.filter_config.data_window,
            liquidity_window=request.filter_config.turnover_window,
        )
        total = compute_total_score(sub, request.score_config)
        candidates.append(CandidateResult(
            code=code, name=name, universe=universe_label,
            filters=flags, scores=sub, total_score=total, rank=0,
            reason=_build_reason(name, flags, sub),
        ))

    # Layer 6: rank + top_n
    candidates = aggregate_and_rank(candidates, request.top_n)

    return ScreenerResult(
        date=request.date,
        universe_mode=request.universe_mode,
        universe=universe_label,
        market_score=market_snap,
        market_gate_passed=True,
        total_in_universe=len(codes),
        total_passed_filters=total_passed_filters,
        filter_config=request.filter_config.__dict__,
        score_config=request.score_config.__dict__,
        top_n=request.top_n,
        candidates=candidates,
    )