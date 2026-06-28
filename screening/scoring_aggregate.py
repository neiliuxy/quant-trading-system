"""Aggregation helpers — kept tiny so service.py stays readable."""
from __future__ import annotations


def aggregate_and_rank(candidates: list, top_n: int) -> list:
    """Sort by total_score desc, take top_n, assign rank 1..N."""
    candidates = sorted(candidates, key=lambda c: c.total_score, reverse=True)
    candidates = candidates[:top_n]
    for i, c in enumerate(candidates, 1):
        c.rank = i
    return candidates