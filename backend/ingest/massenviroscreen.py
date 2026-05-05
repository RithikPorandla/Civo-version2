"""Ingest MassEnviroScreen cumulative burden polygons — statewide (default) or per-town.

Source: OEJE MassEnviroScreen Cumulative Burden Scoring View (block-group level)
    https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/MassEnviroScreen_Cumulative_Burden_Scoring_View/FeatureServer/0

Run modes
---------
  python -m ingest.massenviroscreen              # all 2604 MA block groups (default)
  python -m ingest.massenviroscreen --town Acton # re-ingest one town's block groups only
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
    vulnerability_score, median_hh_income, attrs, geom
) VALUES (
    :geoid, :ej_designation, :cumulative_score, :pollution_score,
    :vulnerability_score, :median_hh_income, CAST(:attrs AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
)
ON CONFLICT (geoid) DO UPDATE SET
    ej_designation     = EXCLUDED.ej_designation,
    cumulative_score   = EXCLUDED.cumulative_score,
    pollution_score    = EXCLUDED.pollution_score,
    vulnerability_score= EXCLUDED.vulnerability_score,
    median_hh_income   = EXCLUDED.median_hh_income,
    attrs              = EXCLUDED.attrs,
    geom               = EXCLUDED.geom;
"""
)

# MassEnviroScreen ACS income field aliases — the service has used different
# names across tool versions; try all known variants.
# Field name verified against live OEJE service response (2026-05-05).
_INCOME_FIELDS = ("medHHincE", "MedIncome", "MedHHInc", "MedianHHIncome", "MHHI", "Median_HH_Income")


def feature_to_row(feat: dict) -> dict | None:
    g = feat.get("geometry")
    if not g:
        return None
    p = feat.get("properties") or {}
    income_raw = next((p[k] for k in _INCOME_FIELDS if k in p and p[k] is not None), None)
    try:
        median_hh_income = float(income_raw) if income_raw is not None else None
    except (TypeError, ValueError):
        median_hh_income = None
    return {
        "geoid": p.get("GEOID"),
        "ej_designation": p.get("EJ"),
        "cumulative_score": p.get("MassEnviroScore"),
        "pollution_score": p.get("PollutionBurden"),
        "vulnerability_score": p.get("hhburden"),
        "median_hh_income": median_hh_income,
        "attrs": json.dumps(p),
        "geom": json.dumps(g),
    }


def ingest_statewide() -> int:
    """Fetch all MA block groups in a single paginated pass — no spatial filter."""
    total = 0
    params = {"where": "1=1", "outFields": "*", "outSR": 26986}
    batch: list[dict] = []
    with httpx.Client(timeout=300) as client:
        for feat in paged_query(client, URL, params, page_size=500):
            row = feature_to_row(feat)
            if row and row["geoid"]:
                batch.append(row)
            if len(batch) >= 500:
                with engine.begin() as conn:
                    conn.execute(INSERT_SQL, batch)
                total += len(batch)
                print(f"  [mes/statewide] {total} rows upserted")
                batch.clear()
        if batch:
            with engine.begin() as conn:
                conn.execute(INSERT_SQL, batch)
            total += len(batch)
    return total


def ingest_town(town: str) -> int:
    """Re-ingest a single town's block groups (useful for targeted refreshes)."""
    total = 0
    with httpx.Client(timeout=300) as client:
        tg = fetch_town_geometry(client, town)
        params = {"where": "1=1", "outFields": "*"}
        params.update(town_filter_params(tg))
        batch: list[dict] = []
        for feat in paged_query(client, URL, params):
            row = feature_to_row(feat)
            if row and row["geoid"]:
                batch.append(row)
            if len(batch) >= 500:
                with engine.begin() as conn:
                    conn.execute(INSERT_SQL, batch)
                total += len(batch)
                batch.clear()
        if batch:
            with engine.begin() as conn:
                conn.execute(INSERT_SQL, batch)
            total += len(batch)
    print(f"  [{town}/mes] +{total}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest MassEnviroScreen block groups.")
    ap.add_argument("--town", action="append", help="Re-ingest specific town(s) only")
    args = ap.parse_args()
    if args.town:
        grand = sum(ingest_town(t) for t in args.town)
        print(f"Done. {grand} MES rows across {len(args.town)} town(s).")
    else:
        grand = ingest_statewide()
        print(f"Done. {grand} MES block groups statewide.")


if __name__ == "__main__":
    main()
