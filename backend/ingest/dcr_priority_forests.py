"""Ingest DCR Priority Forests — top-20% carbon storage forests (statewide).

Source: MassGIS / MA DCR Priority Forests
    https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/
    DCR_PriorityForests/FeatureServer/0

These polygons represent the highest-value forest blocks for carbon storage
statewide, per the DCR Forest Carbon Initiative. Overlap with a parcel triggers
the carbon_top20 ineligibility flag under 225 CMR 29.06 and feeds Criterion 3
(Carbon Storage) in the scoring engine.

Unlike other layers (which are ingested per-town), DCR Priority Forests are
a statewide layer loaded in a single pass — towns don't own forest carbon
boundaries meaningfully. Run once after the initial schema migration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import engine  # noqa: E402
from ingest._common import _request_with_retry, paged_query  # noqa: E402

URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "DCR_PriorityForests/FeatureServer/0/query"
)

PAGE_SIZE = 1000

INSERT_SQL = text(
    """
INSERT INTO dcr_priority_forests (forest_id, forest_name, carbon_tier, attrs, geom)
VALUES (
    :forest_id, :forest_name, :carbon_tier, CAST(:attrs AS jsonb),
    ST_Multi(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 26986)))
)
ON CONFLICT DO NOTHING;
"""
)


def _feature_to_row(feat: dict) -> dict | None:
    g = feat.get("geometry")
    if not g:
        return None
    p = feat.get("properties") or {}
    return {
        "forest_id": str(p.get("OBJECTID") or p.get("FID") or ""),
        "forest_name": p.get("FORESTNAME") or p.get("SITE_NAME") or p.get("NAME"),
        "carbon_tier": p.get("CARBON_TIER") or p.get("TIER") or p.get("PRIORITY"),
        "attrs": json.dumps(p),
        "geom": json.dumps(g),
    }


def ingest() -> int:
    """Load all DCR Priority Forest polygons into the database (statewide, one pass)."""
    total = 0
    with httpx.Client(timeout=180) as client:
        # Verify service is reachable before wiping existing data
        probe = _request_with_retry(
            client, "GET", URL,
            params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
        )
        count = probe.json().get("count", 0)
        if count == 0:
            print(
                f"[dcr_priority_forests] Service returned 0 features or is unreachable.\n"
                f"  URL: {URL}\n"
                f"  Verify the service name is correct in MassGIS ArcGIS Online.\n"
                f"  Skipping ingest — existing data preserved."
            )
            return 0

        print(f"[dcr_priority_forests] {count} features to ingest")

        with engine.begin() as conn:
            deleted = conn.execute(text("DELETE FROM dcr_priority_forests")).rowcount
            if deleted:
                print(f"[dcr_priority_forests] cleared {deleted} existing rows")

        params = {"where": "1=1", "outFields": "*", "outSR": 26986, "f": "geojson"}
        batch: list[dict] = []
        for feat in paged_query(client, URL, params, page_size=PAGE_SIZE):
            row = _feature_to_row(feat)
            if row:
                batch.append(row)
            if len(batch) >= PAGE_SIZE:
                with engine.begin() as conn:
                    conn.execute(INSERT_SQL, batch)
                total += len(batch)
                print(f"[dcr_priority_forests] +{total} rows")
                batch.clear()
        if batch:
            with engine.begin() as conn:
                conn.execute(INSERT_SQL, batch)
            total += len(batch)

    print(f"Done. {total} DCR Priority Forest polygons ingested.")
    return total


def main() -> None:
    ingest()


if __name__ == "__main__":
    main()
