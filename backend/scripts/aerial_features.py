"""Layer 3 — Aerial imagery feature extraction.

Fetches 256x256 orthophoto tiles for each parcel centroid from MassGIS WMS
(no GPU required). Extracts 4 simple image statistics that encode visual
suitability without needing a pretrained neural network:

  aerial_veg_index       — (R - B) / (R + B + 1e-6): high = cleared land, low = dense canopy
  aerial_edge_density    — Laplacian variance: high = structures/roads, low = open field
  aerial_mean_brightness — dark (canopy/water) vs bright (impervious/cleared)
  aerial_texture_var     — pixel standard deviation: low = uniform open land

Stored in parcel_ml_features and used as additional features in the LightGBM ranker.

Phase 2 upgrade path: swap simple stats for EfficientNet-B0 embeddings
(fine-tuned on ~500 labeled parcel images) for a full deep-learning feature layer.

Usage:
    python -m scripts.aerial_features [--town Acton] [--workers 4]
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import httpx
from sqlalchemy import text

sys.path.insert(0, ".")
from app.db import SessionLocal

try:
    from PIL import Image, ImageFilter
    import numpy as np
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# MassGIS 2023 Orthophoto WMS (publicly accessible, EPSG:4326)
_WMS_URL = (
    "https://giswebservices.massgis.state.ma.us/geoserver/wms?"
    "SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
    "&LAYERS=massgis:USGS_Orthos_2023"
    "&SRS=EPSG:4326"
    "&FORMAT=image/png"
    "&WIDTH=256&HEIGHT=256"
    "&BBOX={west},{south},{east},{north}"
)
_TILE_HALF_DEG = 0.002   # ~220m at MA latitude


def _fetch_tile(lat: float, lon: float) -> "Image.Image | None":
    url = _WMS_URL.format(
        west=lon - _TILE_HALF_DEG,
        south=lat - _TILE_HALF_DEG,
        east=lon + _TILE_HALF_DEG,
        north=lat + _TILE_HALF_DEG,
    )
    try:
        resp = httpx.get(url, timeout=12)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        pass
    return None


def _extract_features(img: "Image.Image") -> dict[str, float]:
    arr = np.array(img, dtype=np.float32)
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    veg_index = float(np.mean((R - B) / (R + B + 1e-6)))
    mean_brightness = float(np.mean((R + G + B) / 3))
    texture_var = float(np.std((R + G + B) / 3))

    # Edge density via Laplacian filter
    gray = img.convert("L")
    lap = gray.filter(ImageFilter.Kernel(
        size=3, kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1], scale=1
    ))
    edge_density = float(np.var(np.array(lap, dtype=np.float32)))

    return {
        "aerial_veg_index": round(veg_index, 4),
        "aerial_edge_density": round(edge_density, 2),
        "aerial_mean_brightness": round(mean_brightness, 2),
        "aerial_texture_var": round(texture_var, 2),
    }


_UPDATE_SQL = text("""
    UPDATE parcel_ml_features SET
        aerial_veg_index      = :veg,
        aerial_edge_density   = :edge,
        aerial_mean_brightness = :brightness,
        aerial_texture_var    = :texture,
        aerial_at             = :now
    WHERE parcel_loc_id = :loc_id
""")


def _process_parcel(parcel_id: str, lat: float, lon: float) -> tuple[str, bool]:
    img = _fetch_tile(lat, lon)
    if img is None:
        return parcel_id, False

    feats = _extract_features(img)
    with SessionLocal() as session:
        session.execute(_UPDATE_SQL, {
            "loc_id": parcel_id,
            "veg": feats["aerial_veg_index"],
            "edge": feats["aerial_edge_density"],
            "brightness": feats["aerial_mean_brightness"],
            "texture": feats["aerial_texture_var"],
            "now": datetime.now(timezone.utc),
        })
        session.commit()

    time.sleep(0.1)  # respect MassGIS rate limit
    return parcel_id, True


def main() -> None:
    if not _PIL_AVAILABLE:
        print("Pillow + numpy not installed. Run: pip install Pillow numpy")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--town")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    with SessionLocal() as session:
        q = """
            SELECT f.parcel_loc_id,
                   ST_Y(ST_Transform(ST_Centroid(p.geom), 4326)) AS lat,
                   ST_X(ST_Transform(ST_Centroid(p.geom), 4326)) AS lon
            FROM parcel_ml_features f
            JOIN parcels p ON p.loc_id = f.parcel_loc_id
            WHERE f.aerial_at IS NULL
        """
        params: dict = {}
        if args.town:
            q += " AND p.town_name = :town"
            params["town"] = args.town
        parcels = session.execute(text(q), params).mappings().all()

    print(f"Fetching aerial features for {len(parcels)} parcels ...")

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_process_parcel, r["parcel_loc_id"], r["lat"], r["lon"]): r["parcel_loc_id"]
            for r in parcels
        }
        for fut in as_completed(futures):
            _, ok = fut.result()
            if ok:
                done += 1
                if done % 50 == 0:
                    print(f"  {done}/{len(parcels)} ...")

    print(f"Done — {done} parcels scored.")


if __name__ == "__main__":
    main()
