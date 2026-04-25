"""Candidate site discovery around an ESMP project anchor.

Context (from Chris 2026-04-17): the core workflow is "pick an ESMP
substation, find 2-3 parcels in close proximity that would make good
BESS / solar sites, approach the landowners." This module is the
automated first pass — it scans parcels inside a configurable radius
of an anchor point, filters out hard-ineligible land, scores the
survivors through the production scoring engine, and returns the top
N ranked by total score.

The caller supplies either:
  - anchor_project_id (an esmp_projects.id — we pull coords from it), or
  - anchor_lat + anchor_lon directly.

Performance profile: the scoring engine runs ~7 PostGIS queries per
parcel. With ``score_pool_size=15`` we spend ~1.5-3s in scoring; the
remaining ``limit`` are returned ranked by pool score. For anything
bigger, an offline batch job would be the right approach — this one's
tuned for a consultant doing interactive screening.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.scoring.engine import score_site


# Per-project-type default size windows (acres). Chris works mainly in BESS
# + ground-mount solar; other types have reasonable defaults but aren't the
# intended headline use.
DEFAULT_SIZE_WINDOWS_ACRES: dict[str, tuple[float, float]] = {
    "solar_ground_mount": (3.0, 80.0),
    "solar_canopy": (1.0, 20.0),
    "bess_standalone": (0.5, 10.0),
    "bess_colocated": (3.0, 80.0),  # attached to solar footprint
    "substation": (1.0, 15.0),
    "transmission": (0.1, 1000.0),  # linear; effectively no cap
    "ev_charging": (0.1, 3.0),
    "solar_rooftop": (0.1, 1000.0),  # doesn't really apply
}

# Target "ideal" acreage for proximity scoring in the composite ranker. Close
# to these values = perfect fit.
IDEAL_SIZE_ACRES: dict[str, float] = {
    "solar_ground_mount": 20.0,
    "solar_canopy": 5.0,
    "bess_standalone": 3.0,
    "bess_colocated": 25.0,
    "substation": 5.0,
    "ev_charging": 1.0,
}


@dataclass
class CandidateSite:
    """One ranked candidate + the metadata needed to surface it in the UI."""

    parcel_id: str
    site_addr: str | None
    town_name: str | None
    lot_size_acres: float | None
    distance_to_anchor_m: float
    use_code: str | None
    total_val: int | None
    # Populated for parcels that entered the scoring pool; None for tail.
    total_score: float | None = None
    bucket: str | None = None
    primary_constraint: str | None = None
    # Disqualifiers the pre-filter caught. Empty when the parcel passed.
    hard_ineligibilities: list[str] = field(default_factory=list)
    # Composite used for sorting (higher = better). Combines score, size fit,
    # and distance to anchor.
    composite_rank: float = 0.0


@dataclass
class CandidateSearchResult:
    anchor: dict[str, Any]
    project_type: str
    radius_m: float
    min_acres: float
    max_acres: float
    config_version: str
    pre_filter_count: int
    scored_count: int
    candidates: list[CandidateSite]


# ---------------------------------------------------------------------------
# Anchor resolution
# ---------------------------------------------------------------------------
def _resolve_anchor(
    session: Session,
    anchor_project_id: int | None,
    anchor_lat: float | None,
    anchor_lon: float | None,
) -> dict[str, Any]:
    if anchor_project_id is not None:
        row = (
            session.execute(
                text(
                    """
                    SELECT id, project_name, project_type, mw, municipality,
                           source_filing, siting_status,
                           ST_X(ST_Transform(geom, 4326)) AS lon,
                           ST_Y(ST_Transform(geom, 4326)) AS lat
                    FROM esmp_projects
                    WHERE id = :pid
                    """
                ),
                {"pid": anchor_project_id},
            )
            .mappings()
            .first()
        )
        if not row:
            raise ValueError(f"esmp_projects.id={anchor_project_id} not found")
        return {
            "kind": "esmp_project",
            "id": row["id"],
            "project_name": row["project_name"],
            "project_type": row["project_type"],
            "mw": float(row["mw"]) if row["mw"] is not None else None,
            "municipality": row["municipality"],
            "source_filing": row["source_filing"],
            "siting_status": row["siting_status"],
            "lat": row["lat"],
            "lon": row["lon"],
        }

    if anchor_lat is None or anchor_lon is None:
        raise ValueError("must supply anchor_project_id or both anchor_lat and anchor_lon")
    return {
        "kind": "point",
        "lat": anchor_lat,
        "lon": anchor_lon,
    }


# ---------------------------------------------------------------------------
# Parcel pre-filter
# ---------------------------------------------------------------------------
# MassGIS L3 parcels store lot_size DIRECTLY in acres — not square feet.
# (Verified against sample rows; lot_size values cluster in the 0–130 range
# which only makes sense as acres.)


def _pre_filter_parcels(
    session: Session,
    anchor_lat: float,
    anchor_lon: float,
    radius_m: float,
    min_acres: float,
    max_acres: float,
    pool_size: int,
) -> list[CandidateSite]:
    """Spatial + size + ineligibility pre-filter in one SQL round-trip.

    Returns parcels sorted by distance to anchor, limited to pool_size.
    Hard-ineligible parcels (>50% inside BioMap Core or NHESP Priority)
    are excluded outright. Wetland/flood overlap is kept as metadata for
    the UI but doesn't disqualify.
    """
    rows = (
        session.execute(
            text(
                """
                WITH anchor_pt AS (
                  SELECT ST_Transform(
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986
                  ) AS g
                ),
                in_radius AS (
                  SELECT p.loc_id, p.site_addr, p.town_name, p.use_code,
                         p.total_val, p.lot_size,
                         ST_Distance(p.geom, anchor_pt.g) AS dist
                  FROM parcels p, anchor_pt
                  WHERE ST_DWithin(p.geom, anchor_pt.g, :r)
                    AND p.lot_size BETWEEN :min_acres AND :max_acres
                ),
                flagged AS (
                  SELECT ir.*,
                    EXISTS (
                      SELECT 1 FROM habitat_biomap_core h
                      WHERE ST_Intersects(h.geom, (SELECT geom FROM parcels WHERE loc_id = ir.loc_id))
                        AND ST_Area(ST_Intersection(h.geom, (SELECT geom FROM parcels WHERE loc_id = ir.loc_id)))
                            > 0.5 * ST_Area((SELECT geom FROM parcels WHERE loc_id = ir.loc_id))
                    ) AS biomap_core_ineligible,
                    EXISTS (
                      SELECT 1 FROM habitat_nhesp_priority h
                      WHERE ST_Intersects(h.geom, (SELECT geom FROM parcels WHERE loc_id = ir.loc_id))
                        AND ST_Area(ST_Intersection(h.geom, (SELECT geom FROM parcels WHERE loc_id = ir.loc_id)))
                            > 0.5 * ST_Area((SELECT geom FROM parcels WHERE loc_id = ir.loc_id))
                    ) AS nhesp_priority_ineligible,
                    EXISTS (
                      SELECT 1 FROM article97 a
                      WHERE ST_Intersects(a.geom, (SELECT geom FROM parcels WHERE loc_id = ir.loc_id))
                    ) AS article97_overlap
                  FROM in_radius ir
                )
                SELECT * FROM flagged
                WHERE NOT biomap_core_ineligible
                  AND NOT nhesp_priority_ineligible
                  AND NOT article97_overlap
                ORDER BY dist
                LIMIT :pool
                """
            ),
            {
                "lat": anchor_lat,
                "lon": anchor_lon,
                "r": radius_m,
                "min_acres": min_acres,
                "max_acres": max_acres,
                "pool": pool_size,
            },
        )
        .mappings()
        .all()
    )

    out: list[CandidateSite] = []
    for r in rows:
        out.append(
            CandidateSite(
                parcel_id=r["loc_id"],
                site_addr=r["site_addr"],
                town_name=r["town_name"],
                lot_size_acres=float(r["lot_size"]) if r["lot_size"] is not None else None,
                distance_to_anchor_m=float(r["dist"] or 0),
                use_code=r["use_code"],
                total_val=r["total_val"],
            )
        )
    return out


# ---------------------------------------------------------------------------
# Composite ranker
# ---------------------------------------------------------------------------
def _composite_rank(
    site: CandidateSite, project_type: str, anchor_radius_m: float
) -> float:
    """Blend score + size fit + distance into a single sort key.

    We keep total_score as the dominant signal (0-100) and add small
    bonuses/penalties from size fit and anchor proximity so that ties get
    broken by the signals Chris explicitly named — "close to the ESMP
    project" and "right size for the intended use."
    """
    if site.total_score is None:
        # Unscored tail — rank by proximity only, below any scored site.
        return -1 + (1.0 - site.distance_to_anchor_m / anchor_radius_m) * 0.5

    score = site.total_score  # 0..100

    # Proximity bonus: up to +10 for being at the anchor, 0 at the edge.
    prox = max(0.0, 1.0 - site.distance_to_anchor_m / anchor_radius_m) * 10.0

    # Size fit bonus: 1.0 when exactly at ideal, 0.0 at endpoints. Tanh-smoothed.
    ideal = IDEAL_SIZE_ACRES.get(project_type)
    if ideal and site.lot_size_acres:
        deviation = abs(site.lot_size_acres - ideal) / ideal
        fit = max(0.0, 1.0 - deviation * 0.5) * 5.0
    else:
        fit = 0.0

    return score + prox + fit


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def find_candidate_sites(
    session: Session,
    project_type: str,
    anchor_project_id: int | None = None,
    anchor_lat: float | None = None,
    anchor_lon: float | None = None,
    radius_m: float = 5000.0,
    min_acres: float | None = None,
    max_acres: float | None = None,
    score_pool_size: int = 15,
    limit: int = 10,
    config_version: str = "ma-eea-2026-v1",
) -> CandidateSearchResult:
    """Return up to ``limit`` candidate parcels ranked by composite score.

    ``score_pool_size`` is the number of parcels we run through the full
    scoring engine; the rest get returned unscored (ranked by distance to
    anchor). This bounds the latency of a single search.
    """
    anchor = _resolve_anchor(session, anchor_project_id, anchor_lat, anchor_lon)

    # Resolve size window.
    default_min, default_max = DEFAULT_SIZE_WINDOWS_ACRES.get(
        project_type, (0.1, 1000.0)
    )
    min_a = float(min_acres) if min_acres is not None else default_min
    max_a = float(max_acres) if max_acres is not None else default_max

    # Pre-filter.
    pool = _pre_filter_parcels(
        session,
        anchor_lat=anchor["lat"],
        anchor_lon=anchor["lon"],
        radius_m=radius_m,
        min_acres=min_a,
        max_acres=max_a,
        pool_size=max(score_pool_size, limit),
    )

    pre_filter_count = len(pool)

    # Full-score the first `score_pool_size` sites.
    to_score = pool[:score_pool_size]
    scored = 0
    for site in to_score:
        try:
            report = score_site(
                session,
                parcel_id=site.parcel_id,
                project_type=project_type,
                config_version=config_version,
            )
        except Exception:
            # Scoring can fail for parcels with missing data; leave unscored
            # rather than killing the whole search.
            continue
        site.total_score = round(report.total_score, 1)
        site.bucket = report.bucket
        site.primary_constraint = report.primary_constraint
        scored += 1

    # Rank and slice.
    for s in pool:
        s.composite_rank = _composite_rank(s, project_type, radius_m)
    pool.sort(key=lambda s: s.composite_rank, reverse=True)
    top = pool[:limit]

    return CandidateSearchResult(
        anchor=anchor,
        project_type=project_type,
        radius_m=radius_m,
        min_acres=min_a,
        max_acres=max_a,
        config_version=config_version,
        pre_filter_count=pre_filter_count,
        scored_count=scored,
        candidates=top,
    )
