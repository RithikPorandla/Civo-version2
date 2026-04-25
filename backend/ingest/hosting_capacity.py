"""Ingest Eversource and National Grid Hosting Capacity Analysis (HCA) data.

Eversource publishes HCA shapefiles/CSVs annually under their Grid
Modernization filing. National Grid publishes equivalent data under
DPU 24-EL-01. Both use similar schemas.

Expected input format (CSV with columns):
    utility, circuit_id, substation_name, voltage_kv, available_mw,
    technology, data_year, source_url, lat, lon

Download sources:
    Eversource HCA: https://www.eversource.com/content/ct-c/residential/
                    my-account/billing-payments/about-your-bill/
                    rates-and-tariffs/hosting-capacity-analysis
    National Grid HCA: https://www.nationalgridus.com/MA-Electric/Business/
                       Rates-and-Tariffs/Grid-Modernization

Usage:
    python ingest/hosting_capacity.py --file data/eversource_hca_2025.csv --utility Eversource
    python ingest/hosting_capacity.py --file data/nationalgrid_hca_2025.csv --utility "National Grid"
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import engine

UPSERT_SQL = text("""
    INSERT INTO hosting_capacity
        (utility, circuit_id, substation_name, voltage_kv, available_mw,
         technology, data_year, source_url, attrs, geom)
    VALUES (
        :utility, :circuit_id, :substation_name, :voltage_kv, :available_mw,
        :technology, :data_year, :source_url, CAST(:attrs AS jsonb),
        ST_Transform(ST_SetSRID(ST_Point(:lon, :lat), 4326), 26986)
    )
    ON CONFLICT DO NOTHING
""")


def ingest_csv(path: Path, utility: str, dry_run: bool = False) -> int:
    rows = list(csv.DictReader(open(path)))
    print(f"Loaded {len(rows)} records from {path.name}")
    if dry_run:
        print("[dry-run] Would insert:", len(rows))
        return len(rows)

    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
                available_mw = float(row.get("available_mw") or 0)
            except (ValueError, KeyError):
                continue

            tech = (row.get("technology") or "all").strip().lower()
            if tech not in ("solar", "bess", "all"):
                tech = "all"

            extra = {k: v for k, v in row.items()
                     if k not in {"lat", "lon", "utility", "circuit_id", "substation_name",
                                  "voltage_kv", "available_mw", "technology", "data_year", "source_url"}}

            conn.execute(UPSERT_SQL, {
                "utility": utility,
                "circuit_id": row.get("circuit_id") or None,
                "substation_name": row.get("substation_name") or None,
                "voltage_kv": float(row["voltage_kv"]) if row.get("voltage_kv") else None,
                "available_mw": available_mw,
                "technology": tech,
                "data_year": int(row["data_year"]) if row.get("data_year") else None,
                "source_url": row.get("source_url") or None,
                "attrs": json.dumps(extra),
                "lat": lat,
                "lon": lon,
            })
            inserted += 1

    print(f"Inserted {inserted} hosting capacity records for {utility}")
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, help="CSV file path")
    parser.add_argument("--utility", required=True, help="'Eversource' or 'National Grid'")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ingest_csv(Path(args.file), args.utility, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
