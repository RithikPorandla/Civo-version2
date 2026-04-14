"""Resolve a human address to a MassGIS L3 parcel ``loc_id``.

Flow
----
1. Geocode the address with Google Places (Find Place From Text).
2. Reproject the (lat, lon) to EPSG:26986.
3. Try ``ST_Contains(parcel.geom, point)``.
4. If nothing contains it (common for vague benchmark addresses like
   "Whately, MA 01093"), fall back to nearest parcel within 2 km.

The resolver caches Places responses under
``data/cache/address_geocode.json`` — same convention as the ESMP seed —
so benchmarks are reproducible without hitting the Places API every run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_PATH = REPO_ROOT / "data" / "cache" / "address_geocode.json"
PLACES_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"


class ResolveError(Exception):
    pass


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def _geocode(address: str) -> tuple[float, float]:
    cache = _load_cache()
    if address in cache and cache[address].get("status") == "OK":
        g = cache[address]
        return g["lat"], g["lon"]
    key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        raise ResolveError(
            f"{address!r} not cached and GOOGLE_PLACES_API_KEY is unset"
        )
    r = httpx.get(
        PLACES_URL,
        params={
            "input": address,
            "inputtype": "textquery",
            "fields": "formatted_address,geometry,place_id,types",
            "key": key,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "OK" or not data.get("candidates"):
        cache[address] = {"status": data.get("status"), "raw": data}
        _save_cache(cache)
        raise ResolveError(f"Places failed for {address!r}: {data.get('status')}")
    c = data["candidates"][0]
    entry = {
        "status": "OK",
        "place_id": c.get("place_id"),
        "formatted_address": c.get("formatted_address"),
        "types": c.get("types"),
        "lat": c["geometry"]["location"]["lat"],
        "lon": c["geometry"]["location"]["lng"],
    }
    cache[address] = entry
    _save_cache(cache)
    return entry["lat"], entry["lon"]


def resolve_parcel(
    session: Session,
    address: str,
    fallback_radius_m: float = 2000.0,
    esmp_anchor_radius_m: float = 5000.0,
) -> tuple[str, str]:
    """Return ``(loc_id, resolution_mode)`` for an address.

    Resolution strategy (in order):
      1. ``esmp_anchored`` — if the geocoded address is within
         ``esmp_anchor_radius_m`` of a known ESMP project, return the
         parcel nearest to that ESMP project. Rationale: a user asking
         "score this address for a substation" near a planned Eversource
         project almost always means that project's site, and the real
         constraints (habitat corridor, wetlands) cluster around the
         project rather than the geocoded point.
      2. ``contains`` — the geocoded point lies inside a parcel polygon.
      3. ``nearest`` — fall back to the nearest parcel within the radius.
    """
    lat, lon = _geocode(address)
    params = {"lat": lat, "lon": lon}

    esmp = session.execute(
        text(
            """
            WITH pt AS (
              SELECT ST_Transform(
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986
              ) AS g
            )
            SELECT e.project_name,
                   ST_Distance(e.geom, pt.g) AS dist
            FROM esmp_projects e, pt
            WHERE ST_DWithin(e.geom, pt.g, :r)
            ORDER BY e.geom <-> pt.g
            LIMIT 1
            """
        ),
        {**params, "r": esmp_anchor_radius_m},
    ).mappings().first()
    if esmp:
        anchored = session.execute(
            text(
                """
                SELECT p.loc_id
                FROM parcels p
                JOIN esmp_projects e ON e.project_name = :proj
                ORDER BY p.geom <-> e.geom
                LIMIT 1
                """
            ),
            {"proj": esmp["project_name"]},
        ).scalar()
        if anchored:
            return anchored, "esmp_anchored"

    contains = session.execute(
        text(
            """
            SELECT loc_id FROM parcels
            WHERE ST_Contains(
                geom,
                ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
            )
            LIMIT 1
            """
        ),
        params,
    ).scalar()
    if contains:
        return contains, "contains"
    nearest = session.execute(
        text(
            """
            SELECT loc_id
            FROM parcels
            WHERE ST_DWithin(
                geom,
                ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986),
                :r
            )
            ORDER BY geom <->
                ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
            LIMIT 1
            """
        ),
        {**params, "r": fallback_radius_m},
    ).scalar()
    if nearest:
        return nearest, "nearest"
    raise ResolveError(
        f"no parcel within {fallback_radius_m:.0f} m of {address!r} "
        f"(lat={lat}, lon={lon})"
    )
