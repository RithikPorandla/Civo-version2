"""Ingest National Grid MA EGMP projects into esmp_projects.

Mirrors the structure of ingest/esmp_projects.py but reads from
data/nationalgrid_esmp.csv (derived from National Grid's EGMP filing,
DPU 24-EL-01). Geocodes municipality centroids via Google Places with
the same caching layer used for Eversource.

Usage:
    python ingest/nationalgrid_projects.py [--api-key KEY]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import engine
from ingest._common import _request_with_retry

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "nationalgrid_esmp.csv"
CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "cache" / "ng_geocode.json"
PLACES_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"

SITING_STATUS_MAP = {
    "in_service": "in_service",
    "under_construction": "under_construction",
    "in_permitting": "in_permitting",
    "approved": "approved",
    "planned": "planned",
}

UPSERT_SQL = text("""
    INSERT INTO esmp_projects (
        project_name, sub_region, isd, mw, project_type, status,
        siting_status, coordinate_confidence, municipality, source_filing,
        in_service_date, attrs, geom
    ) VALUES (
        :project_name, :sub_region, :isd, :mw, :project_type, :status,
        :siting_status, :coordinate_confidence, :municipality, :source_filing,
        :in_service_date, CAST(:attrs AS jsonb),
        ST_Transform(ST_SetSRID(ST_Point(:lon, :lat), 4326), 26986)
    )
    ON CONFLICT (project_name) DO UPDATE SET
        sub_region          = EXCLUDED.sub_region,
        isd                 = EXCLUDED.isd,
        mw                  = EXCLUDED.mw,
        project_type        = EXCLUDED.project_type,
        status              = EXCLUDED.status,
        siting_status       = EXCLUDED.siting_status,
        coordinate_confidence = EXCLUDED.coordinate_confidence,
        municipality        = EXCLUDED.municipality,
        source_filing       = EXCLUDED.source_filing,
        in_service_date     = EXCLUDED.in_service_date,
        attrs               = EXCLUDED.attrs,
        geom                = EXCLUDED.geom
""")


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def geocode_municipality(municipality: str, api_key: str, cache: dict) -> tuple[float, float] | None:
    query = f"{municipality}, MA, USA"
    if query in cache:
        c = cache[query]
        return c["lat"], c["lon"]

    if not api_key:
        return None

    with httpx.Client() as client:
        try:
            r = _request_with_retry(
                client,
                "GET",
                PLACES_URL,
                params={
                    "input": query,
                    "inputtype": "textquery",
                    "fields": "geometry",
                    "key": api_key,
                },
                timeout=30,
            )
            data = r.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return None
            loc = candidates[0]["geometry"]["location"]
            cache[query] = {"lat": loc["lat"], "lon": loc["lng"]}
            _save_cache(cache)
            time.sleep(0.05)
            return loc["lat"], loc["lng"]
        except Exception:
            return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", default=os.getenv("GOOGLE_PLACES_API_KEY", ""))
    args = parser.parse_args()

    cache = _load_cache()
    rows = list(csv.DictReader(open(CSV_PATH)))
    print(f"Loaded {len(rows)} National Grid projects from {CSV_PATH.name}")

    inserted = skipped = 0
    with engine.begin() as conn:
        for row in rows:
            muni = row["municipality"].strip()
            coords = geocode_municipality(muni, args.api_key, cache)
            if not coords:
                print(f"  SKIP {row['project_name']} — could not geocode '{muni}'")
                skipped += 1
                continue

            lat, lon = coords
            isd_year = row.get("isd", "").strip()
            try:
                in_service_date = f"{isd_year}-01-01" if isd_year else None
            except Exception:
                in_service_date = None

            attrs = json.dumps({
                "notes": row.get("notes", ""),
                "source_filing": row.get("source_filing", ""),
            })

            conn.execute(UPSERT_SQL, {
                "project_name": row["project_name"].strip(),
                "sub_region": row.get("sub_region", "").strip() or None,
                "isd": isd_year or None,
                "mw": float(row["mw"]) if row.get("mw") else None,
                "project_type": row.get("project_type", "substation").strip(),
                "status": row.get("status", "planned").strip(),
                "siting_status": SITING_STATUS_MAP.get(row.get("status", "planned"), "planned"),
                "coordinate_confidence": "approximate",
                "municipality": muni,
                "source_filing": row.get("source_filing", "NG EGMP DPU 24-EL-01").strip(),
                "in_service_date": in_service_date,
                "attrs": attrs,
                "lat": lat,
                "lon": lon,
            })
            print(f"  OK  {row['project_name']} ({muni})")
            inserted += 1

    print(f"\nDone — {inserted} upserted, {skipped} skipped")


if __name__ == "__main__":
    main()
