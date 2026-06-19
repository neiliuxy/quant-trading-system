from __future__ import annotations

from datetime import date, datetime
import re

import pandas as pd

from datahub.models import DataHubError


def format_date(value) -> str:
    if value is None:
        raise DataHubError("schema_invalid", "date value cannot be None")
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        return text
    return pd.to_datetime(text).strftime("%Y%m%d")


def normalize_frame(frame: pd.DataFrame, columns: list[str] | tuple[str, ...]) -> pd.DataFrame:
    missing = [col for col in columns if col not in frame.columns]
    if missing:
        raise DataHubError("schema_invalid", f"Missing columns: {', '.join(missing)}")
    df = frame[list(columns)].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    if df.empty:
        raise DataHubError("empty_data", "Dataset returned no rows")
    return df


def trim_frame(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    df = frame[(frame["date"] >= start_dt) & (frame["date"] <= end_dt)].copy()
    if df.empty:
        raise DataHubError("empty_data", f"No rows in requested range {start}-{end}")
    return df.reset_index(drop=True)
