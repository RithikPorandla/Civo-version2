"""PostGIS-backed parcel discovery engine.

Translates structured InterpretedQuery filters into parameterized SQL.
All geometry is in EPSG:26986 (MA State Plane, meters); centroids are
transformed to WGS-84 for the frontend.

Ranking strategy
----------------
Results are ordered by ``COALESCE(score_history.total_score, proxy_score)
× risk_multiplier``.  When a parcel has been scored before, the real
225 CMR 29 score takes precedence.  When it hasn't, the proxy score
stands in — a fast SQL-inline approximation that uses the same signals
(grid proximity, land-use category, parcel size, constraint flags) weighted
to mirror 225 CMR 29 criterion priorities.  This means every result is
ranked meaningfully even for towns that have never been pre-scored.

Hard pre-filters (always applied, not user-configurable)
---------------------------------------------------------
1. ESMP grid proximity ≤ 20 km — parcels beyond this have no realistic
   interconnection path; every result cites an actual ESMP project.
2. BioMap Core + NHESP Priority excluded — 225 CMR 29.06 hard ineligibility;
   no point surfacing sites that cannot receive a simplified permit.
3. Non-developable use codes (parks, ROW, airports) excluded.

Performance
-----------
- ESMP LATERAL join is always used; table is ~100 rows, so cost is negligible.
- When parcels.flags_computed_at IS NOT NULL, constraint flags are read from
  pre-computed boolean columns (~50× faster than LATERAL JOINs).
- Critical indexes (migration 0013):
    idx_parcels_town_area      — eliminates parcel seq scan
    idx_score_history_parcel   — eliminates inner-loop score_history seq scan
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.query_interpreter import InterpretedQuery
from app.services import ml_scorer

# ---------------------------------------------------------------------------
# Module-level caches — set once per process lifetime.
# ---------------------------------------------------------------------------
_jurisdiction_table_exists: bool | None = None
_flags_precomputed: bool | None = None


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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ACRES_TO_M2 = 4046.856
DEFAULT_LIMIT = 50

# Practical floor for ground-mount solar; BESS can be smaller.
DEFAULT_MIN_AREA_M2 = 2.0 * ACRES_TO_M2

# Parcels beyond this distance from the nearest ESMP project have no
# realistic interconnection path at reasonable capital cost.
DEFAULT_MAX_GRID_DIST_M = 20_000.0  # 20 km

# MA DOR residential use codes — excluded from discovery by default.
_RESIDENTIAL_USE_PREFIXES = (
    "101", "102", "103", "104", "105", "106", "107",
    "108", "109", "111", "112", "113", "114", "115",
    "116", "117", "118", "119", "120", "121", "122",
    "123", "124", "125",
    "1010", "1020", "1040", "1050",
)

# Use codes that are inherently undevelopable for clean energy, regardless
# of project type.  These are excluded unconditionally.
_NON_DEVELOPABLE_USE_CODES = frozenset([
    "742",  # Municipal park / playground (Article 97 protected)
    "743",  # Private recreation (golf course, sports club)
    "744",  # Conservation / agricultural reserve
    "965",  # Airport / airfield (FAA constraints)
    "995",  # Right-of-way / road
])

# Maps layer name → (table_name, sql_alias, precomputed_column_or_None)
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


# ---------------------------------------------------------------------------
# Proxy score
# ---------------------------------------------------------------------------
def _proxy_score_sql(use_precomputed: bool) -> str:
    """SQL expression for the inline proxy suitability score (0–100 scale).

    Used when score_history has no entry for a parcel.  Mirrors 225 CMR 29.00
    criterion priorities using signals already available in the discovery query:
      - Grid proximity   0–40 pts  (criterion 1: Grid Alignment, weight 20%)
      - Land-use type    0–25 pts  (industrial > commercial > institutional > ag)
      - Parcel size      0–20 pts  (log scale; large parcels score higher)
      - Clean flags      0–15 pts  (no flood + no wetlands + no article97)

    ``nearest_esmp.dist_m`` comes from the always-present ESMP LATERAL join.
    Flag expressions differ between fast (pre-computed columns) and slow
    (LATERAL join aliases) paths — do not unify them.
    """
    if use_precomputed:
        clean_flags_sql = """
            CASE
                WHEN NOT COALESCE(p.flag_flood_zone, false)
                 AND NOT COALESCE(p.flag_wetlands,   false)
                 AND NOT COALESCE(p.flag_article97,  false) THEN 15
                WHEN NOT COALESCE(p.flag_flood_zone, false)
                 AND NOT COALESCE(p.flag_wetlands,   false)  THEN 10
                ELSE 4
            END"""
    else:
        clean_flags_sql = """
            CASE
                WHEN flood.id IS NULL AND wet.id IS NULL AND a97.id IS NULL THEN 15
                WHEN flood.id IS NULL AND wet.id IS NULL                    THEN 10
                ELSE 4
            END"""

    return f"""
        GREATEST(0.0,
            -- Grid proximity: 40 pts at 0 m → 0 pts at 20 km
            GREATEST(0.0, 40.0 - (nearest_esmp.dist_m / 500.0))
            -- Land-use type (MA DOR use codes)
            + CASE
                WHEN LEFT(p.use_code, 2) = ANY(ARRAY['40','41','42','43']) THEN 25
                WHEN LEFT(p.use_code, 2) = ANY(ARRAY['13','14','15','32','33','34','35']) THEN 20
                WHEN p.use_code = ANY(ARRAY['903','904','910','911','325']) THEN 15
                WHEN LEFT(p.use_code, 2) = ANY(ARRAY['90','91','92','93','94','95']) THEN 12
                WHEN LEFT(p.use_code, 2) = ANY(ARRAY['01','02','03']) THEN 8
                ELSE 5
              END
            -- Parcel size (log scale so 500-acre parcels don't dominate)
            + LEAST(20.0, LN(GREATEST(p.shape_area / 4046.856, 1.0) + 1.0) * 7.5)
            -- Constraint cleanliness
            + {clean_flags_sql}
        )"""


# ---------------------------------------------------------------------------
# DiscoveryFilters dataclass
# ---------------------------------------------------------------------------
@dataclass
class DiscoveryFilters:
    municipalities: list[str] = field(default_factory=list)
    min_area_m2: float | None = None
    max_area_m2: float | None = None
    max_grid_dist_m: float = DEFAULT_MAX_GRID_DIST_M
    exclude_layers: list[str] = field(default_factory=list)
    include_layers: list[str] = field(default_factory=list)
    doer_bess_status: str | None = None
    doer_solar_status: str | None = None
    project_type: str | None = None
    min_score: float | None = None
    sort_by: str = "score_desc"
    limit: int = DEFAULT_LIMIT
    exclude_residential: bool = True

    @classmethod
    def from_interpreted(cls, q: InterpretedQuery, limit: int = DEFAULT_LIMIT) -> "DiscoveryFilters":
        munis = q.resolved_municipalities()

        min_acres = q.min_acres
        if min_acres is None and q.project_size_mw is not None:
            if q.project_type in ("bess_standalone", "bess_colocated"):
                min_acres = max(1.0, q.project_size_mw * 0.4)
            elif q.project_type in ("solar_ground_mount", "solar_canopy"):
                min_acres = max(2.0, q.project_size_mw * 1.0)

        if min_acres is None:
            min_acres = 2.0

        return cls(
            municipalities=munis,
            min_area_m2=(min_acres * ACRES_TO_M2) if min_acres else DEFAULT_MIN_AREA_M2,
            max_area_m2=(q.max_acres * ACRES_TO_M2) if q.max_acres else None,
            max_grid_dist_m=DEFAULT_MAX_GRID_DIST_M,
            exclude_layers=[l for l in q.exclude_layers if l in LAYER_TABLE_MAP],
            include_layers=[l for l in q.include_layers if l in LAYER_TABLE_MAP],
            doer_bess_status=q.doer_bess_status,
            doer_solar_status=q.doer_solar_status,
            project_type=q.project_type,
            min_score=q.min_score,
            sort_by=q.sort_by or "score_desc",
            limit=limit,
        )


# ---------------------------------------------------------------------------
# Core discovery query
# ---------------------------------------------------------------------------
def run_discovery(
    session: Session,
    filters: DiscoveryFilters,
) -> list[dict[str, Any]]:
    """Execute the PostGIS discovery query and return raw result dicts.

    Every result is guaranteed to be within ``max_grid_dist_m`` of an ESMP
    project and outside the 225 CMR 29.06 hard-ineligibility layers.
    """
    use_precomputed = _check_flags_precomputed(session)

    where_parts: list[str] = []
    params: dict[str, Any] = {
        "limit": filters.limit,
        "max_grid_dist_m": filters.max_grid_dist_m,
        "score_project_type": filters.project_type or "bess_standalone",
    }

    # ── Municipality filter ───────────────────────────────────────────────
    if filters.municipalities:
        placeholders = ", ".join(f":muni_{i}" for i in range(len(filters.municipalities)))
        where_parts.append(f"p.town_name IN ({placeholders})")
        for i, m in enumerate(filters.municipalities):
            params[f"muni_{i}"] = m

    # ── Size filter ───────────────────────────────────────────────────────
    min_area = filters.min_area_m2 if filters.min_area_m2 is not None else DEFAULT_MIN_AREA_M2
    where_parts.append("p.shape_area >= :min_area")
    params["min_area"] = min_area
    if filters.max_area_m2 is not None:
        where_parts.append("p.shape_area <= :max_area")
        params["max_area"] = filters.max_area_m2

    # ── Grid proximity (hard filter — cites ESMP as source) ───────────────
    # nearest_esmp.dist_m comes from the always-present ESMP LATERAL join.
    where_parts.append("nearest_esmp.dist_m <= :max_grid_dist_m")

    # ── Land-use exclusions ───────────────────────────────────────────────
    # Residential
    if filters.exclude_residential:
        res_conditions = " AND ".join(
            f"p.use_code NOT LIKE '{prefix}%'" for prefix in _RESIDENTIAL_USE_PREFIXES
        )
        where_parts.append(f"(p.use_code IS NULL OR ({res_conditions}))")

    # Parks, ROW, airports — always excluded regardless of project type
    if _NON_DEVELOPABLE_USE_CODES:
        nd_list = ", ".join(f"'{c}'" for c in sorted(_NON_DEVELOPABLE_USE_CODES))
        where_parts.append(f"(p.use_code IS NULL OR p.use_code NOT IN ({nd_list}))")

    # ── Score filter ──────────────────────────────────────────────────────
    if filters.min_score is not None:
        where_parts.append("(sh.total_score IS NULL OR sh.total_score >= :min_score)")
        params["min_score"] = filters.min_score

    # ── DOER bylaw adoption filters ───────────────────────────────────────
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

    # ── Constraint layer handling ─────────────────────────────────────────
    # BioMap Core and NHESP Priority are excluded by default — they are
    # 225 CMR 29.06 hard ineligibility triggers.  The user can override
    # this by adding them to include_layers (e.g. for research queries).

    if use_precomputed:
        constraint_select = """
            COALESCE(p.flag_biomap_core,    false) AS in_biomap_core,
            COALESCE(p.flag_nhesp_priority, false) AS in_nhesp_priority,
            COALESCE(p.flag_flood_zone,     false) AS in_flood_zone,
            COALESCE(p.flag_wetlands,       false) AS in_wetlands,
            COALESCE(p.flag_article97,      false) AS in_article97"""
        extra_lateral_sql = ""

        # Default ineligibility exclusions (fast path)
        if "biomap_core" not in filters.include_layers:
            where_parts.append("NOT COALESCE(p.flag_biomap_core, false)")
        if "nhesp_priority" not in filters.include_layers:
            where_parts.append("NOT COALESCE(p.flag_nhesp_priority, false)")

        # User-requested layer filters
        for layer in filters.exclude_layers:
            col = LAYER_TABLE_MAP[layer][2]
            if col:
                where_parts.append(f"(p.{col} IS NULL OR p.{col} = false)")
            else:
                extra_lateral_sql += f"""
        LEFT JOIN LATERAL (
            SELECT id FROM {LAYER_TABLE_MAP[layer][0]}
            WHERE ST_Intersects(geom, p.geom) LIMIT 1
        ) {LAYER_TABLE_MAP[layer][1]} ON true"""
                where_parts.append(f"{LAYER_TABLE_MAP[layer][1]}.id IS NULL")

        for layer in filters.include_layers:
            col = LAYER_TABLE_MAP[layer][2]
            if col:
                where_parts.append(f"p.{col} = true")
            else:
                extra_lateral_sql += f"""
        LEFT JOIN LATERAL (
            SELECT id FROM {LAYER_TABLE_MAP[layer][0]}
            WHERE ST_Intersects(geom, p.geom) LIMIT 1
        ) {LAYER_TABLE_MAP[layer][1]} ON true"""
                where_parts.append(f"{LAYER_TABLE_MAP[layer][1]}.id IS NOT NULL")

        always_lateral_sql = ""

    else:
        # Slow path: always-joined LATERAL for constraint flags
        constraint_select = """
            (bmc.id  IS NOT NULL) AS in_biomap_core,
            (nhesp.id IS NOT NULL) AS in_nhesp_priority,
            (flood.id IS NOT NULL) AS in_flood_zone,
            (wet.id  IS NOT NULL) AS in_wetlands,
            (a97.id  IS NOT NULL) AS in_article97"""

        always_lateral_sql = """
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

        # Default ineligibility exclusions (slow path)
        if "biomap_core" not in filters.include_layers:
            where_parts.append("bmc.id IS NULL")
        if "nhesp_priority" not in filters.include_layers:
            where_parts.append("nhesp.id IS NULL")

        extra_layers = (
            (set(filters.exclude_layers) | set(filters.include_layers)) - ALWAYS_JOINED_LAYERS
        )
        extra_lateral_sql = "\n".join(
            f"""        LEFT JOIN LATERAL (
            SELECT id FROM {LAYER_TABLE_MAP[layer][0]}
            WHERE  ST_Intersects(geom, p.geom) LIMIT 1
        ) {LAYER_TABLE_MAP[layer][1]} ON true"""
            for layer in extra_layers
            if layer in LAYER_TABLE_MAP
        )

        for layer in filters.exclude_layers:
            where_parts.append(f"{LAYER_TABLE_MAP[layer][1]}.id IS NULL")
        for layer in filters.include_layers:
            where_parts.append(f"{LAYER_TABLE_MAP[layer][1]}.id IS NOT NULL")

    # ── Jurisdiction risk ─────────────────────────────────────────────────
    has_jurisdiction_table = _check_jurisdiction_table(session)
    if has_jurisdiction_table and filters.project_type:
        params["jurisdiction_project_type"] = filters.project_type
        jurisdiction_join = """
        LEFT JOIN town_jurisdiction_risk tjr
            ON tjr.town_name    = p.town_name
           AND tjr.project_type = :jurisdiction_project_type"""
        risk_multiplier_expr = "COALESCE(tjr.risk_multiplier, 1.0)"
        jurisdiction_select = """
            COALESCE(tjr.moratorium_active, false)  AS moratorium_active,
            tjr.doer_status                         AS doer_status,
            COALESCE(tjr.risk_multiplier, 1.0)      AS risk_multiplier"""
    else:
        jurisdiction_join = ""
        risk_multiplier_expr = "1.0"
        jurisdiction_select = """
            false  AS moratorium_active,
            NULL   AS doer_status,
            1.0    AS risk_multiplier"""

    # ── Proxy score and effective rank ────────────────────────────────────
    proxy_sql = _proxy_score_sql(use_precomputed)
    effective_score_sql = (
        f"COALESCE(sh.total_score, {proxy_sql}) * {risk_multiplier_expr}"
    )

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sort_sql = {
        "score_desc":   f"{effective_score_sql} DESC NULLS LAST, p.shape_area DESC NULLS LAST",
        "area_desc":    f"p.shape_area DESC NULLS LAST, {effective_score_sql} DESC NULLS LAST",
        "distance_asc": f"nearest_esmp.dist_m ASC NULLS LAST, {effective_score_sql} DESC NULLS LAST",
    }.get(filters.sort_by, f"{effective_score_sql} DESC NULLS LAST, p.shape_area DESC NULLS LAST")

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
            {jurisdiction_select},
            ROUND(nearest_esmp.dist_m::numeric, 0)          AS nearest_esmp_m,
            ROUND(({proxy_sql})::numeric, 1)                AS proxy_score,
            ROUND(({effective_score_sql})::numeric, 1)      AS effective_score
        FROM parcels p
        -- ESMP proximity — always joined; ESMP is ~100 rows so cost is negligible.
        -- Provides the grid alignment signal and the 20 km hard filter.
        CROSS JOIN LATERAL (
            SELECT ST_Distance(p.geom, e.geom) AS dist_m
            FROM   esmp_projects e
            ORDER  BY p.geom <-> e.geom
            LIMIT  1
        ) nearest_esmp
        LEFT JOIN LATERAL (
            SELECT total_score, bucket, report
            FROM   score_history
            WHERE  parcel_loc_id = p.loc_id
              AND  report->>'project_type' = :score_project_type
            ORDER  BY computed_at DESC
            LIMIT  1
        ) sh ON true
        {always_lateral_sql}
        {extra_lateral_sql}
        {jurisdiction_join}
        {where_sql}
        ORDER BY {sort_sql}
        LIMIT :limit
    """)

    rows = session.execute(sql, params).mappings().all()
    results = [dict(r) for r in rows]

    # ── ML re-ranking (optional — currently disabled, _ML_WEIGHT = 0.0) ──
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
        # Use effective_score (real or proxy) as the display score.
        for r in results:
            r["ml_score"] = None
            r["blended_score"] = r.get("effective_score")

    return results
