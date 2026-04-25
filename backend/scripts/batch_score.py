"""Batch pre-scorer — populate score_history for all parcels above a minimum acreage.

Usage:
    python -m scripts.batch_score [options]

Options:
    --project-types   Space-separated list (default: bess_standalone solar_ground_mount)
    --min-acres       Minimum parcel size to score (default: 2.0)
    --workers         ThreadPoolExecutor concurrency (default: 12)
    --config          Scoring config version (default: ma-eea-2026-v1)
    --dry-run         Print counts without writing any rows
    --town            Restrict to a single town name (repeatable)

Examples:
    python -m scripts.batch_score
    python -m scripts.batch_score --min-acres 5 --workers 16
    python -m scripts.batch_score --town Acton --town Burlington --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.scoring.engine import config_for_project_type, score_site

ACRES_TO_M2 = 4046.856
DEFAULT_PROJECT_TYPES = ["bess_standalone", "solar_ground_mount"]
DEFAULT_MIN_ACRES = 2.0
DEFAULT_WORKERS = 12


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_parcel_ids(
    session: Session,
    min_area_m2: float,
    towns: list[str] | None,
) -> list[str]:
    where_parts = ["p.shape_area >= :min_area", "p.geom IS NOT NULL"]
    params: dict = {"min_area": min_area_m2}
    if towns:
        placeholders = ", ".join(f":town_{i}" for i in range(len(towns)))
        where_parts.append(f"p.town_name IN ({placeholders})")
        for i, t in enumerate(towns):
            params[f"town_{i}"] = t

    rows = session.execute(
        text(f"SELECT loc_id FROM parcels p WHERE {' AND '.join(where_parts)} ORDER BY loc_id"),
        params,
    ).scalars().all()
    return list(rows)


def _already_scored(session: Session, parcel_id: str, project_type: str, config: str) -> bool:
    row = session.execute(
        text("""
            SELECT 1 FROM score_history
            WHERE  parcel_loc_id = :pid
              AND  config_version = :cfg
              AND  report->>'project_type' = :pt
            LIMIT  1
        """),
        {"pid": parcel_id, "cfg": config, "pt": project_type},
    ).fetchone()
    return row is not None


def _score_and_persist(parcel_id: str, project_type: str, dry_run: bool) -> str:
    """Score one (parcel, project_type) pair. Returns 'skip', 'dry-run', 'ok', or 'error:...'."""
    config = config_for_project_type(project_type)
    with SessionLocal() as session:
        # Disable parallel workers per session — each worker grabs shared memory
        # segments; in Docker the default shm is 64MB which exhausts quickly.
        session.execute(text("SET max_parallel_workers_per_gather = 0"))
        session.execute(text("SET work_mem = '2MB'"))

        if _already_scored(session, parcel_id, project_type, config):
            return "skip"
        if dry_run:
            return "dry-run"
        try:
            report = score_site(session, parcel_id, project_type, config)
            report_dict = report.model_dump(mode="json")
            session.execute(
                text("""
                    INSERT INTO score_history
                        (parcel_loc_id, address, config_version, total_score, bucket, report)
                    VALUES
                        (:pid, :addr, :cfg, :total, :bucket, CAST(:report AS jsonb))
                    ON CONFLICT DO NOTHING
                """),
                {
                    "pid": report.parcel_id,
                    "addr": report.address,
                    "cfg": report.config_version,
                    "total": report.total_score,
                    "bucket": report.bucket,
                    "report": json.dumps(report_dict),
                },
            )
            session.commit()
            return "ok"
        except Exception as exc:
            return f"error:{str(exc)[:120]}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-types", nargs="+", default=DEFAULT_PROJECT_TYPES)
    parser.add_argument("--min-acres", type=float, default=DEFAULT_MIN_ACRES)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--town", dest="towns", action="append", default=None)
    args = parser.parse_args()

    min_area_m2 = args.min_acres * ACRES_TO_M2

    with SessionLocal() as session:
        parcel_ids = _fetch_parcel_ids(session, min_area_m2, args.towns)

    total_jobs = len(parcel_ids) * len(args.project_types)
    print(
        f"{'[DRY RUN] ' if args.dry_run else ''}"
        f"{len(parcel_ids)} parcels × {len(args.project_types)} project types "
        f"= {total_jobs} jobs  |  {args.workers} workers"
    )
    if args.towns:
        print(f"Towns: {', '.join(args.towns)}")

    if total_jobs == 0:
        print("Nothing to score.")
        return

    counters = {"ok": 0, "skip": 0, "dry-run": 0, "error": 0}
    t0 = time.monotonic()

    jobs = [
        (pid, pt)
        for pid in parcel_ids
        for pt in args.project_types
    ]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_score_and_persist, pid, pt, args.dry_run): (pid, pt)
            for pid, pt in jobs
        }
        done = 0
        for future in as_completed(futures):
            result = future.result()
            key = result if result in counters else "error"
            counters[key] += 1
            done += 1
            if done % 100 == 0 or done == total_jobs:
                elapsed = time.monotonic() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total_jobs - done) / rate if rate > 0 else 0
                print(
                    f"  {done}/{total_jobs}  "
                    f"ok={counters['ok']} skip={counters['skip']} err={counters['error']}  "
                    f"{rate:.1f}/s  ETA {eta:.0f}s",
                    end="\r",
                    flush=True,
                )

    elapsed = time.monotonic() - t0
    print()  # newline after \r
    print(
        f"\nDone in {elapsed:.1f}s  —  "
        f"ok={counters['ok']}  skip={counters['skip']}  "
        f"dry-run={counters['dry-run']}  error={counters['error']}"
    )
    if counters["error"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
