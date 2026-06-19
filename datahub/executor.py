from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from server.db import init_db

from datahub.models import DatasetRequest


class DataHubRefreshExecutor:
    """Thread-pool executor for refresh jobs.

    Each worker runs with its own DB connection (opened via `server.db.connect`)
    so SQLite calls don't share state across threads. The caller-supplied
    `worker(conn, request, refresh_id)` callback is responsible for any
    refresh-record writes; this class only owns lifecycle.
    """

    def __init__(self, db_path: str, worker: Callable, max_workers: int = 2):
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self.db_path = db_path
        self.worker = worker
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="datahub-refresh")

    def submit(self, request: DatasetRequest, refresh_id: int) -> Future:
        def task() -> None:
            conn = init_db(self.db_path)
            try:
                self.worker(conn, request, refresh_id)
            finally:
                conn.close()

        return self._pool.submit(task)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)