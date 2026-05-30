import json
import os
import threading

from backtest.service import run_backtest_service
from server.jobs import get_job, mark_job_completed, request_from_job, update_job_status

DEFAULT_ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'results')


def execute_job_once(conn, job_id: int, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> None:
    job = get_job(conn, job_id)
    if job is None:
        return
    os.makedirs(artifact_dir, exist_ok=True)
    update_job_status(conn, job_id, 'running')
    try:
        result = run_backtest_service(request_from_job(job))
        artifact_path = os.path.join(artifact_dir, f'{job_id}.json')
        with open(artifact_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        mark_job_completed(conn, job_id, result.to_dict(), artifact_path)
    except Exception as exc:
        update_job_status(conn, job_id, 'failed', str(exc))


def submit_background(conn, job_id: int, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> threading.Thread:
    thread = threading.Thread(
        target=execute_job_once,
        args=(conn, job_id, artifact_dir),
        daemon=True,
    )
    thread.start()
    return thread
