from __future__ import annotations

from typing import Any

import pandas as pd

from datahub.cache import CacheStore
from datahub.metadata import (
    create_cache_record,
    create_refresh_record,
    get_refresh_record,
    mark_refresh_completed,
)
from datahub.models import DatasetRequest, DatasetResult, DataHubError
from datahub.registry import get_dataset_spec, request_for_feed_id


class DataHub:
    """Central facade for dataset reads: cache lookup, source fetch, refresh logging."""

    SCHEMA_VERSION = "v1"

    def __init__(self, root_dir: str, conn, source):
        self.root_dir = root_dir
        self.conn = conn
        self.source = source
        self.cache = CacheStore(root_dir)

    def get_dataset(self, request: DatasetRequest) -> DatasetResult:
        spec = get_dataset_spec(request.dataset_type)
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
            frame = self.source.fetch(request)
            path = self.cache.write(request, spec, frame)
            self._record_cache(request, spec, frame, path)
        return DatasetResult(
            request=request,
            frame=frame,
            cache_hit=False,
            cache_path=path,
            source_name=self.source.name,
        )

    def create_refresh(self, request: DatasetRequest) -> dict[str, Any]:
        """Run a refresh, return the persisted refresh record."""
        spec = get_dataset_spec(request.dataset_type)
        refresh = create_refresh_record(
            self.conn,
            request_key=request.cache_key,
            dataset_type=request.dataset_type,
            symbol=request.symbol,
            frequency=request.frequency,
            start_date=request.start,
            end_date=request.end,
            force_refresh=request.force_refresh,
            status="running",
        )
        try:
            result = self.get_dataset(request)
        except DataHubError as exc:
            from datahub.metadata import mark_refresh_failed
            mark_refresh_failed(
                self.conn,
                refresh["id"],
                error_type=exc.error_type,
                error_message=exc.message,
            )
            raise
        mark_refresh_completed(
            self.conn,
            refresh["id"],
            cache_hit=result.cache_hit,
            output_cache_path=result.cache_path,
        )
        saved = get_refresh_record(self.conn, refresh["id"])
        # Backfill cache metadata fields that exist on the result but not on the
        # bare refresh row, so callers can inspect source/row_count without a
        # second query.
        saved["dataset_spec"] = spec.dataset_type
        saved["source_name"] = result.source_name
        saved["row_count"] = len(result.frame)
        return saved

    def get_feed_dataframe(self, feed_id: str, start: str, end: str) -> pd.DataFrame:
        """Convenience: resolve a feed_id to a DatasetRequest and load its DataFrame."""
        request = request_for_feed_id(feed_id, start, end)
        return self.get_dataset(request).frame

    def _record_cache(self, request: DatasetRequest, spec, frame: pd.DataFrame, path: str) -> None:
        try:
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
                expires_at=None,
            )
        except Exception:
            # Cache metadata is best-effort; never block the read path.
            pass