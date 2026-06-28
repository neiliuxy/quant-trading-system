"""Screener background executor — mirrors server/wfo_executor.py pattern.

A screener run touches many stocks; we run it on a thread, persist status
to screener_runs, and write the result JSON to data/screener/<id>.json.
"""
import json
import os
import threading

from server.db import DEFAULT_DB_PATH, init_db
from server.jobs import (
    get_screener_run,
    mark_screener_run_completed,
    update_screener_run_status,
)

DEFAULT_ARTIFACT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'screener',
)


def _build_hub_for_worker(db_path: str):
    """Per-thread DataHub instance (sqlite connections are not shared across threads)."""
    from datahub.service import DataHub
    from datahub.cache import CacheStore

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    conn = init_db(db_path)
    return DataHub(root_dir=project_root, conn=conn, cache=CacheStore(project_root))


def execute_screener_once(
    conn, run_id: int, db_path: str = DEFAULT_DB_PATH,
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
) -> None:
    row = get_screener_run(conn, run_id)
    if row is None:
        return
    os.makedirs(artifact_dir, exist_ok=True)
    update_screener_run_status(conn, run_id, 'running')

    try:
        from screening.config import ScreenerFilterConfig, ScreenerRequest, ScreenerScoreConfig
        from screening.service import run_screening

        config = json.loads(row['config_json'])
        filter_cfg = ScreenerFilterConfig(**config.get('filter_config', {}))
        score_cfg = ScreenerScoreConfig(**config.get('score_config', {}))
        request = ScreenerRequest(
            date=config['date'],
            universe_mode=config.get('universe_mode', 'predefined'),
            universe_symbol=config.get('universe_symbol'),
            custom_list=config.get('custom_list'),
            filter_config=filter_cfg,
            score_config=score_cfg,
            top_n=int(config.get('top_n', 30)),
            market_gate_mode=config.get('market_gate_mode', 'hard'),
            market_gate_threshold=float(config.get('market_gate_threshold', 0.4)),
        )
        hub = _build_hub_for_worker(db_path)
        try:
            result = run_screening(hub, request)
        finally:
            try:
                hub.conn.close()
            except Exception:
                pass

        artifact_path = os.path.join(artifact_dir, f'screener_{run_id}.json')
        with open(artifact_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        mark_screener_run_completed(
            conn, run_id, result.total_in_universe, result.total_passed_filters, artifact_path,
        )
    except Exception as exc:
        update_screener_run_status(conn, run_id, 'failed', str(exc))


def submit_screener_background(
    conn, run_id: int, db_path: str = DEFAULT_DB_PATH,
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
) -> threading.Thread:
    thread = threading.Thread(
        target=execute_screener_once,
        args=(conn, run_id, db_path, artifact_dir),
        daemon=True,
    )
    thread.start()
    return thread