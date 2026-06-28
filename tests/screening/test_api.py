"""End-to-end test for screener API endpoints.

Uses TestClient + temporary DB. The screener run executes in a real thread;
we monkeypatch run_screening to return a synthetic result so the test
doesn't touch the network.
"""
import json
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "screener_test.sqlite")
    from server.api import create_app
    app = create_app(db_path)
    with TestClient(app) as c:
        yield c


def _wait_for_completion(client, run_id: int, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/screener/{run_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"screener run {run_id} did not finish in {timeout}s")


def test_create_screener_returns_id_and_status(client, monkeypatch):
    """Submit a screener job; expect 200 + run id + status transitions."""
    from screening.config import (
        CandidateResult, CandidateScore, MarketScoreSnapshot, ScreenerResult,
    )
    import screening.service as svc

    def fake_run(hub, request):
        return ScreenerResult(
            date=request.date,
            universe_mode=request.universe_mode,
            universe=request.universe_symbol or "custom",
            market_score=MarketScoreSnapshot(0.7, 0.7, 0.7, 0.7),
            market_gate_passed=True,
            total_in_universe=300,
            total_passed_filters=42,
            filter_config=request.filter_config.__dict__,
            score_config=request.score_config.__dict__,
            top_n=request.top_n,
            candidates=[
                CandidateResult(
                    code="600519", name="贵州茅台", universe="000300",
                    filters={"not_st": True}, scores=CandidateScore(0.9, 0.8, 0.7, 0.6, 0.9),
                    total_score=0.8, rank=1, reason="跑赢基准 / 均线多头",
                ),
            ],
        )

    monkeypatch.setattr(svc, "run_screening", fake_run)

    payload = {
        "date": "20260628",
        "universe_mode": "predefined",
        "universe_symbol": "000300",
        "top_n": 30,
    }
    resp = client.post("/api/screener", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    run_id = body["id"]
    assert body["status"] in ("queued", "running", "completed")
    assert body["screening_date"] == "20260628"

    final = _wait_for_completion(client, run_id)
    assert final["status"] == "completed"
    assert final["total_in_universe"] == 300
    assert final["total_passed_filters"] == 42


def test_screener_result_returns_candidate_payload(client, monkeypatch):
    from screening.config import (
        CandidateResult, CandidateScore, MarketScoreSnapshot, ScreenerResult,
    )
    import screening.service as svc

    def fake_run(hub, request):
        return ScreenerResult(
            date=request.date,
            universe_mode=request.universe_mode,
            universe="000300",
            market_score=MarketScoreSnapshot(0.7, 0.7, 0.7, 0.7),
            market_gate_passed=True,
            total_in_universe=2,
            total_passed_filters=2,
            filter_config=request.filter_config.__dict__,
            score_config=request.score_config.__dict__,
            top_n=5,
            candidates=[
                CandidateResult(
                    code="600519", name="贵州茅台", universe="000300",
                    filters={"not_st": True, "turnover": True},
                    scores=CandidateScore(0.9, 0.8, 0.7, 0.6, 0.9),
                    total_score=0.81, rank=1, reason="跑赢基准",
                ),
            ],
        )

    monkeypatch.setattr(svc, "run_screening", fake_run)

    resp = client.post("/api/screener", json={"date": "20260628", "universe_symbol": "000300"})
    assert resp.status_code == 200
    run_id = resp.json()["id"]

    final = _wait_for_completion(client, run_id)
    assert final["status"] == "completed"

    r = client.get(f"/api/screener/{run_id}/result")
    assert r.status_code == 200
    payload = r.json()
    assert payload["date"] == "20260628"
    assert len(payload["candidates"]) == 1
    c0 = payload["candidates"][0]
    assert c0["code"] == "600519"
    assert c0["rank"] == 1
    assert c0["total_score"] == 0.81
    assert "relative_strength" in c0["scores"]


def test_screener_404_for_missing_run(client):
    r = client.get("/api/screener/99999")
    assert r.status_code == 404


def test_screener_result_404_until_completed(client, monkeypatch):
    """Result endpoint returns 404 when artifact is not yet written."""
    import screening.service as svc
    block = threading.Event()
    monkeypatch.setattr(svc, "run_screening", lambda hub, req: block.wait(3) or None)

    resp = client.post("/api/screener", json={"date": "20260628"})
    run_id = resp.json()["id"]

    r = client.get(f"/api/screener/{run_id}/result")
    assert r.status_code == 404

    block.set()  # let the worker finish (it'll fail but at least unblock)


def test_create_screener_validates_config(client):
    """Missing required `date` field should 400."""
    resp = client.post("/api/screener", json={"universe_mode": "predefined"})
    assert resp.status_code == 400


def test_failed_run_records_error_message(client, monkeypatch):
    """Worker exception surfaces as status='failed' with error text."""
    import screening.service as svc

    def boom(hub, request):
        raise RuntimeError("intentional test failure")

    monkeypatch.setattr(svc, "run_screening", boom)

    resp = client.post("/api/screener", json={"date": "20260628"})
    run_id = resp.json()["id"]
    final = _wait_for_completion(client, run_id)
    assert final["status"] == "failed"
    assert "intentional test failure" in (final.get("error") or "")


def test_recent_valid_date_returns_index_cache_max(client, monkeypatch):
    """When index_daily cache has rows, endpoint returns the latest date string."""
    import pandas as pd
    from datahub.models import DatasetRequest, DatasetResult

    class FakeHub:
        def get_dataset(self, request: DatasetRequest):
            assert request.dataset_type == "index_daily"
            assert request.symbol == "sh000001"
            frame = pd.DataFrame({
                "date": pd.to_datetime(["20240102", "20240103", "20240628"]),
                "open": [2900.0, 2910.0, 3000.0],
                "close": [2910.0, 2920.0, 3010.0],
            })
            return DatasetResult(request=request, frame=frame, cache_hit=True)

    # Override hub_factory on the FastAPI app instance
    from server.main import create_app  # noqa
    app = client.app
    app.state.hub_factory = lambda: FakeHub()

    r = client.get("/api/screener/recent-valid-date")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "20240628"
    assert body["source"] == "index_cache"


def test_recent_valid_date_falls_back_when_cache_empty(client, monkeypatch):
    """When DataHub raises, endpoint returns today as a fallback."""
    from datahub.models import DataHubError

    class FailingHub:
        def get_dataset(self, request):
            raise DataHubError("empty_data", "no rows")

    app = client.app
    app.state.hub_factory = lambda: FailingHub()

    r = client.get("/api/screener/recent-valid-date")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "today-fallback"
    assert len(body["date"]) == 8  # YYYYMMDD