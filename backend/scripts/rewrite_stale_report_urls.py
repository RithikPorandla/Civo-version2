"""Rewrite known-stale citation URLs inside persisted score_history reports.

When mass.gov restructures a slug, Civo patches the source (so future
reports use the new URL) but existing rows in ``score_history.report``
still carry the old URL in their JSONB. This one-off script walks every
persisted report and performs the same string substitutions we committed
to the Python source.

The rewrite map lives inline — keep it in sync with every URL fix we
ship. Mapping is conservative: only replace URLs we have explicitly
verified as 200 at the new location.

Idempotent (repeated runs do nothing extra). Safe to run during a demo.

Usage
-----
    .venv/bin/python -m scripts.rewrite_stale_report_urls
    .venv/bin/python -m scripts.rewrite_stale_report_urls --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db import SessionLocal


# Canonical mapping of old → new URLs. Every entry here was manually
# verified (HEAD 200) at the time of the 2026-04-16 link-rot sweep.
REWRITE_MAP: dict[str, str] = {
    "https://www.mass.gov/info-details/massgis-data-massdep-wetlands": (
        "https://gis.data.mass.gov/search?q=massdep%20wetlands"
    ),
    "https://www.mass.gov/info-details/massgis-data-noaa-soils": (
        "https://gis.data.mass.gov/search?q=noaa%20soils"
    ),
    "https://www.mass.gov/doc/dpu-24-10-electric-sector-modernization-plan/download": (
        "https://eeaonline.eea.state.ma.us/DPU/Fileroom/dockets/get/?num=24-10"
    ),
    "https://www.mass.gov/regulations/225-CMR-29-site-suitability-criteria-for-clean-energy-infrastructure": (
        "https://www.mass.gov/regulations/225-CMR-29-225-cmr-2900-small-clean-energy-"
        "infrastructure-facility-siting-and-permitting-draft-regulation"
    ),
    "https://www.mass.gov/regulations/225-CMR-20-00-solar-massachusetts-renewable-target-smart-program": (
        "https://www.mass.gov/regulations/225-CMR-2000-solar-massachusetts-renewable-target-smart-program"
    ),
    "https://www.mass.gov/doc/225-cmr-20-solar-massachusetts-renewable-target-smart-program-regulations": (
        "https://www.mass.gov/regulations/225-CMR-2000-solar-massachusetts-renewable-target-smart-program"
    ),
    "https://www.mass.gov/regulations/321-CMR-10-00-massachusetts-endangered-species-act-mesa": (
        "https://www.mass.gov/regulations/321-CMR-1000-massachusetts-endangered-species-act"
    ),
    "https://www.mass.gov/regulations/527-CMR-1-00-massachusetts-comprehensive-fire-safety-code": (
        "https://www.mass.gov/regulations/527-CMR-100-massachusetts-comprehensive-fire-safety-code"
    ),
    "https://www.mass.gov/regulations/780-CMR-massachusetts-state-building-code": (
        "https://www.mass.gov/massachusetts-state-building-code-780-cmr"
    ),
    "https://www.mass.gov/regulations/521-CMR-architectural-access-board": (
        "https://www.mass.gov/law-library/521-cmr"
    ),
    "https://www.mass.gov/info-details/electric-vehicle-charging-make-ready-programs": (
        "https://www.mass.gov/info-details/electric-vehicle-charging"
    ),
    "https://www.mass.gov/info-details/solar-energy-systems": (
        "https://www.mass.gov/info-details/solar"
    ),
    "https://www.mass.gov/doc/massachusetts-nevi-plan/download": (
        "https://www.mass.gov/massdot-nevi-plan"
    ),
}


def _rewrite(raw: str) -> tuple[str, int]:
    """Apply every mapping to a JSON-serialized report. Returns (new_text, n_replacements)."""
    out = raw
    n = 0
    for old, new in REWRITE_MAP.items():
        if old in out:
            n += out.count(old)
            out = out.replace(old, new)
    return out, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Count changes; don't write.")
    args = ap.parse_args()

    touched = 0
    total_replacements = 0
    with SessionLocal() as session:
        rows = (
            session.execute(
                text(
                    """
                    SELECT id, report::text AS report_text
                    FROM score_history
                    ORDER BY id
                    """
                )
            )
            .mappings()
            .all()
        )
        print(f"scanning {len(rows)} reports…")

        for r in rows:
            raw = r["report_text"]
            new_text, n = _rewrite(raw)
            if n == 0:
                continue
            touched += 1
            total_replacements += n
            if args.dry_run:
                print(f"  [dry] report_id={r['id']}  {n} replacements")
                continue
            session.execute(
                text(
                    "UPDATE score_history SET report = CAST(:v AS jsonb) WHERE id = :rid"
                ),
                {"v": new_text, "rid": r["id"]},
            )
        if not args.dry_run:
            session.commit()

    verb = "would update" if args.dry_run else "updated"
    print(f"{verb} {touched} reports · {total_replacements} URL replacements total")

    # Also clear stale link_health rows for the OLD URLs — the next enrichment
    # pass will probe the NEW URLs and repopulate the cache cleanly.
    if not args.dry_run and REWRITE_MAP:
        with SessionLocal() as session:
            deleted = session.execute(
                text("DELETE FROM link_health WHERE url = ANY(:urls)"),
                {"urls": list(REWRITE_MAP.keys())},
            ).rowcount
            session.commit()
            print(f"pruned {deleted} stale link_health rows")


if __name__ == "__main__":
    main()
