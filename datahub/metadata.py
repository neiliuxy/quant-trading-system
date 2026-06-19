from __future__ import annotations

from typing import Any


def _row_to_dict(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def create_cache_record(
    conn,
    *,
    dataset_type: str,
    symbol: str | None,
    frequency: str,
    start_date: str,
    end_date: str,
    file_path: str,
    row_count: int,
    schema_version: str,
    source_name: str,
    expires_at: str | None,
) -> dict[str, Any]:
    cur = conn.execute(
        """
        INSERT INTO datahub_cache (
            dataset_type, symbol, frequency, start_date, end_date, file_path,
            row_count, schema_version, source_name, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset_type,
            symbol,
            frequency,
            start_date,
            end_date,
            file_path,
            row_count,
            schema_version,
            source_name,
            expires_at,
        ),
    )
    conn.commit()
    return get_cache_record(conn, cur.lastrowid)


def get_cache_record(conn, cache_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM datahub_cache WHERE id = ?", (cache_id,)).fetchone()
    return _row_to_dict(row)


def list_cache_records(
    conn,
    *,
    dataset_type: str | None = None,
    symbol: str | None = None,
    frequency: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM datahub_cache WHERE 1 = 1"
    params: list[Any] = []
    if dataset_type is not None:
        sql += " AND dataset_type = ?"
        params.append(dataset_type)
    if symbol is not None:
        sql += " AND symbol = ?"
        params.append(symbol)
    if frequency is not None:
        sql += " AND frequency = ?"
        params.append(frequency)
    if start_date is not None:
        sql += " AND end_date >= ?"
        params.append(start_date)
    if end_date is not None:
        sql += " AND start_date <= ?"
        params.append(end_date)
    sql += " ORDER BY refreshed_at DESC, id DESC"
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def create_refresh_record(
    conn,
    *,
    request_key: str,
    dataset_type: str,
    symbol: str | None,
    frequency: str,
    start_date: str,
    end_date: str,
    force_refresh: bool,
    status: str,
) -> dict[str, Any]:
    cur = conn.execute(
        """
        INSERT INTO datahub_refreshes (
            request_key, dataset_type, symbol, frequency, start_date, end_date,
            force_refresh, status, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'running' THEN CURRENT_TIMESTAMP ELSE NULL END)
        """,
        (
            request_key,
            dataset_type,
            symbol,
            frequency,
            start_date,
            end_date,
            int(force_refresh),
            status,
            status,
        ),
    )
    conn.commit()
    return get_refresh_record(conn, cur.lastrowid)


def get_refresh_record(conn, refresh_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM datahub_refreshes WHERE id = ?",
        (refresh_id,),
    ).fetchone()
    return _row_to_dict(row)


def find_running_refresh(conn, request_key: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM datahub_refreshes
        WHERE request_key = ? AND status IN ('queued', 'running')
        ORDER BY id DESC LIMIT 1
        """,
        (request_key,),
    ).fetchone()
    return _row_to_dict(row)


def mark_refresh_running(conn, refresh_id: int) -> None:
    conn.execute(
        """
        UPDATE datahub_refreshes
        SET status = 'running', started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (refresh_id,),
    )
    conn.commit()


def mark_refresh_completed(
    conn,
    refresh_id: int,
    *,
    cache_hit: bool,
    output_cache_path: str | None,
) -> None:
    conn.execute(
        """
        UPDATE datahub_refreshes
        SET status = 'completed', cache_hit = ?, output_cache_path = ?,
            finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (int(cache_hit), output_cache_path, refresh_id),
    )
    conn.commit()


def mark_refresh_failed(
    conn,
    refresh_id: int,
    *,
    error_type: str,
    error_message: str,
) -> None:
    conn.execute(
        """
        UPDATE datahub_refreshes
        SET status = 'failed', error_type = ?, error_message = ?,
            finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (error_type, error_message, refresh_id),
    )
    conn.commit()
