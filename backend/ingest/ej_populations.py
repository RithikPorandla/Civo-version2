"""Ingest MA EJ Population 2020 (Nov 2022 update) block groups.

Source: OEJE / MassGIS — EJ_2020_updated_Nov2022_allBGs FeatureServer
  https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/
  EJ_2020_updated_Nov2022_allBGs/FeatureServer/0

Loads all 5,121 MA census block groups with the official EJ designation and
criteria used in 225 CMR 29.09 (DOER), 310 CMR 7.72, and MEPA review.

EJ_CRITERIA codes:
  I   = Income (BG MHHI ≤ 65% of MA MHHI)
  M   = Minority (≥ 40% non-white / Hispanic)
  E   = Language Isolation (≥ 25% HH with limited English)
  IM  = Income + Minority
  IE  = Income + Language Isolation
  ME  = Minority + Language Isolation
  IME = Income + Minority + Language Isolation

Usage
-----
    cd v2/backend
    python -m ingest.ej_populations          # full statewide run (~5 121 BGs)
    python -m ingest.ej_populations --count  # print row count and exit
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

URL = (
    "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/"
    "EJ_2020_updated_Nov2022_allBGs/FeatureServer/0/query"
)

PAGE_SIZE = 500
RETRY_MAX = 4
RETRY_DELAY = 5

UPSERT = text("""
    INSERT INTO ej_populations
        (geoid, geo_area_name, municipality, ej, ej_criteria, ej_crit_desc,
         pct_minority, bg_mhhi, bg_mhhi_pct_ma, lim_eng_pct,
         muni_mhhi, muni_mhhi_pct_ma, total_pop, total_hh, geom)
    VALUES
        (:geoid, :geo_area_name, :municipality, :ej, :ej_criteria, :ej_crit_desc,
         :pct_minority, :bg_mhhi, :bg_mhhi_pct_ma, :lim_eng_pct,
         :muni_mhhi, :muni_mhhi_pct_ma, :total_pop, :total_hh,
         ST_Multi(ST_Force2D(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326), 26986))))
    ON CONFLICT (geoid) DO UPDATE SET
        geo_area_name    = EXCLUDED.geo_area_name,
        municipality     = EXCLUDED.municipality,
        ej               = EXCLUDED.ej,
        ej_criteria      = EXCLUDED.ej_criteria,
        ej_crit_desc     = EXCLUDED.ej_crit_desc,
        pct_minority     = EXCLUDED.pct_minority,
        bg_mhhi          = EXCLUDED.bg_mhhi,
        bg_mhhi_pct_ma   = EXCLUDED.bg_mhhi_pct_ma,
        lim_eng_pct      = EXCLUDED.lim_eng_pct,
        muni_mhhi        = EXCLUDED.muni_mhhi,
        muni_mhhi_pct_ma = EXCLUDED.muni_mhhi_pct_ma,
        total_pop        = EXCLUDED.total_pop,
        total_hh         = EXCLUDED.total_hh,
        geom             = EXCLUDED.geom
""")


def _fetch_page(client: httpx.Client, offset: int) -> list[dict]:
    params = {
        "where": "1=1",
        "outFields": (
            "GEOID,GeographicAreaName,Municipality,"
            "EJ,EJ_CRITERIA,EJ_CRIT_DESC,"
            "pct_minority,BG_MHHI,BG_MHHI_pct_MAHHI,limEngHHpct,"
            "muni_MHHI,muniMHHI_pct_MAHHI,Totsl_pop,TotalHH"
        ),
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "f": "geojson",
    }
    for attempt in range(1, RETRY_MAX + 1):
        try:
            r = client.get(URL, params=params, timeout=60)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise RuntimeError(f"ArcGIS error: {d['error']}")
            return d.get("features", [])
        except Exception as exc:
            if attempt == RETRY_MAX:
                raise
            log.warning("Attempt %d failed (%s), retrying in %ds…", attempt, exc, RETRY_DELAY)
            time.sleep(RETRY_DELAY)
    return []


def _feat_to_row(feat: dict) -> dict | None:
    p = feat.get("properties") or {}
    g = feat.get("geometry")
    if not g or not p.get("GEOID"):
        return None

    def _f(key: str) -> float | None:
        v = p.get(key)
        return float(v) if v is not None else None

    def _i(key: str) -> int | None:
        v = p.get(key)
        return int(v) if v is not None else None

    return {
        "geoid":           p["GEOID"],
        "geo_area_name":   p.get("GeographicAreaName"),
        "municipality":    p.get("Municipality"),
        "ej":              (p.get("EJ") or "").strip().upper() == "YES",
        "ej_criteria":     p.get("EJ_CRITERIA"),
        "ej_crit_desc":    p.get("EJ_CRIT_DESC"),
        "pct_minority":    _f("pct_minority"),
        "bg_mhhi":         _f("BG_MHHI"),
        "bg_mhhi_pct_ma":  _f("BG_MHHI_pct_MAHHI"),
        "lim_eng_pct":     _f("limEngHHpct"),
        "muni_mhhi":       _f("muni_MHHI"),
        "muni_mhhi_pct_ma":_f("muniMHHI_pct_MAHHI"),
        "total_pop":       _i("Totsl_pop"),
        "total_hh":        _i("TotalHH"),
        "geom":            json.dumps(g),
    }


def run_ingest() -> int:
    total = 0
    offset = 0
    with httpx.Client(headers={"User-Agent": "Civo/1.0 (ej-population-ingest)"}) as client:
        while True:
            feats = _fetch_page(client, offset)
            if not feats:
                break
            rows = [r for f in feats if (r := _feat_to_row(f))]
            if rows:
                with engine.begin() as conn:
                    conn.execute(UPSERT, rows)
                total += len(rows)
                log.info("  %d rows upserted (offset %d)", total, offset)
            if len(feats) < PAGE_SIZE:
                break
            offset += len(feats)
    return total


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", action="store_true", help="Print row count and exit.")
    args = ap.parse_args(argv)

    if args.count:
        from sqlalchemy import text as _text
        with engine.connect() as conn:
            n = conn.execute(_text("SELECT COUNT(*) FROM ej_populations")).scalar()
            ej = conn.execute(_text("SELECT COUNT(*) FROM ej_populations WHERE ej")).scalar()
        print(f"ej_populations: {n:,} rows, {ej:,} EJ-designated")
        return

    log.info("Ingesting MA EJ Population 2020 block groups…")
    n = run_ingest()
    log.info("Done. %d block groups loaded.", n)


if __name__ == "__main__":
    main()
