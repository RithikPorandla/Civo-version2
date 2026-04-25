"""Ingest MassGIS Protected & Recreational OpenSpace polygons (parks,
Article 97 lands, state forests, APRs, local conservation land) clipped
to target municipalities.

Persists into the existing ``article97`` table. The table name is a
historical artifact — it originally held only Article 97 constitutional
open space, but that subset was too narrow (Chris's user feedback:
"parks nearby aren't showing up"). The Protected & Recreational
OpenSpace dataset is the right source: it covers every park and
protected parcel MassGIS tracks, including Article 97.

Source (MassGIS Data Hub · Protected and Recreational OpenSpace):
  https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/OpenSpace/FeatureServer/0

Idempotent per town: DELETE rows whose geometry intersects the town
polygon, then INSERT fresh.
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

OPEN_SPACE_URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "openspace/FeatureServer/0"
)


INSERT_SQL = text(
    """
    INSERT INTO article97 (site_name, owner_type, owner_name, attrs, geom)
    VALUES (
        :site_name, :owner_type, :owner_name, CAST(:attrs AS jsonb),
        ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
    )
    """
)


def _delete_existing(conn, town_wkt: str) -> int:
    res = conn.execute(
        text(
            "DELETE FROM article97 WHERE ST_Intersects(geom, ST_GeomFromText(:wkt, 26986))"
        ),
        {"wkt": town_wkt},
    )
    return res.rowcount or 0


def _town_wkt(town_geom: dict) -> str:
    parts = []
    for ring in town_geom["rings"]:
        coords = ", ".join(f"{x} {y}" for x, y, *_ in ring)
        parts.append(f"({coords})")
    return "MULTIPOLYGON((" + "),(".join(parts) + "))"


def feature_to_row(feat: dict) -> dict | None:
    props = feat.get("properties") or {}
    geom = feat.get("geometry")
    if not geom:
        return None
    # MassGIS OpenSpace schema: SITE_NAME, OWNER_TYPE (e.g. STATE/MUNICIPAL/
    # NONPROFIT/FEDERAL/PRIVATE), OWNER_NAME. We store the raw record under
    # `attrs` so downstream queries can filter by OpenSpace-specific fields
    # (PUB_ACCESS, LEV_PROT, etc.) without schema migrations.
    return {
        "site_name": props.get("SITE_NAME") or props.get("site_name"),
        "owner_type": props.get("OWNER_TYPE") or props.get("owner_type"),
        "owner_name": props.get("OWNER_NAME") or props.get("owner_name"),
        "attrs": json.dumps(props),
        "geom": json.dumps(geom),
    }


def ingest_town(town: str) -> int:
    total = 0
    with httpx.Client() as client, engine.begin() as conn:
        town_geom = fetch_town_geometry(client, town)
        wkt = _town_wkt(town_geom)
        n_del = _delete_existing(conn, wkt)
        if n_del:
            print(f"  [{town}] deleted {n_del} existing rows")

        url = f"{OPEN_SPACE_URL}/query"
        params = {"where": "1=1", "outFields": "*"}
        params.update(town_filter_params(town_geom))

        batch: list[dict] = []
        for feat in paged_query(client, url, params):
            row = feature_to_row(feat)
            if row:
                batch.append(row)
            if len(batch) >= 500:
                conn.execute(INSERT_SQL, batch)
                total += len(batch)
                batch.clear()
        if batch:
            conn.execute(INSERT_SQL, batch)
            total += len(batch)
        print(f"  [{town}] +{total} open-space polygons")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Ingest MassGIS Protected & Recreational OpenSpace for MA towns."
    )
    ap.add_argument(
        "--town",
        action="append",
        help="Town (repeatable). Default: every TARGET_TOWN.",
    )
    args = ap.parse_args()
    towns = args.town or TARGET_TOWNS
    grand = 0
    for town in towns:
        grand += ingest_town(town)
    print(f"Done. Ingested {grand} open-space polygons across {len(towns)} town(s).")


if __name__ == "__main__":
    main()
