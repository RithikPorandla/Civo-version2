"""Pull MassGIS L3 Property Tax Parcels for one MA town into Postgres.

Usage:
    python ingest/l3_parcels.py --town Acton

Source:
    MassGIS "Massachusetts Property Tax Parcels" hosted feature layer
    https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/Massachusetts_Property_Tax_Parcels/FeatureServer/0

Notes:
    - The service exposes TOWN_ID (integer); extend TOWN_IDS for new towns.
    - Geometry is returned in EPSG:26986 (MA State Plane, meters).
    - maxRecordCount on this service is 2000; we page with resultOffset.
    - Idempotent: INSERT ... ON CONFLICT (loc_id) DO UPDATE.
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

FEATURE_URL = (
    "https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/"
    "Massachusetts_Property_Tax_Parcels/FeatureServer/0/query"
)
PAGE_SIZE = 2000

from ingest._common import TARGET_TOWNS, _request_with_retry, resolve_town_id  # noqa: E402


def fetch_page(client: httpx.Client, town_id: int, offset: int) -> dict:
    params = {
        "where": f"TOWN_ID={town_id}",
        "outFields": "*",
        "outSR": 26986,
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "returnGeometry": "true",
    }
    r = _request_with_retry(client, "GET", FEATURE_URL, params=params, timeout=120)
    return r.json()


UPSERT_SQL = text(
    """
INSERT INTO parcels (
    loc_id, map_par_id, prop_id, town_id, town_name, poly_type,
    site_addr, city, zip, owner1, use_code, lot_size, total_val, fy,
    shape_area, raw, geom
) VALUES (
    :loc_id, :map_par_id, :prop_id, :town_id, :town_name, :poly_type,
    :site_addr, :city, :zip, :owner1, :use_code, :lot_size,
    :total_val, :fy, :shape_area, CAST(:raw AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
)
ON CONFLICT (loc_id) DO UPDATE SET
    map_par_id = EXCLUDED.map_par_id,
    prop_id    = EXCLUDED.prop_id,
    town_id    = EXCLUDED.town_id,
    town_name  = EXCLUDED.town_name,
    poly_type  = EXCLUDED.poly_type,
    site_addr  = EXCLUDED.site_addr,
    city       = EXCLUDED.city,
    zip        = EXCLUDED.zip,
    owner1     = EXCLUDED.owner1,
    use_code   = EXCLUDED.use_code,
    lot_size   = EXCLUDED.lot_size,
    total_val  = EXCLUDED.total_val,
    fy         = EXCLUDED.fy,
    shape_area = EXCLUDED.shape_area,
    raw        = EXCLUDED.raw,
    geom       = EXCLUDED.geom,
    ingested_at = now();
"""
)


def feature_to_row(feat: dict, town_name: str) -> dict | None:
    props = feat.get("properties") or {}
    geom = feat.get("geometry")
    loc_id = props.get("LOC_ID")
    if not loc_id or not geom:
        return None
    return {
        "loc_id": loc_id,
        "map_par_id": props.get("MAP_PAR_ID"),
        "prop_id": props.get("PROP_ID"),
        "town_id": props.get("TOWN_ID"),
        "town_name": town_name,
        "poly_type": props.get("POLY_TYPE"),
        "site_addr": props.get("SITE_ADDR"),
        "city": props.get("CITY"),
        "zip": props.get("ZIP"),
        "owner1": props.get("OWNER1"),
        "use_code": props.get("USE_CODE"),
        "lot_size": props.get("LOT_SIZE"),
        "total_val": props.get("TOTAL_VAL"),
        "fy": props.get("FY"),
        "shape_area": props.get("Shape__Area"),
        "raw": json.dumps(props),
        "geom": json.dumps(geom),
    }


def ingest_town(town: str) -> int:
    town_id = resolve_town_id(town)
    total = 0
    offset = 0
    with httpx.Client() as client, engine.begin() as conn:
        while True:
            page = fetch_page(client, town_id, offset)
            feats = page.get("features") or []
            if not feats:
                break
            rows = [r for r in (feature_to_row(f, town) for f in feats) if r]
            if rows:
                conn.execute(UPSERT_SQL, rows)
            total += len(rows)
            print(f"  [{town}] page offset={offset}: +{len(rows)} (total={total})")
            exceeded = page.get("exceededTransferLimit") or len(feats) == PAGE_SIZE
            if not exceeded:
                break
            offset += PAGE_SIZE
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest MassGIS L3 parcels for MA towns.")
    ap.add_argument(
        "--town",
        action="append",
        help="Town name (repeatable). Default: 10 target towns.",
    )
    args = ap.parse_args()
    towns = args.town or TARGET_TOWNS
    grand = 0
    for t in towns:
        n = ingest_town(t)
        grand += n
    print(f"Done. Upserted {grand} parcels across {len(towns)} town(s).")


if __name__ == "__main__":
    main()
