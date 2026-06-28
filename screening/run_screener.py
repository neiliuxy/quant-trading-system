"""Run the screener from CLI — quick pick for today's date.

Usage:
    python screening/run_screener.py
    python screening/run_screener.py --date 20260628 --universe 000300 --top 30
"""
import argparse
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from datahub.cache import CacheStore
from datahub.service import DataHub
from server.db import DEFAULT_DB_PATH, init_db

from screening.config import ScreenerRequest
from screening.service import run_screening


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stock screener for a single date.")
    parser.add_argument("--date", default=date.today().strftime("%Y%m%d"),
                        help="Screening date YYYYMMDD (default: today)")
    parser.add_argument("--universe", default="000300",
                        help="Universe symbol for predefined mode (default: 000300)")
    parser.add_argument("--top", type=int, default=30, help="Top N output (default: 30)")
    parser.add_argument("--market-gate", choices=["hard", "soft", "off"], default="hard")
    args = parser.parse_args()

    hub = DataHub(root_dir=ROOT, conn=init_db(DEFAULT_DB_PATH), cache=CacheStore(ROOT))
    request = ScreenerRequest(
        date=args.date,
        universe_mode="predefined",
        universe_symbol=args.universe,
        top_n=args.top,
        market_gate_mode=args.market_gate,
    )
    result = run_screening(hub, request)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())