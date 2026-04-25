"""PostGIS-backed parcel discovery engine.

Translates structured InterpretedQuery filters into parameterized SQL.
All geometry is in EPSG:26986 (MA State Plane, meters); centroids are
transformed to WGS-84 for the frontend.

Performance architecture:
  - When parcels.flags_computed_at IS NOT NULL, constraint flags are read directly
    from pre-computed boolean columns (no LATERAL JOINs → ~50x faster).
  - Critical indexes (migration 0013):
      idx_parcels_town_area          — eliminates parcels seq scan
      idx_score_history_parcel       — eliminates inner-loop score_history seq scan

1 acre = 4046.856 m²  (shape_area is stored in m²)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.query_interpreter import InterpretedQuery
from app.services import ml_scorer

# Module-level caches — set once, never reset.
_jurisdiction_table_exists: bool | None = None
_flags_precomputed: bool | None = None   # True once any parcel has flags_computed_at set


def _check_jurisdiction_table(session: Session) -> bool:
    global _jurisdiction_table_exists
    if _jurisdiction_table_exists:
        return True
    row = session.execute(
        text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'town_jurisdiction_risk'
            LIMIT 1
        """)
    ).fetchone()
    _jurisdiction_table_exists = row is not None
    return _jurisdiction_table_exists


def _check_flags_precomputed(session: Session) -> bool:
    global _flags_precomputed
    if _flags_precomputed:
        return True
    row = session.execute(
        text("SELECT 1 FROM parcels WHERE flags_computed_at IS NOT NULL LIMIT 1")
    ).fetchone()
    _flags_precomputed = row is not None
    return _flags_precomputed


ACRES_TO_M2 = 4046.856
DEFAULT_LIMIT = 50

# Default minimum area — 2 acres is the practical floor for ground-mount solar.
DEFAULT_MIN_AREA_M2 = 2.0 * ACRES_TO_M2

# MA DOR use codes that represent potentially developable land.
# Discovery excludes pure residential by default (101-125 = single/multi-family,
# condos, apartments). This is a key "actual sites" quality filter.
_RESIDENTIAL_USE_PREFIXES = ("101", "102", "103", "104", "105", "106", "107",
                              "108", "109", "111", "112", "113", "114", "115",
                              "116", "117", "118", "119", "120", "121", "122",
                              "123", "124", "125", "1010", "1020", "1040", "1050")

# Maps layer name → (table_name, sql_alias, precomputed_column)
LAYER_TABLE_MAP: dict[str, tuple[str, str, str | None]] = {
    "biomap_core":     ("habitat_biomap_core",    "bmc",   "flag_biomap_core"),
    "biomap_cnl":      ("habitat_biomap_cnl",      "bcnl",  None),
    "nhesp_priority":  ("habitat_nhesp_priority",  "nhesp", "flag_nhesp_priority"),
    "nhesp_estimated": ("habitat_nhesp_estimated", "nhest", None),
    "flood_zone":      ("flood_zones",             "flood", "flag_flood_zone"),
    "wetlands":        ("wetlands",                "wet",   "flag_wetlands"),
    "article97":       ("article97",               "a97",   "flag_article97"),
    "prime_farmland":  ("prime_farmland",          "pfarm", "flag_prime_farmland"),
}

ALWAYS_JOINED_LAYERS = {"biomap_core", "nhesp_priority", "flood_zone", "wetlands", "article97"}


@dataclass
class DiscoveryFilters:
    municipalities: list[str] = field(default_factory=list)
    min_area_m2: float | None = None
    max_area_m2: float | None = None
    exclude_layers: list[str] = field(default_factory=list)
    include_layers: list[str] = field(default_factory=list)
    doer_bess_status: str | None = None
    doer_solar_status: str | None = None
    project_type: str | None = None
    min_score: float | None = None
    sort_by: str = "score_desc"
    limit: int = DEFAULT_LIMIT
    exclude_residential: bool = True   # default: skip 101-125 use codes

    @classmethod
    def from_interpreted(cls, q: InterpretedQuery, limit: int = DEFAULT_LIMIT) -> "DiscoveryFilters":
        munis = q.resolved_municipalities()

        min_acres = q.min_acres
        if min_acres is None and q.project_size_mw is not None:
            if q.project_type in ("bess_standalone", "bess_colocated"):
                min_acres = max(1.0, q.project_size_mw * 0.4)
            elif q.project_type in ("solar_ground_mount", "solar_canopy"):
                min_acres = max(2.0, q.project_size_mw * 1.0)

        # Apply a sensible floor so unfiltered queries don't return tiny residential lots
        if min_acres is None:
            min_acres = 2.0

        return cls(
            municipalities=munis,
            min_area_m2=(min_acres * ACRES_TO_M2) if min_acres else DEFAULT_MIN_AREA_M2,
            max_area_m2=(q.max_acres * ACRES_TO_M2) if q.max_acres else None,
            exclude_layers=[l for l in q.exclude_layers if l in LAYER_TABLE_MAP],
            include_layers=[l for l in q.include_layers if l in LAYER_TABLE_MAP],
            doer_bess_status=q.doer_bess_status,
            doer_solar_status=q.doer_solar_status,
            project_type=q.project_type,
            min_score=q.min_score,
            sort_by=q.sort_by or "score_desc",
            limit=limit,
        )


def run_discovery(
    session: Session,
    filters: DiscoveryFilters,
) -> list[dict[str, Any]]:
    """Execute the PostGIS discovery query and return raw result dicts."""

    use_precomputed = _check_flags_precomputed(session)

    where_parts: list[str] = []
    params: dict[str, Any] = {
        "limit": filters.limit,
        "score_project_type": filters.project_type or "bess_standalone",
    }

    # Municipality filter
    if filters.municipalities:
        placeholders = ", ".join(f":muni_{i}" for i in range(len(filters.municipalities)))
        where_parts.append(f"p.town_name IN ({placeholders})")
        for i, m in enumerate(filters.municipalities):
            params[f"muni_{i}"] = m

    # Size filters — always applied; default 2 acres ensures real developable parcels
    min_area = filters.min_area_m2 if filters.min_area_m2 is not None else DEFAULT_MIN_AREA_M2
    where_parts.append("p.shape_area >= :min_area")
    params["min_area"] = min_area
    if filters.max_area_m2 is not None:
        where_parts.append("p.shape_area <= :max_area")
        params["max_area"] = filters.max_area_m2

    # Land use filter — exclude residential subdivisions by default
    if filters.exclude_residential:
        res_conditions = " AND ".join(
            f"p.use_code NOT LIKE '{prefix}%'" for prefix in _RESIDENTIAL_USE_PREFIXES
        )
        where_parts.append(f"(p.use_code IS NULL OR ({res_conditions}))")

    # Score filter
    if filters.min_score is not None:
        where_parts.append("(sh.total_score IS NULL OR sh.total_score >= :min_score)")
        params["min_score"] = filters.min_score

    # DOER filters
    if filters.doer_bess_status:
        where_parts.append("""
            EXISTS (
                SELECT 1 FROM municipalities m_bess
                JOIN municipal_doer_adoption mda_bess
                  ON mda_bess.municipality_id = m_bess.town_id
                WHERE m_bess.town_name = p.town_name
                  AND mda_bess.project_type = 'bess'
                  AND mda_bess.adoption_status = :doer_bess_status
            )
        """)
        params["doer_bess_status"] = filters.doer_bess_status

    if filters.doer_solar_status:
        where_parts.append("""
            EXISTS (
                SELECT 1 FROM municipalities m_sol
                JOIN municipal_doer_adoption mda_sol
                  ON mda_sol.municipality_id = m_sol.town_id
                WHERE m_sol.town_name = p.town_name
                  AND mda_sol.project_type = 'solar'
                  AND mda_sol.adoption_status = :doer_solar_status
            )
        """)
        params["doer_solar_status"] = filters.doer_solar_status

    # ── Constraint layer handling ─────────────────────────────────────────────
    # When flags are pre-computed, read boolean columns directly (fast path).
    # When not yet computed, fall back to LATERAL JOINs (slow path, correct).

    if use_precomputed:
        # Fast path: SELECT reads pre-computed columns; no LATERAL JOINs needed.
        constraint_select = """
            COALESCE(p.flag_biomap_core,    false) AS in_biomap_core,
            COALESCE(p.flag_nhesp_priority, false) AS in_nhesp_priority,
            COALESCE(p.flag_flood_zone,     false) AS in_flood_zone,
            COALESCE(p.flag_wetlands,       false) AS in_wetlands,
            COALESCE(p.flag_article97,      false) AS in_article97"""
        always_lateral_sql = ""

        # exclude/include still work via pre-computed columns
        for layer in filters.exclude_layers:
            col = LAYER_TABLE_MAP[layer][2]
            if col:
                where_parts.append(f"(p.{col} IS NULL OR p.{col} = false)")
            else:
                # Layer has no precomputed column — fall through to LATERAL
                always_lateral_sql += f"""
        LEFT JOIN LATERAL (
            SELECT id FROM {LAYER_TABLE_MAP[layer][0]}
            WHERE  ST_Intersects(geom, p.geom) LIMIT 1
        ) {LAYER_TABLE_MAP[layer][1]} ON true"""
                where_parts.append(f"{LAYER_TABLE_MAP[layer][1]}.id IS NULL")

        for layer in filters.include_layers:
            col = LAYER_TABLE_MAP[layer][2]
            if col:
                where_parts.append(f"p.{col} = true")
            else:
                always_lateral_sql += f"""
        LEFT JOIN LATERAL (
            SELECT id FROM {LAYER_TABLE_MAP[layer][0]}
            WHERE  ST_Intersects(geom, p.geom) LIMIT 1
        ) {LAYER_TABLE_MAP[layer][1]} ON true"""
                where_parts.append(f"{LAYER_TABLE_MAP[layer][1]}.id IS NOT NULL")

        extra_lateral_sql = always_lateral_sql

    else:
        # Slow path: original LATERAL JOIN approach
        constraint_select = """
            (bmc.id  IS NOT NULL) AS in_biomap_core,
            (nhesp.id IS NOT NULL) AS in_nhesp_priority,
            (flood.id IS NOT NULL) AS in_flood_zone,
            (wet.id  IS NOT NULL) AS in_wetlands,
            (a97.id  IS NOT NULL) AS in_article97"""

        extra_layers = (set(filters.exclude_layers) | set(filters.include_layers)) - ALWAYS_JOINED_LAYERS
        extra_lateral_sql = "\n".join(
            f"""        LEFT JOIN LATERAL (
            SELECT id FROM {LAYER_TABLE_MAP[layer][0]}
            WHERE  ST_Intersects(geom, p.geom) LIMIT 1
        ) {LAYER_TABLE_MAP[layer][1]} ON true"""
            for layer in extra_layers
            if layer in LAYER_TABLE_MAP
        )

        for layer in filters.exclude_layers:
            alias = LAYER_TABLE_MAP[layer][1]
            where_parts.append(f"{alias}.id IS NULL")
        for layer in filters.include_layers:
            alias = LAYER_TABLE_MAP[layer][1]
            where_parts.append(f"{alias}.id IS NOT NULL")

    # ── Always-joined LATERAL for constraint flags (slow path only) ───────────
    always_lateral = "" if use_precomputed else """
        LEFT JOIN LATERAL (
            SELECT id FROM habitat_biomap_core
            WHERE  ST_Intersects(geom, p.geom) LIMIT 1
        ) bmc ON true
        LEFT JOIN LATERAL (
            SELECT id FROM habitat_nhesp_priority
            WHERE  ST_Intersects(geom, p.geom) LIMIT 1
        ) nhesp ON true
        LEFT JOIN LATERAL (
            SELECT id FROM flood_zones
            WHERE  ST_Intersects(geom, p.geom) LIMIT 1
        ) flood ON true
        LEFT JOIN LATERAL (
            SELECT id FROM wetlands
            WHERE  ST_Intersects(geom, p.geom) LIMIT 1
        ) wet ON true
        LEFT JOIN LATERAL (
            SELECT id FROM article97
            WHERE  ST_Intersects(geom, p.geom) LIMIT 1
        ) a97 ON true"""

    # ── Jurisdiction risk ─────────────────────────────────────────────────────
    has_jurisdiction_table = _check_jurisdiction_table(session)
    if has_jurisdiction_table and filters.project_type:
        params["jurisdiction_project_type"] = filters.project_type
        jurisdiction_join = """
        LEFT JOIN town_jurisdiction_risk tjr
            ON tjr.town_name    = p.town_name
           AND tjr.project_type = :jurisdiction_project_type"""
        jurisdiction_score = "sh.total_score * COALESCE(tjr.risk_multiplier, 1.0)"
        jurisdiction_select = """
            COALESCE(tjr.moratorium_active, false)  AS moratorium_active,
            tjr.doer_status                         AS doer_status,
            COALESCE(tjr.risk_multiplier, 1.0)      AS risk_multiplier"""
    else:
        jurisdiction_join = ""
        jurisdiction_score = "sh.total_score"
        jurisdiction_select = """
            false   AS moratorium_active,
            NULL    AS doer_status,
            1.0     AS risk_multiplier"""

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sort_sql = {
        "score_desc": f"{jurisdiction_score} DESC NULLS LAST, p.shape_area DESC NULLS LAST",
        "area_desc":  f"p.shape_area DESC NULLS LAST, {jurisdiction_score} DESC NULLS LAST",
        "distance_asc": f"{jurisdiction_score} DESC NULLS LAST",
    }.get(filters.sort_by, f"{jurisdiction_score} DESC NULLS LAST, p.shape_area DESC NULLS LAST")

    sql = text(f"""
        SELECT
            p.loc_id                                        AS parcel_id,
            p.site_addr,
            p.town_name,
            p.use_code,
            ROUND((p.shape_area / 4046.856)::numeric, 2)   AS lot_size_acres,
            ST_Y(ST_Transform(ST_Centroid(p.geom), 4326))::float AS lat,
            ST_X(ST_Transform(ST_Centroid(p.geom), 4326))::float AS lon,
            sh.total_score,
            sh.bucket,
            sh.report ->> 'primary_constraint'              AS primary_constraint,
            {constraint_select},
            {jurisdiction_select}
        FROM parcels p
        LEFT JOIN LATERAL (
            SELECT total_score, bucket, report
            FROM   score_history
            WHERE  parcel_loc_id = p.loc_id
              AND  report->>'project_type' = :score_project_type
            ORDER  BY computed_at DESC
            LIMIT  1
        ) sh ON true
        {always_lateral}
        {extra_lateral_sql}
        {jurisdiction_join}
        {where_sql}
        ORDER BY {sort_sql}
        LIMIT :limit
    """)

    rows = session.execute(sql, params).mappings().all()
    results = [dict(r) for r in rows]

    # ML re-ranking
    parcel_ids = [r["parcel_id"] for r in results]
    if parcel_ids and ml_scorer.model_available(filters.project_type):
        id_placeholders = ", ".join(f":pid_{i}" for i in range(len(parcel_ids)))
        feat_params = {f"pid_{i}": pid for i, pid in enumerate(parcel_ids)}
        feat_rows = session.execute(
            text(f"SELECT * FROM parcel_ml_features WHERE parcel_loc_id IN ({id_placeholders})"),
            feat_params,
        ).mappings().all()
        feat_map = {r["parcel_loc_id"]: dict(r) for r in feat_rows}
        results = ml_scorer.blend_scores(results, feat_map, filters.project_type)
        results.sort(key=lambda r: r.get("blended_score") or 0, reverse=True)
    else:
        for r in results:
            r["ml_score"] = None
            r["blended_score"] = None

    return results
