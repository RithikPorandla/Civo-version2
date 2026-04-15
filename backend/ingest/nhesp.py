"""Ingest NHESP Priority + Estimated Habitats clipped to MA town(s).

Priority:  https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/NHESP_Priority_Habitats/MapServer/0
Estimated: https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/NHESP_Estimated_Habitats/MapServer/0
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
from ingest._common import (  # noqa: E402
    TARGET_TOWNS,
    fetch_town_geometry,
    paged_query,
    town_filter_params,
)

PRIORITY_URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "NHESP_Priority_Habitats/MapServer/0/query"
)
ESTIMATED_URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "NHESP_Estimated_Habitats/MapServer/0/query"
)


PRIORITY_INSERT = text(
    """
INSERT INTO habitat_nhesp_priority (priority_id, source_version, attrs, geom)
VALUES (
    :priority_id, :source_version, CAST(:attrs AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
);
"""
)
ESTIMATED_INSERT = text(
    """
INSERT INTO habitat_nhesp_estimated (estimated_id, source_version, attrs, geom)
VALUES (
    :estimated_id, :source_version, CAST(:attrs AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
);
"""
)


def priority_row(feat: dict) -> dict | None:
    g = feat.get("geometry")
    if not g:
        return None
    p = feat.get("properties") or {}
    return {
        "priority_id": str(p.get("PRIHAB_ID") or p.get("OBJECTID") or ""),
        "source_version": p.get("HAB_DATE") or "NHESP",
        "attrs": json.dumps(p),
        "geom": json.dumps(g),
    }


def estimated_row(feat: dict) -> dict | None:
    g = feat.get("geometry")
    if not g:
        return None
    p = feat.get("properties") or {}
    return {
        "estimated_id": str(p.get("ESTHAB_ID") or p.get("OBJECTID") or ""),
        "source_version": p.get("HAB_DATE") or "NHESP",
        "attrs": json.dumps(p),
        "geom": json.dumps(g),
    }


def _delete_existing(conn, table: str, town_wkt: str) -> int:
    res = conn.execute(
        text(f"DELETE FROM {table} WHERE ST_Intersects(geom, ST_GeomFromText(:wkt, 26986))"),
        {"wkt": town_wkt},
    )
    return res.rowcount or 0


def _town_wkt(town_geom: dict) -> str:
    parts = []
    for ring in town_geom["rings"]:
        coords = ", ".join(f"{x} {y}" for x, y, *_ in ring)
        parts.append(f"({coords})")
    return "MULTIPOLYGON((" + "),(".join(parts) + "))"


def ingest(town: str, kind: str) -> int:
    url = PRIORITY_URL if kind == "priority" else ESTIMATED_URL
    table = "habitat_nhesp_priority" if kind == "priority" else "habitat_nhesp_estimated"
    insert_sql = PRIORITY_INSERT if kind == "priority" else ESTIMATED_INSERT
    to_row = priority_row if kind == "priority" else estimated_row
    total = 0
    with httpx.Client() as client, engine.begin() as conn:
        town_geom = fetch_town_geometry(client, town)
        wkt = _town_wkt(town_geom)
        n_del = _delete_existing(conn, table, wkt)
        if n_del:
            print(f"  [{town}/{kind}] deleted {n_del} existing rows")
        params = {"where": "1=1", "outFields": "*"}
        params.update(town_filter_params(town_geom))
        batch: list[dict] = []
        for feat in paged_query(client, url, params):
            r = to_row(feat)
            if r:
                batch.append(r)
            if len(batch) >= 500:
                conn.execute(insert_sql, batch)
                total += len(batch)
                batch.clear()
        if batch:
            conn.execute(insert_sql, batch)
            total += len(batch)
    print(f"  [{town}/{kind}] +{total}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest NHESP habitats for MA towns.")
    ap.add_argument("--town", action="append")
    ap.add_argument("--kind", choices=("priority", "estimated", "both"), default="both")
    args = ap.parse_args()
    towns = args.town or TARGET_TOWNS
    kinds = ["priority", "estimated"] if args.kind == "both" else [args.kind]
    grand = 0
    for t in towns:
        for k in kinds:
            grand += ingest(t, k)
    print(f"Done. {grand} NHESP rows across {len(towns)} town(s).")


if __name__ == "__main__":
    main()
