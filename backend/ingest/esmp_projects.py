"""Seed the Eversource ESMP project pipeline (DPU 24-10, Jan 2024).

Reads ``data/esmp_projects.csv`` (derived from
``docs/eversource_esmp_pipeline.xlsx``), normalizes each row's municipality
into a Google Places query, geocodes (or loads cached geocode), and upserts
into ``esmp_projects``.

Cached responses: ``data/cache/esmp_geocode.json`` — committed to git so the
seed is reproducible without a Places key. Missing project IDs trigger a
live Places call (requires ``GOOGLE_PLACES_API_KEY``) and are appended.

Idempotent: ``ON CONFLICT (project_name) DO UPDATE``.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import engine  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "data" / "esmp_projects.csv"
CACHE_PATH = REPO_ROOT / "data" / "cache" / "esmp_geocode.json"

PLACES_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"

# Project IDs whose siting Eversource hasn't finalized — per user direction
# (typically 2030-2034 planned projects). Match by substring on the CSV's
# Project Name.
PENDING_SITING_NAME_PATTERNS = [
    "New South End Substation",
    "New Allston/Fenway/Brookline Substation",
    "New Charlestown/Somerville Substation",
    "New Metro Boston Network Substation",
    "New Saxonville/Natick Substation",
    "New North Acton Substation",
    "New Waltham Substation",
    "New Dennis/Brewster Substation",
    "New Worthington Substation",
    "Whately-Deerfield Group CIP",
]

# Status/Phase → controlled vocabulary (order matters; first match wins).
_SITING_STATUS_RULES: list[tuple[str, str]] = [
    ("in construction", "under_construction"),
    ("in progress", "under_construction"),
    ("under construction", "under_construction"),
    ("interim operational", "in_service"),
    ("in service", "in_service"),
    ("efsb tentative", "in_permitting"),
    ("permitting", "in_permitting"),
    ("design", "in_permitting"),
    ("cert proceeding", "in_permitting"),
    ("internally approved", "approved"),
    ("approved", "approved"),
    ("dpu 22-47 approved", "approved"),
    ("planning phase", "planned"),
    ("preliminary", "planned"),
    ("proposed", "planned"),
    ("planned", "planned"),
]


def normalize_siting_status(raw: str) -> str:
    r = (raw or "").lower()
    for needle, code in _SITING_STATUS_RULES:
        if needle in r:
            return code
    return "planned"


def normalize_place_query(muni: str) -> tuple[str, bool]:
    """Turn the xlsx Primary Municipality into a Places query string.

    Returns ``(query, has_neighborhood)``.  ``has_neighborhood`` is True
    when a parenthetical locale was present and is promoted to the front of
    the query — that's the cue that an ``exact`` match is attainable.
    """
    s = (muni or "").strip()
    m = re.match(r"^([^(]+?)\s*\(([^)]+)\)\s*(?:/\s*(.+))?$", s)
    if m:
        town = m.group(1).strip()
        neigh = m.group(2).strip()
        # Inside a parenthetical, a "/" means multiple neighborhoods — take the first.
        neigh = neigh.split("/")[0].strip()
        # Common abbreviation fixes.
        neigh = re.sub(r"\bSq\b\.?", "Square", neigh, flags=re.IGNORECASE)
        if neigh.lower() in {"downtown"}:
            return f"Downtown {town}, MA", True
        if neigh.lower() in {"north", "south", "east", "west"}:
            return f"{neigh} {town}, MA", True
        return f"{neigh}, {town}, MA", True
    # Slash without parenthetical: take first town, note multi-town in caller.
    if "/" in s:
        first = s.split("/")[0].strip()
        return f"{first}, MA", False
    return f"{s}, MA", False


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def places_lookup(query: str, api_key: str) -> dict:
    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "formatted_address,geometry,place_id,types,name",
        "key": api_key,
    }
    r = httpx.get(PLACES_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "OK" or not data.get("candidates"):
        return {"status": data.get("status"), "query": query, "raw": data}
    c = data["candidates"][0]
    return {
        "status": "OK",
        "query": query,
        "place_id": c.get("place_id"),
        "formatted_address": c.get("formatted_address"),
        "types": c.get("types") or [],
        "lat": c["geometry"]["location"]["lat"],
        "lon": c["geometry"]["location"]["lng"],
    }


def classify_confidence(
    project_name: str, has_neighborhood: bool, places_result: dict | None
) -> str:
    if any(p in project_name for p in PENDING_SITING_NAME_PATTERNS):
        return "pending_siting"
    if not places_result or places_result.get("status") != "OK":
        return "approximate"
    types = set(places_result.get("types") or [])
    neighborhood_types = {"sublocality", "sublocality_level_1", "neighborhood"}
    # Places resolved to a sub-town locale — treat as exact regardless of
    # whether the source string had a parenthetical; places like "East
    # Freetown" (a village in Freetown) come back typed as "neighborhood"
    # without a parenthetical in the xlsx.
    if types & neighborhood_types:
        return "exact"
    # Seaport/Kendall sometimes resolve to a specific establishment/premise
    # — only count those as exact if the source string actually signaled a
    # sub-town locale (parenthetical), so we don't promote a random town-
    # level hit that happens to match a POI.
    if has_neighborhood and ({"point_of_interest", "establishment", "premise"} & types):
        return "exact"
    return "approximate"


UPSERT_SQL = text(
    """
INSERT INTO esmp_projects (
    project_name, sub_region, isd, mw, project_type, status,
    siting_status, coordinate_confidence, in_service_date,
    municipality, source_filing, attrs, geom
) VALUES (
    :project_name, :sub_region, :isd, :mw, :project_type, :status,
    :siting_status, :coordinate_confidence, :in_service_date,
    :municipality, :source_filing, CAST(:attrs AS jsonb),
    ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
)
ON CONFLICT (project_name) DO UPDATE SET
    sub_region            = EXCLUDED.sub_region,
    isd                   = EXCLUDED.isd,
    mw                    = EXCLUDED.mw,
    project_type          = EXCLUDED.project_type,
    status                = EXCLUDED.status,
    siting_status         = EXCLUDED.siting_status,
    coordinate_confidence = EXCLUDED.coordinate_confidence,
    in_service_date       = EXCLUDED.in_service_date,
    municipality          = EXCLUDED.municipality,
    source_filing         = EXCLUDED.source_filing,
    attrs                 = EXCLUDED.attrs,
    geom                  = EXCLUDED.geom;
"""
)


def run() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"missing {CSV_PATH}")

    cache = load_cache()
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()

    rows_out = []
    breakdown = {"exact": 0, "approximate": 0, "pending_siting": 0}

    with CSV_PATH.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = str(row["Project ID"]).strip()
            if not pid:
                continue
            name = row["Project Name"].strip()
            muni_raw = row["Primary Municipality"].strip()
            query, has_neigh = normalize_place_query(muni_raw)

            geo = cache.get(pid)
            if geo is None:
                if not api_key:
                    raise SystemExit(f"project {pid} not cached and GOOGLE_PLACES_API_KEY is unset")
                geo = places_lookup(query, api_key)
                cache[pid] = geo
                save_cache(cache)  # persist incrementally

            confidence = classify_confidence(name, has_neigh, geo)
            breakdown[confidence] = breakdown.get(confidence, 0) + 1

            if geo.get("status") != "OK" and confidence != "pending_siting":
                raise SystemExit(f"geocode failed for {pid} ({query}): {geo}")

            # For pending_siting rows without a good geocode, still use whatever
            # Places returned (or fall back to town centroid could be added later).
            lat, lon = geo.get("lat"), geo.get("lon")
            if lat is None or lon is None:
                # Fallback: re-query town-only and cache under a synthetic key.
                town_only = muni_raw.split("(")[0].split("/")[0].strip() + ", MA"
                fb = places_lookup(town_only, api_key) if api_key else {}
                if fb.get("status") != "OK":
                    raise SystemExit(f"cannot resolve any coordinate for {pid} (query={query})")
                lat, lon = fb["lat"], fb["lon"]
                geo["fallback"] = fb
                cache[pid] = geo
                save_cache(cache)

            mw_added = row["MW Added"]
            isd_raw = row["Target ISD"]
            try:
                isd_year = int(isd_raw) if isd_raw else None
            except (TypeError, ValueError):
                isd_year = None

            attrs = {
                "project_id": pid,
                "communities_served": row.get("Communities Served"),
                "voltage": row.get("Voltage"),
                "esmp_page": row.get("ESMP Page"),
                "permitting_notes": row.get("Permitting Notes"),
                "source_initiative": row.get("Source Project / Initiative"),
                "mw_expandable_to": row.get("MW Expandable To"),
                "multi_town": "/" in muni_raw,
                "places_query": query,
                "places_place_id": geo.get("place_id"),
                "places_formatted_address": geo.get("formatted_address"),
                "places_types": geo.get("types"),
            }

            rows_out.append(
                {
                    "project_name": name,
                    "sub_region": row.get("Sub-Region"),
                    "isd": isd_raw,
                    "mw": float(mw_added) if mw_added not in ("", None) else None,
                    "project_type": row.get("Project Type"),
                    "status": row.get("Status / Phase"),
                    "siting_status": normalize_siting_status(row.get("Status / Phase") or ""),
                    "coordinate_confidence": confidence,
                    "in_service_date": date(isd_year, 1, 1) if isd_year else None,
                    "municipality": muni_raw,
                    "source_filing": "DPU 24-10",
                    "attrs": json.dumps(attrs),
                    "lat": lat,
                    "lon": lon,
                }
            )

    with engine.begin() as conn:
        conn.execute(UPSERT_SQL, rows_out)

    print(f"Seeded {len(rows_out)} ESMP projects.")
    print("coordinate_confidence breakdown:")
    for k in ("exact", "approximate", "pending_siting"):
        print(f"  {k:>16}: {breakdown.get(k, 0)}")


if __name__ == "__main__":
    run()
