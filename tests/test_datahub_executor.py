import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datahub.executor import DataHubRefreshExecutor
from datahub.metadata import create_refresh_record, get_refresh_record
from datahub.models import DatasetRequest
from server.db import init_db


def test_refresh_executor_opens_worker_connection(tmp_path):
    db_path = str(tmp_path / "quantx.sqlite")
    conn = init_db(db_path)
    refresh = create_refresh_record(
        conn,
        request_key="stock_daily:000001:daily:20240101:20240131:true",
        dataset_type="stock_daily",
        symbol="000001",
        frequency="daily",
        start_date="20240101",
        end_date="20240131",
        force_refresh=True,
        status="queued",
    )
    seen = {}

    def worker(conn, request, refresh_id):
        seen["same_connection"] = conn is not None
        from datahub.metadata import mark_refresh_completed
        mark_refresh_completed(conn, refresh_id, cache_hit=False, output_cache_path="/tmp/cache.csv")

    executor = DataHubRefreshExecutor(db_path=db_path, worker=worker, max_workers=1)
    executor.submit(DatasetRequest("stock_daily", symbol="000001", start="20240101", end="20240131", force_refresh=True), refresh["id"]).result(timeout=5)

    saved = get_refresh_record(conn, refresh["id"])
    assert seen["same_connection"] is True
    assert saved["status"] == "completed"
