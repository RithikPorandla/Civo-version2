"""Ingest MassGIS Prime Farmland Soils clipped to MA town(s).

Source: Top 20 Soils — Prime Farmland Soils (Feature Service, EPSG:26986)
    https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/Soils_PrimeFarmland/FeatureServer/0
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

URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "Soils_PrimeFarmland/FeatureServer/0/query"
)

INSERT_SQL = text(
    """
INSERT INTO prime_farmland (
    farmland_class, musym, muname, attrs, geom
) VALUES (
    :farmland_class, :musym, :muname, CAST(:attrs AS jsonb),
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
        "farmland_class": p.get("FARMLNDCL"),
        "musym": p.get("MUSYM"),
        "muname": p.get("MUNAME"),
        "attrs": json.dumps(p),
        "geom": json.dumps(g),
    }


def _town_wkt(tg: dict) -> str:
    parts = []
    for ring in tg["rings"]:
        coords = ", ".join(f"{x} {y}" for x, y, *_ in ring)
        parts.append(f"({coords})")
    return "MULTIPOLYGON((" + "),(".join(parts) + "))"


def ingest_town(town: str) -> int:
    total = 0
    with httpx.Client() as client, engine.begin() as conn:
        tg = fetch_town_geometry(client, town)
        wkt = _town_wkt(tg)
        n_del = conn.execute(
            text(
                "DELETE FROM prime_farmland "
                "WHERE ST_Intersects(geom, ST_GeomFromText(:wkt, 26986))"
            ),
            {"wkt": wkt},
        ).rowcount or 0
        if n_del:
            print(f"  [{town}/farmland] deleted {n_del}")
        params = {"where": "1=1", "outFields": "*"}
        params.update(town_filter_params(tg))
        batch: list[dict] = []
        for feat in paged_query(client, URL, params):
            r = feature_to_row(feat)
            if r:
                batch.append(r)
            if len(batch) >= 500:
                conn.execute(INSERT_SQL, batch)
                total += len(batch)
                batch.clear()
        if batch:
            conn.execute(INSERT_SQL, batch)
            total += len(batch)
    print(f"  [{town}/farmland] +{total}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Prime Farmland Soils for MA towns.")
    ap.add_argument("--town", action="append")
    args = ap.parse_args()
    towns = args.town or TARGET_TOWNS
    grand = sum(ingest_town(t) for t in towns)
    print(f"Done. {grand} prime-farmland rows across {len(towns)} town(s).")


if __name__ == "__main__":
    main()
