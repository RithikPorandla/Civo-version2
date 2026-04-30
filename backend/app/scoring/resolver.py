"""Resolve a human address to a MassGIS L3 parcel ``loc_id``.

Resolution strategy (in order of preference):
  1. ``contains`` — the geocoded point is inside a parcel polygon. This
     is the only resolution mode that means "we found your exact
     address." If ``contains`` succeeds, we ignore every other mode.
  2. ``esmp_anchored`` — **only** when ``project_type`` is substation
     or transmission AND the geocoded point is very close (default
     500 m) to an ESMP project. In this narrow case, the user almost
     certainly means that project's site, and anchoring to the project
     gives us more faithful constraint data than the geocoded point.
  3. ``nearest`` — fall back to the nearest parcel within a small
     radius (default 500 m). If the closest parcel is farther than
     that, we raise ``ResolveError`` rather than silently scoring a
     distant parcel.

Why the strict radii: the previous default (2 km nearest + 8 km ESMP
anchor) produced surprises — e.g. a query for "Wareham, MA" snapping
to a Falmouth parcel because the Falmouth ESMP project happened to be
within 8 km. Consultants screening candidate sites need the resolver
to stay on the address they typed, or fail loudly so they can refine.

The returned metadata includes the original query, the resolved
parcel's site_addr + town, and the straight-line distance from the
geocoded point to the parcel — all surfaced on the Report page so the
consultant can see exactly what we scored vs what they asked for.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_PATH = REPO_ROOT / "data" / "cache" / "address_geocode.json"
PLACES_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"

# Narrow radii by design — see module docstring for rationale.
DEFAULT_NEAREST_RADIUS_M = 500.0
DEFAULT_ESMP_ANCHOR_RADIUS_M = 500.0
ESMP_ANCHOR_ELIGIBLE_TYPES = {"substation", "transmission"}


class ResolveError(Exception):
    pass


def _street_number(text: str) -> str | None:
    """Extract the leading street number from an address string, e.g. '100 Main St' → '100'."""
    m = re.match(r"^\s*(\d+)", text.strip())
    return m.group(1) if m else None


def _parse_ma_address(query: str) -> tuple[int | None, str | None, str | None]:
    """Parse 'NUMBER STREET, TOWN, MA...' into (num, street_upper, town_upper).

    Handles formats like:
      '100 Nagog Park, Acton, MA'
      '100 Nagog Park, Acton MA 01720'
      '100 Nagog Park Acton MA'  (no comma between street and town)

    Returns (None, None, None) if parsing fails.
    """
    q = query.strip()
    # Strip trailing state/zip: ', MA 01234' or ', MA' or ' MA 01234'
    q = re.sub(r",?\s*MA\b.*$", "", q, flags=re.IGNORECASE).strip().rstrip(",").strip()

    # Try: 'NUMBER STREET, TOWN'
    m = re.match(r"^(\d+\w*)\s+(.+?),\s*(.+)$", q)
    if m:
        try:
            num = int(re.match(r"^\d+", m.group(1)).group())
        except Exception:
            return None, None, None
        return num, m.group(2).strip().upper(), m.group(3).strip().upper()

    # Try: 'NUMBER STREET TOWN' (no comma — take last word as town, unlikely but fallback)
    return None, None, None


# Whether the address_points table exists and has been loaded.
# Checked once per process; None = unknown, True/False = cached.
_AP_TABLE_READY: bool | None = None


def _ap_table_ready(session) -> bool:
    """Return True if address_points table exists and has rows."""
    global _AP_TABLE_READY
    if _AP_TABLE_READY is not None:
        return _AP_TABLE_READY
    try:
        row = session.execute(
            text("SELECT COUNT(*) FROM address_points LIMIT 1")
        ).scalar()
        _AP_TABLE_READY = (row or 0) > 0
    except Exception:
        _AP_TABLE_READY = False
    return _AP_TABLE_READY


def _resolve_via_address_points(
    session,
    query: str,
    formatted: str | None,
) -> "ResolvedParcel | None":
    """Step 0: look up the address in the address_points table.

    Tries three tiers in order:
      1. (num, street_exact, town) with loc_id already populated → direct hit
      2. (num, street_exact, town) without loc_id → use lat/lon for ST_Contains
      3. (num, street_prefix_3chars, town) → handles minor abbreviation differences

    Returns None if the table doesn't have the town loaded yet.
    """
    if not _ap_table_ready(session):
        return None

    num, street, town = _parse_ma_address(formatted or query)
    if num is None or not street or not town:
        return None

    params: dict = {"num": num, "street": street, "town": town}

    # Tier 1: exact street + pre-computed loc_id
    row = session.execute(
        text("""
            SELECT loc_id, lat, lon, street_name, town
            FROM   address_points
            WHERE  addr_num    = :num
              AND  street_name = :street
              AND  town        = :town
              AND  loc_id IS NOT NULL
            ORDER BY point_type = 'BC' DESC
            LIMIT 1
        """),
        params,
    ).mappings().first()

    if row:
        # Confirm parcel still exists (cheap PK lookup)
        parcel = session.execute(
            text("SELECT loc_id, site_addr, town_name FROM parcels WHERE loc_id = :lid"),
            {"lid": row["loc_id"]},
        ).mappings().first()
        if parcel:
            return ResolvedParcel(
                loc_id=parcel["loc_id"],
                resolution_mode="addr_match",
                original_query=query,
                formatted_address=formatted,
                resolved_site_addr=parcel["site_addr"],
                resolved_town=parcel["town_name"],
                distance_m=0.0,
            )

    # Tier 2: exact street, no loc_id yet — use lat/lon for spatial lookup
    row = session.execute(
        text("""
            SELECT lat, lon, street_name, town
            FROM   address_points
            WHERE  addr_num    = :num
              AND  street_name = :street
              AND  town        = :town
            ORDER BY point_type = 'BC' DESC
            LIMIT 1
        """),
        params,
    ).mappings().first()

    if row:
        hit = session.execute(
            text("""
                SELECT loc_id, site_addr, town_name,
                       ST_Distance(
                           geom,
                           ST_Transform(ST_SetSRID(ST_MakePoint(:lon,:lat),4326),26986)
                       ) AS dist
                FROM   parcels
                WHERE  ST_Contains(
                           geom,
                           ST_Transform(ST_SetSRID(ST_MakePoint(:lon,:lat),4326),26986)
                       )
                LIMIT 1
            """),
            {"lat": row["lat"], "lon": row["lon"]},
        ).mappings().first()
        if hit:
            # Cache the loc_id so future queries skip the spatial step
            try:
                session.execute(
                    text("""
                        UPDATE address_points
                        SET loc_id = :lid
                        WHERE addr_num = :num AND street_name = :street AND town = :town
                          AND loc_id IS NULL
                    """),
                    {"lid": hit["loc_id"], **params},
                )
                session.commit()
            except Exception:
                session.rollback()
            return ResolvedParcel(
                loc_id=hit["loc_id"],
                resolution_mode="addr_match",
                original_query=query,
                formatted_address=formatted,
                resolved_site_addr=hit["site_addr"],
                resolved_town=hit["town_name"],
                distance_m=float(hit["dist"] or 0.0),
            )

    # Tier 3: street name prefix match (handles 'NAGOG PK' vs 'NAGOG PARK')
    street_prefix = street[:6] if len(street) >= 6 else street
    row = session.execute(
        text("""
            SELECT lat, lon, street_name, town
            FROM   address_points
            WHERE  addr_num    = :num
              AND  street_name LIKE :prefix || '%'
              AND  town        = :town
            ORDER BY point_type = 'BC' DESC, length(street_name)
            LIMIT 1
        """),
        {**params, "prefix": street_prefix},
    ).mappings().first()

    if row:
        hit = session.execute(
            text("""
                SELECT loc_id, site_addr, town_name,
                       ST_Distance(
                           geom,
                           ST_Transform(ST_SetSRID(ST_MakePoint(:lon,:lat),4326),26986)
                       ) AS dist
                FROM   parcels
                WHERE  ST_Contains(
                           geom,
                           ST_Transform(ST_SetSRID(ST_MakePoint(:lon,:lat),4326),26986)
                       )
                LIMIT 1
            """),
            {"lat": row["lat"], "lon": row["lon"]},
        ).mappings().first()
        if hit:
            return ResolvedParcel(
                loc_id=hit["loc_id"],
                resolution_mode="addr_match",
                original_query=query,
                formatted_address=formatted,
                resolved_site_addr=hit["site_addr"],
                resolved_town=hit["town_name"],
                distance_m=float(hit["dist"] or 0.0),
            )

    return None


@dataclass
class ResolvedParcel:
    """Full resolution result for a user query.

    Carries enough metadata that the UI can render a transparency
    banner ("we snapped your query from X to Y because Z") without a
    second database round-trip.
    """

    loc_id: str
    resolution_mode: str  # 'contains' | 'esmp_anchored' | 'nearest'
    original_query: str
    formatted_address: str | None
    resolved_site_addr: str | None
    resolved_town: str | None
    distance_m: float  # from geocoded point to resolved parcel (centroid)


# In-memory geocode cache — survives for the lifetime of the process.
# Populated from disk on first miss; disk is only written on new API calls.
_MEM_CACHE: dict[str, dict] = {}


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def _geocode(address: str) -> dict:
    """Return the full cached Places entry so callers can inspect
    formatted_address + place types in addition to lat/lon."""
    # 1. Hot in-memory cache — no I/O
    if address in _MEM_CACHE and _MEM_CACHE[address].get("status") == "OK":
        return _MEM_CACHE[address]

    # 2. Disk cache — deserialise once, then populate memory cache
    disk = _load_cache()
    if address in disk and disk[address].get("status") == "OK":
        _MEM_CACHE[address] = disk[address]
        return disk[address]

    # 3. Live API call
    key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        raise ResolveError(f"{address!r} not cached and GOOGLE_PLACES_API_KEY is unset")
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
        disk[address] = {"status": data.get("status"), "raw": data}
        _save_cache(disk)
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
    _MEM_CACHE[address] = entry
    disk[address] = entry
    _save_cache(disk)
    return entry


def resolve_parcel_detailed(
    session: Session,
    address: str,
    project_type: str | None = None,
    nearest_radius_m: float = DEFAULT_NEAREST_RADIUS_M,
    esmp_anchor_radius_m: float = DEFAULT_ESMP_ANCHOR_RADIUS_M,
) -> ResolvedParcel:
    """Resolve an address to a parcel, returning full transparency metadata.

    Resolution order:
      0. address_points table (MassGIS MAD building centroids) — most accurate,
         bypasses geocoding entirely for loaded towns.
      1. contains — geocoded point inside a parcel polygon.
      2. esmp_anchored — substation/transmission near an ESMP project.
      3. nearest — closest parcel within strict radius.

    Raises :class:`ResolveError` when no parcel is within
    ``nearest_radius_m`` of the geocoded point.
    """
    # ---- Step 0: MassGIS address points (building centroid → loc_id) ----
    # Try a quick address-text lookup in our ingested address_points table.
    # We pass None as formatted_address here since we haven't geocoded yet;
    # the parser falls back to the raw query string.
    ap_result = _resolve_via_address_points(session, address, None)
    if ap_result is not None:
        return ap_result

    geo = _geocode(address)
    lat, lon = geo["lat"], geo["lon"]
    formatted = geo.get("formatted_address")
    params = {"lat": lat, "lon": lon}

    # Try address_points again now that we have the Google formatted address
    # (better town name parsing for cases like "Cambridge, MA 02142")
    if formatted and formatted != address:
        ap_result2 = _resolve_via_address_points(session, address, formatted)
        if ap_result2 is not None:
            return ap_result2

    # ---- Step 1: contains (the only mode that "means" exact-match) ----
    contains = (
        session.execute(
            text(
                """
                SELECT loc_id, site_addr, town_name,
                       ST_Distance(
                         geom,
                         ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
                       ) AS dist
                FROM parcels
                WHERE ST_Contains(
                    geom,
                    ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
                )
                LIMIT 1
                """
            ),
            params,
        )
        .mappings()
        .first()
    )
    if contains:
        # If the geocoded point landed in an unnamed parcel (parking lot,
        # ROW, common area — site_addr is null/empty), try to find the
        # nearest named parcel whose address starts with the same street
        # number within 200 m. This recovers the common case where Google
        # Places pins the entrance curb rather than the building centroid.
        if not (contains["site_addr"] or "").strip():
            street_num = _street_number(formatted or address)
            if street_num:
                addr_match = (
                    session.execute(
                        text(
                            """
                            SELECT loc_id, site_addr, town_name,
                                   ST_Distance(
                                     geom,
                                     ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
                                   ) AS dist
                            FROM parcels
                            WHERE site_addr IS NOT NULL AND site_addr <> ''
                              AND site_addr ILIKE :num || ' %'
                              AND ST_DWithin(
                                    geom,
                                    ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986),
                                    200
                                  )
                            ORDER BY geom <->
                                ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
                            LIMIT 1
                            """
                        ),
                        {**params, "num": street_num},
                    )
                    .mappings()
                    .first()
                )
                if addr_match:
                    return ResolvedParcel(
                        loc_id=addr_match["loc_id"],
                        resolution_mode="addr_match",
                        original_query=address,
                        formatted_address=formatted,
                        resolved_site_addr=addr_match["site_addr"],
                        resolved_town=addr_match["town_name"],
                        distance_m=float(addr_match["dist"] or 0.0),
                    )
        return ResolvedParcel(
            loc_id=contains["loc_id"],
            resolution_mode="contains",
            original_query=address,
            formatted_address=formatted,
            resolved_site_addr=contains["site_addr"],
            resolved_town=contains["town_name"],
            distance_m=float(contains["dist"] or 0.0),
        )

    # ---- Step 2: ESMP-anchored (only for substation/transmission) ----
    if project_type in ESMP_ANCHOR_ELIGIBLE_TYPES:
        anchor = (
            session.execute(
                text(
                    """
                    WITH pt AS (
                      SELECT ST_Transform(
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986
                      ) AS g
                    )
                    SELECT p.loc_id, p.site_addr, p.town_name,
                           ST_Distance(p.geom, pt.g) AS dist
                    FROM esmp_projects e, pt, parcels p
                    WHERE ST_DWithin(e.geom, pt.g, :r)
                      AND p.geom = (
                          SELECT pp.geom FROM parcels pp
                          ORDER BY pp.geom <-> e.geom LIMIT 1
                      )
                    ORDER BY e.geom <-> pt.g
                    LIMIT 1
                    """
                ),
                {**params, "r": esmp_anchor_radius_m},
            )
            .mappings()
            .first()
        )
        if anchor:
            return ResolvedParcel(
                loc_id=anchor["loc_id"],
                resolution_mode="esmp_anchored",
                original_query=address,
                formatted_address=formatted,
                resolved_site_addr=anchor["site_addr"],
                resolved_town=anchor["town_name"],
                distance_m=float(anchor["dist"] or 0.0),
            )

    # ---- Step 3: nearest parcel within a strict radius ----
    nearest = (
        session.execute(
            text(
                """
                SELECT loc_id, site_addr, town_name,
                       ST_Distance(
                         geom,
                         ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
                       ) AS dist
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
            {**params, "r": nearest_radius_m},
        )
        .mappings()
        .first()
    )
    if nearest:
        return ResolvedParcel(
            loc_id=nearest["loc_id"],
            resolution_mode="nearest",
            original_query=address,
            formatted_address=formatted,
            resolved_site_addr=nearest["site_addr"],
            resolved_town=nearest["town_name"],
            distance_m=float(nearest["dist"] or 0.0),
        )

    raise ResolveError(
        f"no parcel within {nearest_radius_m:.0f} m of {address!r} "
        f"(geocoded to lat={lat:.4f}, lon={lon:.4f}). "
        f"Try a more specific address — this query may be outside the ingested towns."
    )


def resolve_parcel(
    session: Session,
    address: str,
    project_type: str | None = None,
    fallback_radius_m: float = DEFAULT_NEAREST_RADIUS_M,
    esmp_anchor_radius_m: float = DEFAULT_ESMP_ANCHOR_RADIUS_M,
) -> tuple[str, str]:
    """Backwards-compatible shim — returns ``(loc_id, resolution_mode)``.

    Prefer :func:`resolve_parcel_detailed` in new code so the UI can
    surface the resolution metadata.
    """
    r = resolve_parcel_detailed(
        session,
        address,
        project_type=project_type,
        nearest_radius_m=fallback_radius_m,
        esmp_anchor_radius_m=esmp_anchor_radius_m,
    )
    return r.loc_id, r.resolution_mode
