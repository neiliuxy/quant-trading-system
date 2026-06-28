"""Universe loading: predefined index constituents, custom list, full A.

All paths go through DataHub so caching + cache invalidation are consistent.
"""
from __future__ import annotations

import pandas as pd

from datahub.models import DatasetRequest, DataHubError


def load_predefined(
    hub, index_symbol: str, date: str
) -> tuple[list[str], dict[str, str]]:
    """Load constituent codes for an index. Returns (codes, name_map).

    name_map is empty here; caller joins with stock_profile for names.
    """
    try:
        frame = hub.get_dataset(
            DatasetRequest(
                dataset_type="index_constituents",
                symbol=index_symbol,
                start=date,
                end=date,
            )
        ).frame
    except DataHubError:
        return [], {}

    if frame is None or frame.empty:
        return [], {}
    codes = frame["code"].astype(str).str.zfill(6).tolist()
    return codes, {}


def load_full_market(hub, date: str) -> tuple[list[str], dict[str, str]]:
    """Load all A-share codes + name map from stock_profile snapshot."""
    try:
        frame = hub.get_dataset(
            DatasetRequest(
                dataset_type="stock_profile",
                start=date,
                end=date,
            )
        ).frame
    except DataHubError:
        return [], {}

    if frame is None or frame.empty:
        return [], {}

    codes = frame["code"].astype(str).str.zfill(6).tolist()
    name_map = dict(zip(frame["code"].astype(str).str.zfill(6), frame["name"]))
    return codes, name_map


def load_custom(codes: list[str]) -> tuple[list[str], dict[str, str]]:
    """Custom list: caller provides codes; names resolved later via profile."""
    return [str(c).zfill(6) for c in codes], {}


def load_universe(
    hub, request
) -> tuple[list[str], dict[str, str], str]:
    """Dispatch by universe_mode. Returns (codes, name_map, universe_label)."""
    mode = request.universe_mode
    if mode == "predefined":
        if not request.universe_symbol:
            raise ValueError("universe_symbol required for predefined mode")
        codes, names = load_predefined(hub, request.universe_symbol, request.date)
        return codes, names, request.universe_symbol
    if mode == "custom":
        if not request.custom_list:
            raise ValueError("custom_list required for custom mode")
        codes, names = load_custom(request.custom_list)
        return codes, names, "custom"
    if mode == "full_market":
        codes, names = load_full_market(hub, request.date)
        return codes, names, "full_market"
    raise ValueError(f"Unknown universe_mode: {mode}")


def enrich_names(hub, codes: list[str], date: str) -> dict[str, str]:
    """Resolve codes -> names via stock_profile. Used when universe_mode
    is predefined/custom and didn't return a name map."""
    try:
        frame = hub.get_dataset(
            DatasetRequest(
                dataset_type="stock_profile",
                start=date,
                end=date,
            )
        ).frame
    except DataHubError:
        return {}
    if frame is None or frame.empty:
        return {}
    return dict(zip(frame["code"].astype(str).str.zfill(6), frame["name"]))