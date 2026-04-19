"""Seed National Grid (DPU 24-11) + Unitil (DPU 24-12) ESMP projects.

Sister script to ``esmp_projects.py`` (which handles Eversource / DPU 24-10).
Reads ``data/other_utility_esmp_projects.csv`` — hand-curated from public
National Grid + Unitil ESMP filings and construction-project pages — and
upserts rows into the shared ``esmp_projects`` table, keyed by
``project_name``.

Geocoding
---------
CSV rows carry only a municipality, not a street address (National Grid and
Unitil don't publish precise coordinates for planned projects). We geocode
each municipality via the same Places API + cache pattern as the Eversource
seed, and set ``coordinate_confidence = 'town_centroid'`` so downstream
consumers can see the precision we're working with.

Idempotent: ON CONFLICT (project_name) DO UPDATE.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import engine  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "data" / "other_utility_esmp_projects.csv"
# Reuse the same cache file — town geocodes are town geocodes, regardless of
# which utility happens to be siting there.
CACHE_PATH = REPO_ROOT / "data" / "cache" / "esmp_geocode.json"
PLACES_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def _geocode_municipality(municipality: str, cache: dict) -> tuple[float, float]:
    """Return (lat, lon) for a MA municipality. Cache first, Places API second."""
    query = f"{municipality}, Massachusetts"
    if query in cache and cache[query].get("status") == "OK":
        entry = cache[query]
        return entry["lat"], entry["lon"]

    key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            f"{query!r} not cached and GOOGLE_PLACES_API_KEY is unset — "
            "either export the key or pre-populate data/cache/esmp_geocode.json."
        )

    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "geometry/location,formatted_address",
        "key": key,
    }
    r = httpx.get(PLACES_URL, params=params, timeout=10.0)
    r.raise_for_status()
    payload = r.json()
    candidates = payload.get("candidates") or []
    if not candidates:
        cache[query] = {"status": "ZERO_RESULTS"}
        _save_cache(cache)
        raise RuntimeError(f"Places API returned no candidate for {query!r}")

    loc = candidates[0]["geometry"]["location"]
    entry = {
        "status": "OK",
        "lat": loc["lat"],
        "lon": loc["lng"],
        "formatted_address": candidates[0].get("formatted_address"),
    }
    cache[query] = entry
    _save_cache(cache)
    return entry["lat"], entry["lon"]


UPSERT_SQL = text(
    """
    INSERT INTO esmp_projects (
      project_name, sub_region, isd, mw, project_type, status,
      siting_status, coordinate_confidence, in_service_date, municipality,
      source_filing, attrs, geom
    ) VALUES (
      :project_name, :sub_region, :isd, :mw, :project_type, :status,
      :siting_status, :coord_conf, :in_service_date, :municipality,
      :source_filing, CAST(:attrs AS JSONB),
      ST_Transform(
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
        26986
      )
    )
    ON CONFLICT (project_name) DO UPDATE SET
      sub_region = EXCLUDED.sub_region,
      isd = EXCLUDED.isd,
      project_type = EXCLUDED.project_type,
      status = EXCLUDED.status,
      siting_status = EXCLUDED.siting_status,
      coordinate_confidence = EXCLUDED.coordinate_confidence,
      in_service_date = EXCLUDED.in_service_date,
      municipality = EXCLUDED.municipality,
      source_filing = EXCLUDED.source_filing,
      attrs = EXCLUDED.attrs,
      geom = EXCLUDED.geom
    """
)


def _parse_year(year: str) -> date | None:
    y = (year or "").strip()
    if not y:
        return None
    try:
        return date(int(y), 1, 1)
    except ValueError:
        return None


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"Missing CSV: {CSV_PATH}")

    cache = _load_cache()
    rows_written = 0

    with engine.begin() as conn, CSV_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["project_name"].strip()
            if not name:
                continue
            municipality = row["municipality"].strip()
            if not municipality:
                print(f"!! {name!r} — no municipality; skipping")
                continue

            try:
                lat, lon = _geocode_municipality(municipality, cache)
            except Exception as e:  # noqa: BLE001
                print(f"!! geocode failed for {municipality!r}: {e}")
                continue

            attrs = {
                "utility": row["utility"].strip(),
                "source_url": row["source_url"].strip(),
            }
            year = row.get("planned_in_service_year", "").strip()
            if year:
                attrs["planned_in_service_year"] = year

            conn.execute(
                UPSERT_SQL,
                {
                    "project_name": name,
                    "sub_region": row["utility"].strip(),  # National Grid / Unitil
                    "isd": year or None,
                    "mw": None,
                    "project_type": row["project_type"].strip(),
                    "status": row.get("description", "")[:200],
                    "siting_status": row["siting_status"].strip(),
                    "coord_conf": "town_centroid",
                    "in_service_date": _parse_year(year),
                    "municipality": municipality,
                    "source_filing": row["docket"].strip(),
                    "attrs": json.dumps(attrs),
                    "lat": lat,
                    "lon": lon,
                },
            )
            rows_written += 1
            print(f"✓ {name!r} ({municipality})")

    print(f"\nUpserted {rows_written} ESMP projects from National Grid + Unitil.")


if __name__ == "__main__":
    main()
