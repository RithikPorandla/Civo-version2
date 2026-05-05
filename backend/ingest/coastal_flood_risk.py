"""Ingest MA Coastal Flood Risk Model (MC-FRM) inundation polygons.

Source: EOEEA ResilientMA Map Viewer — six services covering three time
horizons (2030 / 2050 / 2070) at two Annual Exceedance Probabilities
(1% ≈ 100-year event, 0.1% ≈ 1000-year event).

Each service is small (42–111 polygons statewide) so all are fetched in a
single paginated pass without a spatial filter. The ingest uses DELETE-before-
INSERT per (scenario, aep) pair so individual layers can be refreshed
independently.

Usage:
    python -m ingest.coastal_flood_risk           # all 6 layers
    python -m ingest.coastal_flood_risk --scenario 2050 --aep 1pct
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
from ingest._common import paged_query  # noqa: E402

# ── Service registry ────────────────────────────────────────────────────────
# Key: (scenario, aep)
# URL: FeatureServer query endpoint
_SERVICES: dict[tuple[str, str], str] = {
    ("2030", "1pct"): (
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/ArcGIS/rest/services/"
        "MA_Coast_Flood_Risk_Model_1pct_Annual_Exceedance_Probability/FeatureServer/2/query"
    ),
    ("2050", "1pct"): (
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/ArcGIS/rest/services/"
        "MA_Coast_Flood_Risk_Model_1pct_Annual_Exceedance_Probability/FeatureServer/1/query"
    ),
    ("2070", "1pct"): (
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/"
        "MA_2070_1Perc_v11/FeatureServer/0/query"
    ),
    ("2030", "0.1pct"): (
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/"
        "MA_2030_Pt1Perc/FeatureServer/0/query"
    ),
    ("2050", "0.1pct"): (
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/"
        "MA_2050_Pt1Perc/FeatureServer/0/query"
    ),
    ("2070", "0.1pct"): (
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/"
        "MA_2070_Pt1Perc/FeatureServer/0/query"
    ),
}

INSERT_SQL = text(
    """
INSERT INTO coastal_flood_risk (scenario, aep, gridcode, attrs, geom)
VALUES (
    :scenario, :aep, :gridcode, CAST(:attrs AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
)
"""
)


def _feature_to_row(feat: dict, scenario: str, aep: str) -> dict | None:
    g = feat.get("geometry")
    if not g:
        return None
    p = feat.get("properties") or {}
    return {
        "scenario": scenario,
        "aep": aep,
        "gridcode": p.get("gridcode") or p.get("GRIDCODE"),
        "attrs": json.dumps(p),
        "geom": json.dumps(g),
    }


def ingest_layer(scenario: str, aep: str) -> int:
    url = _SERVICES[(scenario, aep)]
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": 26986,
    }
    total = 0
    with httpx.Client(timeout=300) as client, engine.begin() as conn:
        # Clear existing rows for this scenario/AEP before re-inserting.
        deleted = conn.execute(
            text("DELETE FROM coastal_flood_risk WHERE scenario=:s AND aep=:a"),
            {"s": scenario, "a": aep},
        ).rowcount
        if deleted:
            print(f"  [{scenario}/{aep}] cleared {deleted} existing rows")

        batch: list[dict] = []
        for feat in paged_query(client, url, params, page_size=500):
            row = _feature_to_row(feat, scenario, aep)
            if row:
                batch.append(row)
            if len(batch) >= 200:
                conn.execute(INSERT_SQL, batch)
                total += len(batch)
                batch.clear()
        if batch:
            conn.execute(INSERT_SQL, batch)
            total += len(batch)

    print(f"  [{scenario}/{aep}] +{total} rows")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest MC-FRM coastal flood risk polygons.")
    ap.add_argument("--scenario", choices=["2030", "2050", "2070"],
                    help="Ingest a single scenario only")
    ap.add_argument("--aep", choices=["1pct", "0.1pct"],
                    help="Ingest a single AEP only")
    args = ap.parse_args()

    targets = [
        (s, a) for (s, a) in _SERVICES
        if (args.scenario is None or s == args.scenario)
        and (args.aep is None or a == args.aep)
    ]
    if not targets:
        ap.error("No matching layers for the given --scenario / --aep combination.")

    grand = 0
    for scenario, aep in sorted(targets):
        grand += ingest_layer(scenario, aep)

    print(f"Done. {grand} total rows across {len(targets)} layer(s).")


if __name__ == "__main__":
    main()
