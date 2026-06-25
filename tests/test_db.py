"""Database schema tests."""
import os
import tempfile

from server.db import init_db


def test_wfo_runs_table_created():
    """init_db 应创建 wfo_runs 表,含全部字段和索引。"""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        db_path = tmp.name
    try:
        conn = init_db(db_path)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='wfo_runs'"
        ).fetchall()
        assert rows, 'wfo_runs 表应被创建'

        cols = conn.execute('PRAGMA table_info(wfo_runs)').fetchall()
        col_names = {c[1] for c in cols}
        expected = {
            'id', 'run_key', 'status', 'symbol', 'start_date', 'end_date',
            'strategy_id', 'config_json', 'artifact_path',
            'current_fold', 'total_folds', 'error',
            'created_at', 'updated_at',
        }
        assert expected <= col_names, f'wfo_runs 缺字段:{expected - col_names}'

        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='wfo_runs'"
        ).fetchall()
        index_names = {r[0] for r in indexes}
        assert 'idx_wfo_runs_run_key' in index_names
    finally:
        os.unlink(db_path)
