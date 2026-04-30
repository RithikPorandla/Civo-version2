"""Extract ML features for every parcel and upsert into parcel_ml_features.

Computes ~35 spatial, grid, jurisdiction, neighborhood, and sentiment features
per parcel using PostGIS. Processes parcels town-by-town in batches.

Usage:
    python -m scripts.extract_ml_features [--town Acton] [--workers 4] [--batch 500]
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlalchemy import text

sys.path.insert(0, ".")
from app.db import SessionLocal

DOER_ENCODE = {
    "adopted": 1.0,
    "in_progress": 0.7,
    "not_started": 0.4,
    "unknown": 0.5,
    None: 0.5,
}

# SQL to extract all features for all parcels in a given town.
# Returns one row per parcel. Heavy spatial ops (coverage %) use LATERAL subqueries.
FEATURE_SQL = text("""
WITH parcel_base AS (
    SELECT
        p.loc_id,
        p.town_name,
        p.shape_area                                        AS area_m2,
        ST_Perimeter(p.geom)                                AS perimeter_m,
        CASE WHEN ST_Perimeter(p.geom) > 0
             THEN 4 * PI() * ST_Area(p.geom)
                  / (ST_Perimeter(p.geom) * ST_Perimeter(p.geom))
             ELSE NULL END                                  AS shape_index,
        p.geom
    FROM parcels p
    WHERE p.town_name = :town
      AND p.shape_area >= :min_area
),

-- Constraint flags — use precomputed boolean columns (avoids ST_Intersection cost)
constraint_pcts AS (
    SELECT
        p.loc_id,
        CASE WHEN p.flag_biomap_core    THEN 1.0 ELSE 0.0 END AS pct_biomap_core,
        CASE WHEN p.flag_nhesp_priority THEN 1.0 ELSE 0.0 END AS pct_nhesp_priority,
        0.0                                                    AS pct_nhesp_estimated,
        CASE WHEN p.flag_flood_zone     THEN 1.0 ELSE 0.0 END AS pct_flood_zone,
        CASE WHEN p.flag_wetlands       THEN 1.0 ELSE 0.0 END AS pct_wetlands,
        CASE WHEN p.flag_article97      THEN 1.0 ELSE 0.0 END AS pct_article97,
        CASE WHEN p.flag_prime_farmland THEN 1.0 ELSE 0.0 END AS pct_prime_farmland
    FROM parcels p
    WHERE p.town_name = :town
      AND p.shape_area >= :min_area
),

-- Nearest ESMP project (grid infrastructure proxy)
esmp_proximity AS (
    SELECT DISTINCT ON (pb.loc_id)
        pb.loc_id,
        ST_Distance(pb.geom, e.geom)                        AS dist_to_esmp_m,
        COALESCE(e.mw, 0)                                   AS nearest_esmp_mw
    FROM parcel_base pb
    JOIN esmp_projects e ON ST_DWithin(pb.geom, e.geom, 25000)
    ORDER BY pb.loc_id, ST_Distance(pb.geom, e.geom)
),

-- Nearest HCA point
hca_proximity AS (
    SELECT DISTINCT ON (pb.loc_id)
        pb.loc_id,
        ST_Distance(pb.geom, h.geom)                        AS dist_to_hca_m,
        COALESCE(h.available_mw, 0)                         AS nearest_hca_mw
    FROM parcel_base pb
    JOIN hosting_capacity h ON ST_DWithin(pb.geom, h.geom, 25000)
    ORDER BY pb.loc_id, ST_Distance(pb.geom, h.geom)
),

-- 5km grid neighborhood aggregates
grid_neighborhood AS (
    SELECT
        pb.loc_id,
        COUNT(DISTINCT e.id)                                AS n_esmp_5km,
        COALESCE(SUM(h_agg.available_mw), 0)                AS total_hca_mw_5km
    FROM parcel_base pb
    LEFT JOIN esmp_projects e
        ON ST_DWithin(pb.geom, e.geom, 5000)
    LEFT JOIN LATERAL (
        SELECT available_mw FROM hosting_capacity hh
        WHERE ST_DWithin(pb.geom, hh.geom, 5000)
    ) h_agg ON true
    GROUP BY pb.loc_id
),

-- Approved/denied precedent counts at 1km and 5km
precedent_proximity AS (
    SELECT
        pb.loc_id,
        COUNT(*) FILTER (
            WHERE pr.decision = 'approved' AND ST_DWithin(pb.geom, pr.geom, 1000)
        )                                                    AS approved_1km,
        COUNT(*) FILTER (
            WHERE pr.decision = 'denied' AND ST_DWithin(pb.geom, pr.geom, 1000)
        )                                                    AS denied_1km,
        COUNT(*) FILTER (
            WHERE pr.decision = 'approved' AND ST_DWithin(pb.geom, pr.geom, 5000)
        )                                                    AS approved_5km,
        COUNT(*) FILTER (
            WHERE pr.decision = 'denied' AND ST_DWithin(pb.geom, pr.geom, 5000)
        )                                                    AS denied_5km
    FROM parcel_base pb
    LEFT JOIN precedents pr ON pr.geom IS NOT NULL
        AND ST_DWithin(pb.geom, pr.geom, 5000)
    GROUP BY pb.loc_id
),

-- Average score of nearby scored parcels (same town, 5km radius)
score_neighborhood AS (
    SELECT
        pb.loc_id,
        AVG(sh.total_score)                                 AS avg_neighbor_score_5km,
        COUNT(sh.total_score)                               AS n_scored_neighbors_5km
    FROM parcel_base pb
    LEFT JOIN parcels p2
        ON p2.town_name = :town
       AND p2.loc_id != pb.loc_id
       AND ST_DWithin(pb.geom, p2.geom, 5000)
    LEFT JOIN LATERAL (
        SELECT total_score FROM score_history
        WHERE parcel_loc_id = p2.loc_id
        ORDER BY computed_at DESC LIMIT 1
    ) sh ON true
    GROUP BY pb.loc_id
),

-- Jurisdiction signals
jurisdiction AS (
    SELECT
        pb.loc_id,
        COALESCE(tjr_bess.risk_multiplier, 1.0)             AS risk_multiplier,
        COALESCE(tjr_bess.moratorium_active, false)         AS moratorium_active,
        COALESCE(tjr_bess.concom_approval_rate, NULL)       AS concom_approval_rate,
        COALESCE(tjr_bess.median_permit_days, NULL)         AS median_permit_days,
        COALESCE(tjr_bess.total_precedents, 0)              AS total_precedents,
        (SELECT adoption_status FROM municipal_doer_adoption mda
            JOIN municipalities m ON m.town_id = mda.municipality_id
            WHERE m.town_name = pb.town_name AND mda.project_type = 'bess'
            LIMIT 1)                                        AS doer_bess_raw,
        (SELECT adoption_status FROM municipal_doer_adoption mda
            JOIN municipalities m ON m.town_id = mda.municipality_id
            WHERE m.town_name = pb.town_name AND mda.project_type = 'solar'
            LIMIT 1)                                        AS doer_solar_raw
    FROM parcel_base pb
    LEFT JOIN town_jurisdiction_risk tjr_bess
        ON tjr_bess.town_name = pb.town_name
       AND tjr_bess.project_type = 'bess_standalone'
),

-- Sentiment
sentiment AS (
    SELECT
        pb.loc_id,
        ts_bess.sentiment_score                             AS town_sentiment_bess,
        ts_sol.sentiment_score                              AS town_sentiment_solar
    FROM parcel_base pb
    LEFT JOIN town_sentiment ts_bess
        ON ts_bess.town_name = pb.town_name
       AND ts_bess.project_type = 'bess_standalone'
    LEFT JOIN town_sentiment ts_sol
        ON ts_sol.town_name = pb.town_name
       AND ts_sol.project_type = 'solar_ground_mount'
)

SELECT
    pb.loc_id                                               AS parcel_loc_id,
    pb.area_m2,
    pb.perimeter_m,
    pb.shape_index,
    cp.pct_biomap_core,
    cp.pct_nhesp_priority,
    cp.pct_nhesp_estimated,
    cp.pct_flood_zone,
    cp.pct_wetlands,
    cp.pct_article97,
    cp.pct_prime_farmland,
    ep.dist_to_esmp_m,
    ep.nearest_esmp_mw,
    hp.dist_to_hca_m,
    hp.nearest_hca_mw,
    COALESCE(gn.n_esmp_5km, 0)                             AS n_esmp_5km,
    COALESCE(gn.total_hca_mw_5km, 0)                       AS total_hca_mw_5km,
    COALESCE(pp.approved_1km, 0)                            AS approved_projects_1km,
    COALESCE(pp.denied_1km, 0)                             AS denied_projects_1km,
    COALESCE(pp.approved_5km, 0)                            AS approved_projects_5km,
    COALESCE(pp.denied_5km, 0)                             AS denied_projects_5km,
    sn.avg_neighbor_score_5km,
    COALESCE(sn.n_scored_neighbors_5km, 0)                 AS n_scored_neighbors_5km,
    j.risk_multiplier,
    j.moratorium_active,
    j.concom_approval_rate,
    j.median_permit_days,
    j.total_precedents,
    j.doer_bess_raw,
    j.doer_solar_raw,
    se.town_sentiment_bess,
    se.town_sentiment_solar

FROM parcel_base pb
LEFT JOIN constraint_pcts cp USING (loc_id)
LEFT JOIN esmp_proximity ep USING (loc_id)
LEFT JOIN hca_proximity hp USING (loc_id)
LEFT JOIN grid_neighborhood gn USING (loc_id)
LEFT JOIN precedent_proximity pp USING (loc_id)
LEFT JOIN score_neighborhood sn USING (loc_id)
LEFT JOIN jurisdiction j USING (loc_id)
LEFT JOIN sentiment se USING (loc_id)
""")

UPSERT_SQL = text("""
INSERT INTO parcel_ml_features (
    parcel_loc_id, area_m2, perimeter_m, shape_index,
    pct_biomap_core, pct_nhesp_priority, pct_nhesp_estimated,
    pct_flood_zone, pct_wetlands, pct_article97, pct_prime_farmland,
    dist_to_esmp_m, nearest_esmp_mw, dist_to_hca_m, nearest_hca_mw,
    n_esmp_5km, total_hca_mw_5km,
    approved_projects_1km, denied_projects_1km,
    approved_projects_5km, denied_projects_5km,
    avg_neighbor_score_5km, n_scored_neighbors_5km,
    risk_multiplier, moratorium_active, concom_approval_rate,
    median_permit_days, total_precedents,
    doer_bess_score, doer_solar_score,
    town_sentiment_bess, town_sentiment_solar,
    extracted_at
) VALUES (
    :parcel_loc_id, :area_m2, :perimeter_m, :shape_index,
    :pct_biomap_core, :pct_nhesp_priority, :pct_nhesp_estimated,
    :pct_flood_zone, :pct_wetlands, :pct_article97, :pct_prime_farmland,
    :dist_to_esmp_m, :nearest_esmp_mw, :dist_to_hca_m, :nearest_hca_mw,
    :n_esmp_5km, :total_hca_mw_5km,
    :approved_projects_1km, :denied_projects_1km,
    :approved_projects_5km, :denied_projects_5km,
    :avg_neighbor_score_5km, :n_scored_neighbors_5km,
    :risk_multiplier, :moratorium_active, :concom_approval_rate,
    :median_permit_days, :total_precedents,
    :doer_bess_score, :doer_solar_score,
    :town_sentiment_bess, :town_sentiment_solar,
    :extracted_at
)
ON CONFLICT (parcel_loc_id) DO UPDATE SET
    area_m2                 = EXCLUDED.area_m2,
    perimeter_m             = EXCLUDED.perimeter_m,
    shape_index             = EXCLUDED.shape_index,
    pct_biomap_core         = EXCLUDED.pct_biomap_core,
    pct_nhesp_priority      = EXCLUDED.pct_nhesp_priority,
    pct_nhesp_estimated     = EXCLUDED.pct_nhesp_estimated,
    pct_flood_zone          = EXCLUDED.pct_flood_zone,
    pct_wetlands            = EXCLUDED.pct_wetlands,
    pct_article97           = EXCLUDED.pct_article97,
    pct_prime_farmland      = EXCLUDED.pct_prime_farmland,
    dist_to_esmp_m          = EXCLUDED.dist_to_esmp_m,
    nearest_esmp_mw         = EXCLUDED.nearest_esmp_mw,
    dist_to_hca_m           = EXCLUDED.dist_to_hca_m,
    nearest_hca_mw          = EXCLUDED.nearest_hca_mw,
    n_esmp_5km              = EXCLUDED.n_esmp_5km,
    total_hca_mw_5km        = EXCLUDED.total_hca_mw_5km,
    approved_projects_1km   = EXCLUDED.approved_projects_1km,
    denied_projects_1km     = EXCLUDED.denied_projects_1km,
    approved_projects_5km   = EXCLUDED.approved_projects_5km,
    denied_projects_5km     = EXCLUDED.denied_projects_5km,
    avg_neighbor_score_5km  = EXCLUDED.avg_neighbor_score_5km,
    n_scored_neighbors_5km  = EXCLUDED.n_scored_neighbors_5km,
    risk_multiplier         = EXCLUDED.risk_multiplier,
    moratorium_active       = EXCLUDED.moratorium_active,
    concom_approval_rate    = EXCLUDED.concom_approval_rate,
    median_permit_days      = EXCLUDED.median_permit_days,
    total_precedents        = EXCLUDED.total_precedents,
    doer_bess_score         = EXCLUDED.doer_bess_score,
    doer_solar_score        = EXCLUDED.doer_solar_score,
    town_sentiment_bess     = EXCLUDED.town_sentiment_bess,
    town_sentiment_solar    = EXCLUDED.town_sentiment_solar,
    extracted_at            = EXCLUDED.extracted_at
""")


def _process_town(town_name: str, min_area_m2: float = 8093.7) -> tuple[str, int]:
    with SessionLocal() as session:
        rows = session.execute(
            FEATURE_SQL,
            {"town": town_name, "min_area": min_area_m2},
        ).mappings().all()

        if not rows:
            return town_name, 0

        now = datetime.now(timezone.utc)
        records = []
        for r in rows:
            records.append({
                **dict(r),
                "doer_bess_score": DOER_ENCODE.get(r["doer_bess_raw"], 0.5),
                "doer_solar_score": DOER_ENCODE.get(r["doer_solar_raw"], 0.5),
                "extracted_at": now,
            })

        for rec in records:
            session.execute(UPSERT_SQL, rec)
        session.commit()
        return town_name, len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--town", help="Process a single town")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--min-acres", type=float, default=2.0)
    args = parser.parse_args()

    min_area_m2 = args.min_acres * 4046.856

    with SessionLocal() as session:
        if args.town:
            towns = [args.town]
        else:
            towns = session.execute(
                text("SELECT DISTINCT town_name FROM parcels WHERE town_name IS NOT NULL ORDER BY town_name")
            ).scalars().all()

    print(f"Extracting features for {len(towns)} town(s) with {args.workers} workers ...")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_process_town, t, min_area_m2): t for t in towns}
        total = 0
        for fut in as_completed(futures):
            town, n = fut.result()
            total += n
            print(f"  {town}: {n} parcels")

    print(f"\nDone — {total} rows upserted into parcel_ml_features")


if __name__ == "__main__":
    main()
