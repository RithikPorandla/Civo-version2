"""Ingest MassGIS BioMap Core Habitat + Critical Natural Landscape components
clipped to one or more MA municipalities.

Core:  https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/BioMap_CoreHabitatComponents/FeatureServer
CNL:   https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/BioMap_CriticalNaturalLandscapeComponents/FeatureServer

Idempotency: for each town, delete existing rows whose geometry intersects
the town polygon, then insert. Polygons that span multiple towns may be
re-inserted when a second town is ingested; that's acceptable because the
source geometry is stable within a given BioMap release.
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

CORE_URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "BioMap_CoreHabitatComponents/FeatureServer"
)
CNL_URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "BioMap_CriticalNaturalLandscapeComponents/FeatureServer"
)

# Sub-layer IDs → human label stored in the {core,cnl}_type column.
CORE_LAYERS = {
    1: "Priority Natural Communities",
    2: "Aquatic Core",
    3: "Wetland Core",
    4: "Rare Species Core",
    5: "Forest Core",
    6: "Vernal Pool Core",
}
CNL_LAYERS = {
    1: "Landscape Blocks",
    2: "Aquatic Core Buffer",
    3: "Wetland Core Buffer",
    4: "Tern Foraging Habitat",
    5: "Coastal Adaptation Areas",
}


CORE_INSERT = text(
    """
INSERT INTO habitat_biomap_core (core_type, source_version, attrs, geom)
VALUES (
    :core_type, :source_version, CAST(:attrs AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
);
"""
)
CNL_INSERT = text(
    """
INSERT INTO habitat_biomap_cnl (cnl_type, source_version, attrs, geom)
VALUES (
    :cnl_type, :source_version, CAST(:attrs AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
);
"""
)


def feature_to_row(feat: dict, layer_label: str, kind: str) -> dict | None:
    props = feat.get("properties") or {}
    geom = feat.get("geometry")
    if not geom:
        return None
    key = "core_type" if kind == "core" else "cnl_type"
    return {
        key: layer_label,
        "source_version": "BioMap 2022",
        "attrs": json.dumps(props),
        "geom": json.dumps(geom),
    }


def _delete_existing(conn, kind: str, town_poly_wkt: str) -> int:
    table = "habitat_biomap_core" if kind == "core" else "habitat_biomap_cnl"
    res = conn.execute(
        text(
            f"DELETE FROM {table} "
            f"WHERE ST_Intersects(geom, ST_GeomFromText(:wkt, 26986))"
        ),
        {"wkt": town_poly_wkt},
    )
    return res.rowcount or 0


def _town_wkt(town_geom: dict) -> str:
    # Build a WKT polygon from the Esri-JSON rings (all in 26986).
    parts = []
    for ring in town_geom["rings"]:
        coords = ", ".join(f"{x} {y}" for x, y, *_ in ring)
        parts.append(f"({coords})")
    return "MULTIPOLYGON((" + "),(".join(parts) + "))"


def ingest_kind(town: str, kind: str) -> int:
    layers = CORE_LAYERS if kind == "core" else CNL_LAYERS
    base_url = CORE_URL if kind == "core" else CNL_URL
    insert_sql = CORE_INSERT if kind == "core" else CNL_INSERT

    total = 0
    with httpx.Client() as client, engine.begin() as conn:
        town_geom = fetch_town_geometry(client, town)
        # Single WKT covering all rings (Esri ring order differs per feature
        # but MULTIPOLYGON with one outer ring per row is a safe spatial
        # filter for DELETE).
        wkt = _town_wkt(town_geom)
        n_del = _delete_existing(conn, kind, wkt)
        if n_del:
            print(f"  [{town}/{kind}] deleted {n_del} existing rows")
        for layer_id, label in layers.items():
            url = f"{base_url}/{layer_id}/query"
            params = {"where": "1=1", "outFields": "*"}
            params.update(town_filter_params(town_geom))
            n = 0
            batch: list[dict] = []
            for feat in paged_query(client, url, params):
                row = feature_to_row(feat, label, kind)
                if row:
                    batch.append(row)
                if len(batch) >= 500:
                    conn.execute(insert_sql, batch)
                    n += len(batch)
                    batch.clear()
            if batch:
                conn.execute(insert_sql, batch)
                n += len(batch)
            total += n
            print(f"  [{town}/{kind}] {label}: +{n}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest BioMap Core and CNL for MA towns.")
    ap.add_argument("--town", action="append", help="Town (repeatable). Default: 10 target towns.")
    ap.add_argument(
        "--kind",
        choices=("core", "cnl", "both"),
        default="both",
        help="Which BioMap layer to ingest.",
    )
    args = ap.parse_args()
    towns = args.town or TARGET_TOWNS
    kinds = ["core", "cnl"] if args.kind == "both" else [args.kind]
    grand = 0
    for town in towns:
        for k in kinds:
            grand += ingest_kind(town, k)
    print(f"Done. Upserted {grand} BioMap rows across {len(towns)} town(s).")


if __name__ == "__main__":
    main()
