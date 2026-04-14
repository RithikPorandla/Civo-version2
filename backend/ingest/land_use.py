"""Ingest MassGIS 2016 Land Cover / Land Use polygons for MA town(s).

Source:
    https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/LandCoverLandUse2016/FeatureServer/0

The service exposes a native ``TOWN_ID`` attribute, so we filter by town
with a where-clause (no spatial geometry filter needed). Idempotent via
DELETE-by-town-id then insert.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import engine  # noqa: E402
from ingest._common import TARGET_TOWNS, _request_with_retry, resolve_town_id  # noqa: E402

URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "LandCoverLandUse2016/FeatureServer/0/query"
)
PAGE_SIZE = 2000

# Only ingest cover codes the scoring engine actually consumes. The full
# statewide layer is >2M polygons of raster-segmented land cover; keeping
# just the classes we need keeps the DB small enough for a 16GB M1.
#   2  Impervious                (built environment / brownfield potential)
#   5  Developed Open Space      (built environment)
#   9  Deciduous Forest          (carbon storage)
#  10  Evergreen Forest          (carbon storage)
#  13  Palustrine Forested Wetland (carbon storage + wetland cross-check)
SCORING_COVERCODES = (2, 5, 9, 10, 13)
MIN_AREA_SQM = 500  # drop raster fragments smaller than this (~22m x 22m)

INSERT_SQL = text(
    """
INSERT INTO land_use (
    town_id, covercode, covername, usegencode, usegenname, use_code,
    poly_type, fy, shape_area, attrs, geom
) VALUES (
    :town_id, :covercode, :covername, :usegencode, :usegenname, :use_code,
    :poly_type, :fy, :shape_area, CAST(:attrs AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
);
"""
)


def feature_to_row(feat: dict) -> dict | None:
    g = feat.get("geometry")
    if not g:
        return None
    p = feat.get("properties") or {}
    return {
        "town_id": p.get("TOWN_ID"),
        "covercode": p.get("COVERCODE"),
        "covername": p.get("COVERNAME"),
        "usegencode": p.get("USEGENCODE"),
        "usegenname": p.get("USEGENNAME"),
        "use_code": p.get("USE_CODE"),
        "poly_type": p.get("POLY_TYPE"),
        "fy": p.get("FY"),
        "shape_area": p.get("Shape__Area"),
        "attrs": json.dumps(p),
        "geom": json.dumps(g),
    }


def _fetch_page(client: httpx.Client, town_id: int, offset: int) -> dict:
    covers = ",".join(str(c) for c in SCORING_COVERCODES)
    where = (
        f"TOWN_ID={town_id} AND COVERCODE IN ({covers}) "
        f"AND Shape__Area >= {MIN_AREA_SQM}"
    )
    params = {
        "where": where,
        "outFields": "*",
        "outSR": 26986,
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "returnGeometry": "true",
    }
    r = _request_with_retry(client, "GET", URL, params=params, timeout=180)
    return r.json()


def ingest_town(town: str) -> int:
    """Ingest filtered land-use polygons for a single town.

    Commits each 2000-row page in its own transaction so a mid-run failure
    doesn't roll back megabytes of in-flight geometry.
    """
    town_id = resolve_town_id(town)
    total = 0
    with httpx.Client() as client:
        with engine.begin() as conn:
            n_del = conn.execute(
                text("DELETE FROM land_use WHERE town_id = :t"),
                {"t": town_id},
            ).rowcount or 0
            if n_del:
                print(f"  [{town}/land_use] deleted {n_del}")
        offset = 0
        while True:
            page = _fetch_page(client, town_id, offset)
            feats = page.get("features") or []
            if not feats:
                break
            rows = [r for r in (feature_to_row(f) for f in feats) if r]
            if rows:
                with engine.begin() as conn:
                    conn.execute(INSERT_SQL, rows)
            total += len(rows)
            print(f"  [{town}/land_use] offset={offset}: +{len(rows)} (total={total})")
            exceeded = page.get("exceededTransferLimit") or len(feats) == PAGE_SIZE
            if not exceeded:
                break
            offset += PAGE_SIZE
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest MassGIS 2016 Land Cover / Land Use.")
    ap.add_argument("--town", action="append")
    args = ap.parse_args()
    towns = args.town or TARGET_TOWNS
    grand = sum(ingest_town(t) for t in towns)
    print(f"Done. {grand} land-use rows across {len(towns)} town(s).")


if __name__ == "__main__":
    main()
