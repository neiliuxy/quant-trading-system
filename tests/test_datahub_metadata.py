import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.db import init_db
from datahub.metadata import (
    create_cache_record,
    create_refresh_record,
    get_refresh_record,
    list_cache_records,
    mark_refresh_completed,
    mark_refresh_failed,
)


def test_init_db_creates_datahub_tables_and_busy_timeout(tmp_path):
    conn = init_db(str(tmp_path / "quantx.sqlite"))

    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert "datahub_cache" in tables
    assert "datahub_refreshes" in tables
    assert busy_timeout >= 5000


def test_cache_and_refresh_metadata_roundtrip(tmp_path):
    conn = init_db(str(tmp_path / "quantx.sqlite"))

    cache = create_cache_record(
        conn,
        dataset_type="stock_daily",
        symbol="000001",
        frequency="daily",
        start_date="20240101",
        end_date="20240131",
        file_path="/tmp/000001.csv",
        row_count=22,
        schema_version="ohlcv-v1",
        source_name="fixture",
        expires_at=None,
    )
    refresh = create_refresh_record(
        conn,
        request_key="stock_daily:000001:daily:20240101:20240131:false",
        dataset_type="stock_daily",
        symbol="000001",
        frequency="daily",
        start_date="20240101",
        end_date="20240131",
        force_refresh=False,
        status="queued",
    )
    mark_refresh_completed(
        conn,
        refresh["id"],
        cache_hit=False,
        output_cache_path="/tmp/000001.csv",
    )

    rows = list_cache_records(conn, dataset_type="stock_daily", symbol="000001")
    saved_refresh = get_refresh_record(conn, refresh["id"])

    assert rows[0]["id"] == cache["id"]
    assert saved_refresh["status"] == "completed"
    assert saved_refresh["cache_hit"] == 0


def test_mark_refresh_failed_records_error(tmp_path):
    conn = init_db(str(tmp_path / "quantx.sqlite"))
    refresh = create_refresh_record(
        conn,
        request_key="index_daily:sh000001:daily:20240101:20240131:false",
        dataset_type="index_daily",
        symbol="sh000001",
        frequency="daily",
        start_date="20240101",
        end_date="20240131",
        force_refresh=False,
        status="running",
    )

    mark_refresh_failed(
        conn,
        refresh["id"],
        error_type="source_unavailable",
        error_message="fixture failure",
    )

    saved = get_refresh_record(conn, refresh["id"])
    assert saved["status"] == "failed"
    assert saved["error_type"] == "source_unavailable"
    assert saved["error_message"] == "fixture failure"
