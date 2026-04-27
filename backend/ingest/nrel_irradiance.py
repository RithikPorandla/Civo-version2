"""Ingest NASA POWER solar irradiance data for all MA parcels.

Uses the NASA POWER Climatology API (free, no API key, ~50km grid resolution).
Fetches annual average GHI (Global Horizontal Irradiance) in kWh/m²/year for
a grid of points covering Massachusetts, then assigns each parcel the value
of its nearest grid point.

Usage:
    python -m ingest.nrel_irradiance [--dry-run]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import SessionLocal

# NASA POWER API — returns long-term annual mean GHI in kWh/m²/day
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"

# 0.5° grid covering MA: lat 41.0–43.0, lon -74.0 to -69.5
MA_GRID_LATS = [41.0, 41.5, 42.0, 42.5, 43.0]
MA_GRID_LONS = [-74.0, -73.5, -73.0, -72.5, -72.0, -71.5, -71.0, -70.5, -70.0, -69.5]


def _fetch_ghi(lat: float, lon: float, client: httpx.Client) -> float | None:
    """Fetch annual average GHI (kWh/m²/day) from NASA POWER for one point."""
    try:
        resp = client.get(
            NASA_POWER_URL,
            params={
                "parameters": "ALLSKY_SFC_SW_DWN",
                "community": "RE",
                "longitude": lon,
                "latitude": lat,
                "format": "JSON",
                "start": "2001",
                "end": "2020",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        annual = data["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"].get("ANN")
        return float(annual) if annual and annual != -999 else None
    except Exception as e:
        print(f"    NASA POWER error ({lat},{lon}): {e}")
        return None


def fetch_ma_grid() -> dict[tuple[float, float], float]:
    """Fetch GHI for the MA grid. Returns {(lat, lon): ghi_kwh_m2_day}."""
    grid: dict[tuple[float, float], float] = {}
    print(f"Fetching NASA POWER GHI for {len(MA_GRID_LATS) * len(MA_GRID_LONS)} grid points ...")
    with httpx.Client() as client:
        for lat in MA_GRID_LATS:
            for lon in MA_GRID_LONS:
                ghi = _fetch_ghi(lat, lon, client)
                if ghi is not None:
                    grid[(lat, lon)] = ghi
                    print(f"  ({lat}, {lon}) → {ghi:.2f} kWh/m²/day")
                time.sleep(0.5)  # NASA POWER rate limit
    return grid


def _nearest_ghi(lat: float, lon: float, grid: dict[tuple[float, float], float]) -> float | None:
    """Return GHI of nearest grid point."""
    if not grid:
        return None
    nearest = min(grid.keys(), key=lambda p: (p[0] - lat) ** 2 + (p[1] - lon) ** 2)
    return grid[nearest]


def assign_to_parcels(grid: dict[tuple[float, float], float], dry_run: bool = False) -> int:
    """Assign nearest-grid GHI to every row in parcel_ml_features. Returns rows updated."""
    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT f.parcel_loc_id,
                   ST_Y(ST_Transform(ST_Centroid(p.geom), 4326)) AS lat,
                   ST_X(ST_Transform(ST_Centroid(p.geom), 4326)) AS lon
            FROM parcel_ml_features f
            JOIN parcels p ON p.loc_id = f.parcel_loc_id
            WHERE f.solar_ghi_kwh_m2_yr IS NULL
        """)).mappings().all()

        print(f"Assigning GHI to {len(rows)} parcels ...")
        if dry_run or not rows:
            return len(rows)

        updated = 0
        for row in rows:
            ghi_day = _nearest_ghi(row["lat"], row["lon"], grid)
            if ghi_day is None:
                continue
            ghi_year = ghi_day * 365  # kWh/m²/year
            session.execute(
                text("UPDATE parcel_ml_features SET solar_ghi_kwh_m2_yr = :g WHERE parcel_loc_id = :pid"),
                {"g": ghi_year, "pid": row["parcel_loc_id"]},
            )
            updated += 1

        session.commit()
        return updated


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    grid = fetch_ma_grid()
    print(f"\nGrid points fetched: {len(grid)}")

    n = assign_to_parcels(grid, dry_run=args.dry_run)
    print(f"Done — {n} parcels {'would be ' if args.dry_run else ''}updated with solar GHI")


if __name__ == "__main__":
    main()
