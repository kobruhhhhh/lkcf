"""Fetch and save the real January 2026 Elexon snapshot for offline use."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings  # noqa: E402
from app.services.ingest import fetch_live, save_snapshot  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and save the real Elexon snapshot")
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()

    settings = Settings()
    if args.data_dir is not None:
        settings = Settings(data_dir=args.data_dir.resolve())

    bundle = await fetch_live(settings)
    manifest = save_snapshot(
        settings,
        bundle.records_actual,
        bundle.records_forecast,
        created_at=datetime.now(tz=UTC),
    )

    january_actuals = [
        record
        for record in bundle.records_actual
        if "2026-01-01" <= str(record["startTime"])[:10] <= "2026-01-31"
    ]
    january_forecasts = [
        record
        for record in bundle.records_forecast
        if "2026-01-01" <= str(record["startTime"])[:10] <= "2026-01-31"
    ]
    publications = sorted({str(record["publishTime"]) for record in bundle.records_forecast})
    first_period_versions = [
        record
        for record in bundle.records_forecast
        if str(record["startTime"]).startswith("2026-01-01T00:00:00")
    ]

    print(json.dumps(manifest, indent=2, sort_keys=True))
    print("\nValidation")
    print(f"  January FUELHH WIND records: {len(january_actuals)} (expected 1488)")
    print(f"  January WINDFOR rows:        {len(january_forecasts)}")
    print(f"  WINDFOR publications:        {len(publications)}")
    print(f"  Publication range:           {publications[0]} -> {publications[-1]}")
    print(
        "  Versions for 2026-01-01 00:00Z: "
        f"{len(first_period_versions)} "
        f"({min(r['publishTime'] for r in first_period_versions)} -> "
        f"{max(r['publishTime'] for r in first_period_versions)})"
    )
    if len(january_actuals) != 1488:
        print("ERROR: January actual count is not 1,488", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
