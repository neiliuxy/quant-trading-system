from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import glob
import os
import re
import threading

import pandas as pd

from datahub.models import DatasetRequest, DatasetSpec
from datahub.normalize import normalize_frame, trim_frame


@dataclass
class CacheHit:
    frame: pd.DataFrame
    cache_path: str


class CacheStore:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def lock_for(self, request: DatasetRequest) -> threading.Lock:
        """Return an in-process lock for the given data key.

        This prevents concurrent refreshes of the same dataset within a single
        process. It does not protect against concurrent writes from separate
        processes (e.g. multiple FastAPI workers or independent scripts); those
        are currently guarded by the SQLite partial unique index on active
        refreshes and the atomic write/replace in ``CacheStore.write``.
        """
        with self._locks_guard:
            if request.data_key not in self._locks:
                self._locks[request.data_key] = threading.Lock()
            return self._locks[request.data_key]

    def read(self, request: DatasetRequest, spec: DatasetSpec) -> CacheHit | None:
        candidates = self._covering_candidates(request, spec)
        candidates.sort(key=lambda item: int(item[2]) - int(item[1]))
        for path, _, _ in candidates:
            if is_cache_expired(path, request, spec):
                continue
            try:
                df = pd.read_csv(path)
                df = normalize_frame(df, spec.columns)
                df = trim_frame(df, request.start, request.end)
                return CacheHit(frame=df, cache_path=path)
            except Exception:
                continue
        return None

    def write(self, request: DatasetRequest, spec: DatasetSpec, frame: pd.DataFrame) -> str:
        path = self.path_for_write(request, spec)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = f"{path}.tmp"
        frame.to_csv(tmp_path, index=False)
        os.replace(tmp_path, path)
        return path

    def path_for_write(self, request: DatasetRequest, spec: DatasetSpec) -> str:
        covering = self._covering_candidates(request, spec)
        if request.force_refresh and covering:
            covering.sort(key=lambda item: int(item[2]) - int(item[1]), reverse=True)
            return covering[0][0]
        symbol = request.symbol or "global"
        return os.path.join(
            self.root_dir,
            "data",
            "cache",
            spec.dataset_type,
            f"{symbol}_{request.start}_{request.end}.csv",
        )

    def _covering_candidates(self, request: DatasetRequest, spec: DatasetSpec) -> list[tuple[str, str, str]]:
        candidates = []
        for path in self._candidate_paths(request, spec):
            parsed = _parse_cache_filename(path, request, spec)
            if parsed is None:
                continue
            start, end = parsed
            if start <= request.start and end >= request.end:
                candidates.append((path, start, end))
        return candidates

    def _candidate_paths(self, request: DatasetRequest, spec: DatasetSpec) -> list[str]:
        symbol = request.symbol or "global"
        legacy_pattern = os.path.join(self.root_dir, f"{symbol}_*.csv")
        new_pattern = os.path.join(self.root_dir, "data", "cache", spec.dataset_type, f"{symbol}_*.csv")
        if request.symbol is None:
            legacy_pattern = os.path.join(self.root_dir, f"{spec.dataset_type}_*.csv")
        return glob.glob(legacy_pattern) + glob.glob(new_pattern)


def _parse_cache_filename(path: str, request: DatasetRequest, spec: DatasetSpec) -> tuple[str, str] | None:
    name = os.path.basename(path)
    symbol = request.symbol or "global"
    patterns = [
        rf"^{re.escape(symbol)}_.+_(\d{{8}})_(\d{{8}})\.csv$",
        rf"^{re.escape(symbol)}_(\d{{8}})_(\d{{8}})\.csv$",
        rf"^{re.escape(spec.dataset_type)}_(\d{{8}})_(\d{{8}})\.csv$",
    ]
    for pattern in patterns:
        match = re.match(pattern, name)
        if match:
            return match.group(1), match.group(2)
    return None


def is_cache_expired(path: str, request: DatasetRequest, spec: DatasetSpec, now: datetime | None = None) -> bool:
    if spec.cache_policy.ttl_seconds is None:
        return False
    if spec.cache_policy.historical_ttl_seconds is None and request.end < datetime.today().strftime("%Y%m%d"):
        return False
    current = now or datetime.now()
    modified = datetime.fromtimestamp(os.path.getmtime(path))
    return current - modified > timedelta(seconds=spec.cache_policy.ttl_seconds)
