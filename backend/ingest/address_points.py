"""Ingest MassGIS Master Address Points into the address_points table.

Source: MassGIS MAD MapServer
  https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/
  MassGIS_Master_Address_Points/MapServer/0

Downloads ~3.7M building-centroid points for all 351 MA towns and loads
them into the address_points table. After loading, runs a spatial join
to populate loc_id from the parcels table.

Usage
-----
    cd v2/backend
    python -m ingest.address_points               # full statewide run
    python -m ingest.address_points --towns "ACTON,CAMBRIDGE"  # subset
    python -m ingest.address_points --join-only   # skip download, just run spatial join
    python -m ingest.address_points --count       # print current row count and exit
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Generator

import httpx
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

MAPSERVER = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL"
    "/MassGIS_Master_Address_Points/MapServer/0"
)
FIELDS = (
    "ADDRESS_NUMBER,ADDRESS_NUMBER_SUFFIX,STREET_NAME,UNIT,"
    "GEOGRAPHIC_TOWN,POSTCODE,COUNTY,POINT_TYPE,MASTER_ADDRESS_ID"
)
BATCH = 2000
RETRY_MAX = 4
RETRY_DELAY = 5  # seconds between retries


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return url


def _fetch_page(
    client: httpx.Client,
    where: str,
    offset: int,
    batch: int = BATCH,
) -> list[dict]:
    """Fetch one page from the MapServer with retry logic."""
    params = {
        "where": where,
        "outFields": FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",
        "resultOffset": offset,
        "resultRecordCount": batch,
        "f": "json",
    }
    for attempt in range(1, RETRY_MAX + 1):
        try:
            r = client.get(f"{MAPSERVER}/query", params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(f"ArcGIS error: {data['error']}")
            return data.get("features", [])
        except Exception as exc:
            if attempt == RETRY_MAX:
                raise
            log.warning("Attempt %d failed (%s), retrying in %ds…", attempt, exc, RETRY_DELAY)
            time.sleep(RETRY_DELAY)
    return []


def _pages(
    client: httpx.Client,
    where: str = "1=1",
) -> Generator[list[dict], None, None]:
    """Yield pages of features until exhausted."""
    offset = 0
    while True:
        feats = _fetch_page(client, where, offset)
        if not feats:
            break
        yield feats
        if len(feats) < BATCH:
            break
        offset += len(feats)


def _row_from_feature(feat: dict) -> dict | None:
    a = feat.get("attributes") or {}
    g = feat.get("geometry") or {}
    lon = g.get("x")
    lat = g.get("y")
    if lat is None or lon is None:
        return None
    num = a.get("ADDRESS_NUMBER")
    street = (a.get("STREET_NAME") or "").strip().upper()
    town = (a.get("GEOGRAPHIC_TOWN") or "").strip().upper()
    if not num or not street or not town:
        return None
    return {
        "addr_num": int(num),
        "addr_suffix": (a.get("ADDRESS_NUMBER_SUFFIX") or "").strip() or None,
        "street_name": street,
        "unit": (a.get("UNIT") or "").strip() or None,
        "town": town,
        "postcode": (a.get("POSTCODE") or "").strip() or None,
        "county": (a.get("COUNTY") or "").strip() or None,
        "point_type": (a.get("POINT_TYPE") or "").strip() or None,
        "lat": lat,
        "lon": lon,
        "master_address_id": a.get("MASTER_ADDRESS_ID"),
    }


_UPSERT = text("""
    INSERT INTO address_points
        (addr_num, addr_suffix, street_name, unit, town, postcode, county,
         point_type, lat, lon, master_address_id)
    VALUES
        (:addr_num, :addr_suffix, :street_name, :unit, :town, :postcode, :county,
         :point_type, :lat, :lon, :master_address_id)
    ON CONFLICT (addr_num, street_name, town,
                 COALESCE(unit,''), COALESCE(addr_suffix,''))
    DO UPDATE SET
        lat               = EXCLUDED.lat,
        lon               = EXCLUDED.lon,
        postcode          = EXCLUDED.postcode,
        point_type        = EXCLUDED.point_type,
        master_address_id = EXCLUDED.master_address_id
""")


def run_download(engine, towns: list[str] | None = None) -> int:
    """Download address points and upsert into address_points table.

    Returns total rows inserted/updated.
    """
    client = httpx.Client(headers={"User-Agent": "Civo/1.0 (parcel-resolver)"})
    total = 0

    if towns:
        # Download one town at a time for progress visibility
        for town in towns:
            where = f"UPPER(GEOGRAPHIC_TOWN)='{town.upper().replace(chr(39), chr(39)*2)}'"
            _download_where(client, engine, where, label=town)
    else:
        # Statewide paginated download
        total = _download_where(client, engine, "1=1", label="statewide")

    return total


def _download_where(
    client: httpx.Client,
    engine,
    where: str,
    label: str,
) -> int:
    total = 0
    batch_rows: list[dict] = []

    def flush():
        nonlocal total
        if not batch_rows:
            return
        with engine.begin() as conn:
            conn.execute(_UPSERT, batch_rows)
        total += len(batch_rows)
        batch_rows.clear()

    log.info("Downloading %s…", label)
    for page in _pages(client, where=where):
        for feat in page:
            row = _row_from_feature(feat)
            if row:
                batch_rows.append(row)
        if len(batch_rows) >= 5000:
            flush()
            log.info("  %s: %d rows so far", label, total)
    flush()
    log.info("  %s: %d rows total", label, total)
    return total


def run_spatial_join(engine) -> int:
    """Populate loc_id by spatially joining address_points to parcels.

    Uses ST_Contains so only points inside a parcel get matched. Points
    outside any indexed parcel (roads, offshore, etc.) are left as NULL.

    This is a bulk UPDATE — expect 5-30 minutes on 3.7M rows depending
    on hardware and whether parcels.geom has a warm GiST cache.
    """
    log.info("Running spatial join address_points → parcels (this takes a while)…")
    t0 = time.time()
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE address_points ap
            SET    loc_id = p.loc_id,
                   geom   = ST_Transform(
                                ST_SetSRID(ST_MakePoint(ap.lon, ap.lat), 4326),
                                26986
                             )
            FROM   parcels p
            WHERE  ap.loc_id IS NULL
              AND  ST_Contains(
                       p.geom,
                       ST_Transform(ST_SetSRID(ST_MakePoint(ap.lon, ap.lat), 4326), 26986)
                   )
        """))
        matched = result.rowcount
    elapsed = time.time() - t0
    log.info("Spatial join done: %d points matched in %.1fs", matched, elapsed)

    # Report remaining unmatched
    with engine.connect() as conn:
        unmatched = conn.execute(text(
            "SELECT COUNT(*) FROM address_points WHERE loc_id IS NULL"
        )).scalar()
    log.info("Unmatched (no containing parcel): %d", unmatched)
    return matched


def run_geom_update(engine) -> None:
    """Populate geom column for rows where it's still NULL (no loc_id match)."""
    log.info("Populating geom for unmatched rows…")
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE address_points
            SET geom = ST_Transform(
                           ST_SetSRID(ST_MakePoint(lon, lat), 4326),
                           26986
                       )
            WHERE geom IS NULL
        """))
    log.info("geom update done.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--towns",
        help="Comma-separated list of towns to download (e.g. 'ACTON,CAMBRIDGE'). "
             "Default: all 351 MA towns.",
    )
    parser.add_argument(
        "--join-only",
        action="store_true",
        help="Skip download; only run the spatial join.",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Print current row count and exit.",
    )
    parser.add_argument(
        "--no-join",
        action="store_true",
        help="Download only; skip the spatial join step.",
    )
    args = parser.parse_args(argv)

    # Load .env if present
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    engine = create_engine(_db_url())

    if args.count:
        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM address_points")).scalar()
            matched = conn.execute(
                text("SELECT COUNT(*) FROM address_points WHERE loc_id IS NOT NULL")
            ).scalar()
        print(f"address_points: {n:,} rows, {matched:,} with loc_id ({100*matched/max(n,1):.1f}%)")
        return

    if not args.join_only:
        towns = [t.strip().upper() for t in args.towns.split(",")] if args.towns else None
        run_download(engine, towns=towns)

    if not args.no_join:
        run_spatial_join(engine)
        run_geom_update(engine)

    log.info("Done.")


if __name__ == "__main__":
    main()
