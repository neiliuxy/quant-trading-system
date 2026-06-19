from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Iterable

import pandas as pd

from datahub.cache import CacheStore
from datahub.metadata import (
    create_cache_record,
    create_refresh_record,
    find_running_refresh,
    get_refresh_record,
    list_cache_records,
    mark_refresh_completed,
    mark_refresh_failed,
    mark_refresh_running,
)
from datahub.models import DatasetRequest, DatasetResult, DataHubError
from datahub.normalize import normalize_frame
from datahub.registry import (
    get_dataset_spec,
    list_dataset_specs,
    request_for_feed_id,
)
from datahub.sources import AkshareSource


class DataHub:
    """Central facade for dataset reads: cache lookup, source fetch, refresh logging."""

    SCHEMA_VERSION = "v1"

    def __init__(self, root_dir: str, conn, source=None, executor=None, cache=None):
        self.root_dir = root_dir
        self.conn = conn
        self.source = source or AkshareSource()
        self.cache = cache if cache is not None else CacheStore(root_dir)
        self.executor = executor

    def get_dataset(self, request: DatasetRequest) -> DatasetResult:
        spec = get_dataset_spec(request.dataset_type)
        if spec.symbol_required and not request.symbol:
            raise DataHubError("unsupported_dataset", f"{request.dataset_type} requires symbol")
        with self.cache.lock_for(request):
            if not request.force_refresh:
                hit = self.cache.read(request, spec)
                if hit is not None:
                    return DatasetResult(
                        request=request,
                        frame=hit.frame,
                        cache_hit=True,
                        cache_path=hit.cache_path,
                        source_name=spec.source_name,
                    )
            raw = self.source.fetch(request)
            frame = normalize_frame(raw, spec.columns)
            path = self.cache.write(request, spec, frame)
            self._record_cache(request, spec, frame, path)
        return DatasetResult(
            request=request,
            frame=frame,
            cache_hit=False,
            cache_path=path,
            source_name=spec.source_name,
        )

    def create_refresh(self, request: DatasetRequest) -> dict[str, Any]:
        """Create a refresh record and either dispatch to the executor or run inline.

        Returns the persisted refresh record. Conflicts (concurrent force_refresh
        for the same cache_key) raise DataHubError('refresh_in_progress').
        """
        non_force = DatasetRequest(
            dataset_type=request.dataset_type,
            symbol=request.symbol,
            start=request.start,
            end=request.end,
            frequency=request.frequency,
            force_refresh=False,
        )
        if request.force_refresh:
            existing = find_running_refresh(self.conn, non_force.cache_key)
            if existing is not None:
                raise DataHubError(
                    "refresh_in_progress",
                    f"Refresh already running: {existing['id']}",
                    {"refresh_id": existing["id"]},
                )

        running = find_running_refresh(self.conn, request.cache_key)
        if running is not None:
            return running

        if not request.force_refresh:
            spec = get_dataset_spec(request.dataset_type)
            hit = self.cache.read(request, spec)
            if hit is not None:
                record = create_refresh_record(
                    self.conn,
                    request_key=request.cache_key,
                    dataset_type=request.dataset_type,
                    symbol=request.symbol,
                    frequency=request.frequency,
                    start_date=request.start,
                    end_date=request.end,
                    force_refresh=request.force_refresh,
                    status="completed",
                )
                mark_refresh_completed(self.conn, record["id"], cache_hit=True, output_cache_path=hit.cache_path)
                return get_refresh_record(self.conn, record["id"])

        try:
            record = create_refresh_record(
                self.conn,
                request_key=request.cache_key,
                dataset_type=request.dataset_type,
                symbol=request.symbol,
                frequency=request.frequency,
                start_date=request.start,
                end_date=request.end,
                force_refresh=request.force_refresh,
                status="queued",
            )
        except sqlite3.IntegrityError:
            # Concurrent request already inserted an active record; return it.
            running = find_running_refresh(self.conn, request.cache_key)
            if running is not None:
                return running
            raise
        if self.executor is not None:
            self.executor.submit(request, record["id"])
        return get_refresh_record(self.conn, record["id"])

    def execute_refresh_once(self, request: DatasetRequest, refresh_id: int, conn=None) -> None:
        """Run one refresh inside a worker thread; update its record on completion/failure."""
        target = conn if conn is not None else self.conn
        mark_refresh_running(target, refresh_id)
        try:
            result = self.get_dataset(request)
        except DataHubError as exc:
            mark_refresh_failed(target, refresh_id, error_type=exc.error_type, error_message=exc.message)
            return
        except Exception as exc:
            mark_refresh_failed(target, refresh_id, error_type="source_unavailable", error_message=str(exc))
            return
        mark_refresh_completed(
            target,
            refresh_id,
            cache_hit=result.cache_hit,
            output_cache_path=result.cache_path,
        )

    def get_refresh(self, refresh_id: int) -> dict[str, Any] | None:
        return get_refresh_record(self.conn, refresh_id)

    def get_feed_dataframe(self, feed_id: str, start: str, end: str) -> pd.DataFrame:
        """Convenience: resolve a feed_id to a DatasetRequest and load its DataFrame."""
        request = request_for_feed_id(feed_id, start, end)
        return self.get_dataset(request).frame

    def list_datasets(self) -> list:
        return list_dataset_specs()

    def list_cache(
        self,
        *,
        dataset_type: str | None = None,
        symbol: str | None = None,
        frequency: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        return list_cache_records(
            self.conn,
            dataset_type=dataset_type,
            symbol=symbol,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
        )

    def resolve_feed_requests(
        self, feed_ids: Iterable[str], start: str, end: str
    ) -> list[DatasetRequest]:
        return [request_for_feed_id(feed_id, start, end) for feed_id in feed_ids]

    def _record_cache(self, request: DatasetRequest, spec, frame: pd.DataFrame, path: str) -> None:
        try:
            expires_at = self._compute_expires_at(request, spec)
            create_cache_record(
                self.conn,
                dataset_type=request.dataset_type,
                symbol=request.symbol,
                frequency=request.frequency,
                start_date=request.start,
                end_date=request.end,
                file_path=path,
                row_count=len(frame),
                schema_version=self.SCHEMA_VERSION,
                source_name=spec.source_name,
                expires_at=expires_at,
            )
        except Exception:
            # Cache metadata is best-effort; never block the read path.
            pass

    @staticmethod
    def _compute_expires_at(request: DatasetRequest, spec) -> str | None:
        """Return metadata expiry timestamp aligned with cache.read TTL logic.

        Historical intervals (end < today) only expire when a historical TTL is
        configured; otherwise the cache is treated as immutable and ``None`` is
        returned. Current/up-to-today intervals use ``ttl_seconds``.
        """
        policy = spec.cache_policy
        if policy.ttl_seconds is None:
            return None
        today = datetime.today().strftime("%Y%m%d")
        is_historical = request.end < today
        if is_historical and policy.historical_ttl_seconds is None:
            return None
        ttl = policy.ttl_seconds
        if is_historical and policy.historical_ttl_seconds is not None:
            ttl = policy.historical_ttl_seconds
        return (datetime.now() + timedelta(seconds=ttl)).strftime("%Y-%m-%dT%H:%M:%S")