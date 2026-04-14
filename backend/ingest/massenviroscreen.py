"""Ingest MassEnviroScreen cumulative burden polygons clipped to MA town(s).

Source: OEJE MassEnviroScreen Cumulative Burden Scoring View (block-group level)
    https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/MassEnviroScreen_Cumulative_Burden_Scoring_View/FeatureServer/0
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
    "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/"
    "MassEnviroScreen_Cumulative_Burden_Scoring_View/FeatureServer/0/query"
)


INSERT_SQL = text(
    """
INSERT INTO massenviroscreen (
    geoid, ej_designation, cumulative_score, pollution_score,
    vulnerability_score, attrs, geom
) VALUES (
    :geoid, :ej_designation, :cumulative_score, :pollution_score,
    :vulnerability_score, CAST(:attrs AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
)
ON CONFLICT (geoid) DO UPDATE SET
    ej_designation     = EXCLUDED.ej_designation,
    cumulative_score   = EXCLUDED.cumulative_score,
    pollution_score    = EXCLUDED.pollution_score,
    vulnerability_score= EXCLUDED.vulnerability_score,
    attrs              = EXCLUDED.attrs,
    geom               = EXCLUDED.geom;
"""
)


def feature_to_row(feat: dict) -> dict | None:
    g = feat.get("geometry")
    if not g:
        return None
    p = feat.get("properties") or {}
    return {
        "geoid": p.get("GEOID"),
        "ej_designation": p.get("EJ"),
        "cumulative_score": p.get("MassEnviroScore"),
        "pollution_score": p.get("PollutionBurden"),
        "vulnerability_score": p.get("hhburden"),
        "attrs": json.dumps(p),
        "geom": json.dumps(g),
    }


def ingest_town(town: str) -> int:
    total = 0
    with httpx.Client() as client, engine.begin() as conn:
        tg = fetch_town_geometry(client, town)
        params = {"where": "1=1", "outFields": "*"}
        params.update(town_filter_params(tg))
        batch: list[dict] = []
        for feat in paged_query(client, URL, params):
            r = feature_to_row(feat)
            if r and r["geoid"]:
                batch.append(r)
            if len(batch) >= 500:
                conn.execute(INSERT_SQL, batch)
                total += len(batch)
                batch.clear()
        if batch:
            conn.execute(INSERT_SQL, batch)
            total += len(batch)
    print(f"  [{town}/mes] +{total}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest MassEnviroScreen for MA towns.")
    ap.add_argument("--town", action="append")
    args = ap.parse_args()
    towns = args.town or TARGET_TOWNS
    grand = sum(ingest_town(t) for t in towns)
    print(f"Done. {grand} MES rows across {len(towns)} town(s).")


if __name__ == "__main__":
    main()
