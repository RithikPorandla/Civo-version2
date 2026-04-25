"""Ingest MassGIS L3 parcels for all 351 MA towns.

Fetches the authoritative town list directly from MassGIS TOWNSSURVEY so
no hardcoded TOWN_ID dict is needed. Runs towns in parallel with a bounded
thread pool to respect MassGIS rate limits.

Usage:
    python -m scripts.ingest_statewide [options]

Options:
    --workers     Parallel town ingest threads (default: 4)
    --skip-done   Skip towns that already have parcels in the DB
    --town        Restrict to a single town (repeatable, for resuming)
    --dry-run     Fetch town list only, print counts, don't write

Runtime:
    ~4-8 hours for all 351 towns at 4 workers. Re-runs are idempotent
    (INSERT ... ON CONFLICT DO UPDATE). Resume safely with --skip-done.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import engine
from ingest._common import _request_with_retry
from ingest.l3_parcels import FEATURE_URL, PAGE_SIZE, UPSERT_SQL, feature_to_row

TOWNS_URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "Towns_survey_polym/FeatureServer/0/query"
)


def fetch_all_towns() -> list[tuple[int, str]]:
    """Return [(town_id, town_name), ...] for all MA towns from MassGIS."""
    with httpx.Client() as client:
        r = _request_with_retry(
            client,
            "GET",
            TOWNS_URL,
            params={
                "where": "1=1",
                "outFields": "TOWN_ID,TOWN",
                "returnDistinctValues": "true",
                "returnGeometry": "false",
                "f": "json",
                "resultRecordCount": 500,
            },
            timeout=60,
        )
    data = r.json()
    towns = []
    for feat in data.get("features") or []:
        attrs = feat.get("attributes") or {}
        tid = attrs.get("TOWN_ID")
        tname = attrs.get("TOWN") or attrs.get("town")
        if tid and tname:
            towns.append((int(tid), tname.title()))
    towns.sort(key=lambda x: x[1])
    return towns


def count_existing(town_name: str) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM parcels WHERE town_name = :t"),
            {"t": town_name},
        ).scalar() or 0


def ingest_by_id(town_name: str, town_id: int, dry_run: bool = False) -> tuple[str, int]:
    """Fetch and upsert all parcels for a town by its MassGIS TOWN_ID."""
    if dry_run:
        return town_name, 0

    total = 0
    offset = 0
    try:
        with httpx.Client() as client, engine.begin() as conn:
            while True:
                params = {
                    "where": f"TOWN_ID={town_id}",
                    "outFields": "*",
                    "outSR": 26986,
                    "f": "geojson",
                    "resultOffset": offset,
                    "resultRecordCount": PAGE_SIZE,
                    "returnGeometry": "true",
                }
                r = _request_with_retry(client, "GET", FEATURE_URL, params=params, timeout=120)
                page = r.json()
                feats = page.get("features") or []
                if not feats:
                    break
                rows = [r for r in (feature_to_row(f, town_name) for f in feats) if r]
                if rows:
                    conn.execute(UPSERT_SQL, rows)
                total += len(rows)
                exceeded = page.get("exceededTransferLimit") or len(feats) == PAGE_SIZE
                if not exceeded:
                    break
                offset += PAGE_SIZE
    except Exception as exc:
        return town_name, -1  # negative signals error to caller

    return town_name, total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-done", action="store_true", help="Skip towns already in DB")
    parser.add_argument("--town", dest="towns", action="append", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("Fetching town list from MassGIS…")
    all_towns = fetch_all_towns()
    print(f"  {len(all_towns)} towns found")

    if args.towns:
        filter_set = {t.lower() for t in args.towns}
        all_towns = [(tid, tname) for tid, tname in all_towns if tname.lower() in filter_set]
        print(f"  Filtered to {len(all_towns)} towns: {[t for _, t in all_towns]}")

    if args.skip_done:
        before = len(all_towns)
        all_towns = [(tid, tname) for tid, tname in all_towns if count_existing(tname) == 0]
        print(f"  --skip-done: {before - len(all_towns)} towns already have parcels, skipping")

    if not all_towns:
        print("Nothing to ingest.")
        return

    t0 = time.monotonic()
    done = errors = total_parcels = 0

    print(f"\nIngesting {len(all_towns)} towns with {args.workers} workers…\n")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(ingest_by_id, tname, tid, args.dry_run): (tid, tname)
            for tid, tname in all_towns
        }
        for future in as_completed(futures):
            tname, n = future.result()
            done += 1
            if n < 0:
                errors += 1
                print(f"  ERROR  {tname}")
            else:
                total_parcels += n
                elapsed = time.monotonic() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(all_towns) - done) / rate if rate > 0 else 0
                print(
                    f"  [{done}/{len(all_towns)}] {tname}: +{n} parcels  "
                    f"({rate:.1f} towns/s  ETA {eta:.0f}s)"
                )

    elapsed = time.monotonic() - t0
    print(f"\nDone in {elapsed/60:.1f} min — {total_parcels:,} parcels upserted, {errors} errors")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
