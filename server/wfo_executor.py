"""WFO 后台执行器。照搬 server/executor.py 模式:线程 + artifact 落盘 + DB 状态。"""
import json
import os
import threading

from backtest.data_loader import default_trading_calendar
from backtest.service import run_backtest_service
from backtest.walkforward import WfoConfig, run_walkforward
from server.jobs import (
    get_wfo_run, mark_wfo_run_completed,
    update_wfo_run_progress, update_wfo_run_status,
)

DEFAULT_ARTIFACT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'results',
)


def execute_wfo_once(conn, wfo_id: int, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> None:
    row = get_wfo_run(conn, wfo_id)
    if row is None:
        return
    os.makedirs(artifact_dir, exist_ok=True)
    update_wfo_run_status(conn, wfo_id, 'running')
    config = WfoConfig(**json.loads(row['config_json']))

    def on_fold_complete(current: int, total: int) -> None:
        update_wfo_run_progress(conn, wfo_id, current, total)

    try:
        result = run_walkforward(
            config,
            run=run_backtest_service,
            trading_calendar=default_trading_calendar,
            on_fold_complete=on_fold_complete,
        )
        artifact_path = os.path.join(artifact_dir, f'wfo_{wfo_id}.json')
        with open(artifact_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        mark_wfo_run_completed(conn, wfo_id, artifact_path)
    except Exception as exc:
        update_wfo_run_status(conn, wfo_id, 'failed', str(exc))


def submit_wfo_background(
    conn, wfo_id: int, artifact_dir: str = DEFAULT_ARTIFACT_DIR,
) -> threading.Thread:
    thread = threading.Thread(
        target=execute_wfo_once,
        args=(conn, wfo_id, artifact_dir),
        daemon=True,
    )
    thread.start()
    return thread
