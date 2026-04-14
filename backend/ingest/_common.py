"""Shared helpers for MassGIS ArcGIS REST ingestion.

The MA feature services all follow the same pagination / spatial-filter
contract, so the per-layer scripts stay focused on table-specific shaping.
"""

from __future__ import annotations

import json
import time
from typing import Iterator

import httpx

TOWN_SURVEY_URL = (
    "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/AGOL/"
    "Towns_survey_polym/FeatureServer/0/query"
)

# Full MassGIS TOWN_ID lookup for our 10 target towns plus every town that
# appears as an ESMP project municipality. Verified live against the
# TOWNSSURVEY_POLYM service on 2026-04-14 (see scripts/resolve_town_ids
# in commit history).
TOWN_IDS: dict[str, int] = {
    "Acton": 2,
    "Boston": 35,
    "Brewster": 41,
    "Burlington": 48,
    "Cambridge": 49,
    "Chelsea": 57,
    "Deerfield": 74,
    "Dennis": 75,
    "Fairhaven": 94,
    "Falmouth": 96,
    "Freetown": 102,
    "East Freetown": 102,  # East Freetown is a village within Freetown.
    "Marion": 169,
    "Natick": 198,
    "Needham": 199,
    "New Bedford": 201,
    "Newton": 207,
    "Somerville": 274,
    "Waltham": 308,
    "Whately": 337,
    "Worthington": 349,
}

TARGET_TOWNS: list[str] = [
    "Acton",
    "Burlington",
    "Falmouth",
    "Natick",
    "Somerville",
    "Cambridge",
    "New Bedford",
    "East Freetown",
    "Worthington",
    "Whately",
]


def resolve_town_id(town: str) -> int:
    """Resolve a human town name to a MassGIS TOWN_ID."""
    key = town.strip()
    if key in TOWN_IDS:
        return TOWN_IDS[key]
    # Case-insensitive fallback.
    for k, v in TOWN_IDS.items():
        if k.lower() == key.lower():
            return v
    raise SystemExit(
        f"Unknown town '{town}'. Known: {sorted(TOWN_IDS)}. "
        "Add it to TOWN_IDS in backend/ingest/_common.py."
    )


def _request_with_retry(
    client: httpx.Client, method: str, url: str, *, retries: int = 4, **kw
) -> httpx.Response:
    """GET/POST with exponential backoff on transient MassGIS failures."""
    delay = 2.0
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = client.request(method, url, **kw)
            if r.status_code >= 500:
                raise httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
            r.raise_for_status()
            return r
        except (
            httpx.RemoteProtocolError,
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.HTTPStatusError,
        ) as e:
            last = e
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    raise RuntimeError("unreachable") from last


def fetch_town_geometry(client: httpx.Client, town: str) -> dict:
    """Return the town's boundary as an Esri-JSON polygon geometry (26986)."""
    town_id = resolve_town_id(town)
    r = _request_with_retry(
        client,
        "GET",
        TOWN_SURVEY_URL,
        params={
            "where": f"TOWN_ID={town_id}",
            "outFields": "TOWN,TOWN_ID",
            "outSR": 26986,
            "f": "json",
            "returnGeometry": "true",
        },
        timeout=60,
    )
    data = r.json()
    feats = data.get("features") or []
    if not feats:
        raise RuntimeError(f"no town polygon returned for {town} (id={town_id})")
    rings: list = []
    for f in feats:
        for ring in f["geometry"]["rings"]:
            rings.append(ring)
    return {"rings": rings, "spatialReference": {"wkid": 26986}}


def envelope_of(town_geometry: dict) -> tuple[float, float, float, float]:
    """Compute the axis-aligned bounding box in EPSG:26986."""
    xs: list[float] = []
    ys: list[float] = []
    for ring in town_geometry["rings"]:
        for pt in ring:
            xs.append(pt[0])
            ys.append(pt[1])
    return min(xs), min(ys), max(xs), max(ys)


def paged_query(
    client: httpx.Client,
    url: str,
    base_params: dict,
    page_size: int = 2000,
) -> Iterator[dict]:
    """Yield GeoJSON features, transparently paginating via resultOffset.

    Uses POST when the combined params are large enough to risk URL-length
    rejection by MassGIS (e.g., polygon spatial filters). Retries transient
    failures with exponential backoff.
    """
    offset = 0
    body_bytes_threshold = 1500  # heuristic: serialize & pick POST past this
    while True:
        params = dict(base_params)
        params.update(
            {
                "resultOffset": offset,
                "resultRecordCount": page_size,
                "f": "geojson",
                "returnGeometry": "true",
            }
        )
        approx_len = sum(len(str(v)) for v in params.values())
        method = "POST" if approx_len > body_bytes_threshold else "GET"
        kwargs = {"data": params} if method == "POST" else {"params": params}
        r = _request_with_retry(client, method, url, timeout=300, **kwargs)
        data = r.json()
        feats = data.get("features") or []
        if not feats:
            return
        yield from feats
        exceeded = data.get("exceededTransferLimit") or len(feats) == page_size
        if not exceeded:
            return
        offset += page_size


def town_filter_params(town_geometry: dict, mode: str = "envelope") -> dict:
    """ArcGIS spatial-filter parameters.

    ``mode='envelope'`` uses the town bbox (small payload, may return a few
    rows outside the town — acceptable because scoring re-tests against the
    parcel polygon with PostGIS anyway). ``mode='polygon'`` uses the full
    town polygon; payload can be large and requires POST.
    """
    if mode == "envelope":
        xmin, ymin, xmax, ymax = envelope_of(town_geometry)
        return {
            "geometry": f"{xmin},{ymin},{xmax},{ymax}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 26986,
            "spatialRel": "esriSpatialRelIntersects",
            "outSR": 26986,
        }
    return {
        "geometry": json.dumps(town_geometry),
        "geometryType": "esriGeometryPolygon",
        "inSR": 26986,
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": 26986,
    }
