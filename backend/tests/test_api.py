"""Integration tests for Phase 4 API routes.

Hits the FastAPI app in-process via ``httpx.AsyncClient`` + ASGI transport
— no uvicorn, no network port. Requires the live Postgres from
docker-compose because the engine runs real spatial queries.

Benchmark addresses are used because they're pre-cached in
``data/cache/address_geocode.json`` so the tests don't need the Places
key in CI.
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("CIVO_SKIP_API_TESTS") == "1", reason="CIVO_SKIP_API_TESTS=1"
)

KENDALL = "Kendall Square, Cambridge, MA 02142"
EAST_EAGLE = "East Eagle St, East Boston, MA 02128"
SEAPORT = "Seaport District, Boston, MA 02210"
WORTHINGTON = "Worthington, MA 01098"


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_health_still_works_after_router_install():
    async with await _client() as c:
        r = await c.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["postgis"].startswith("3.")
    assert j["pgvector"].startswith("0.")


@pytest.mark.asyncio
async def test_post_score_returns_full_report_and_persists():
    async with await _client() as c:
        r = await c.post(
            "/score",
            json={"address": KENDALL, "project_type": "underground_substation"},
        )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["address"] == KENDALL
    assert j["resolution_mode"] in {"contains", "nearest", "esmp_anchored"}
    assert isinstance(j["report_id"], int) and j["report_id"] > 0
    rep = j["report"]
    assert set(
        c["key"] for c in rep["criteria"]
    ) == {
        "grid_alignment",
        "climate_resilience",
        "carbon_storage",
        "biodiversity",
        "burdens",
        "benefits",
        "agriculture",
    }
    # Kendall Sq is an urban underground sub site -> should come out SUITABLE-ish.
    assert rep["bucket"] in {"SUITABLE", "CONDITIONALLY SUITABLE"}
    assert 50 <= rep["total_score"] <= 100
    # Re-fetch by report_id
    async with await _client() as c:
        r2 = await c.get(f"/report/{j['report_id']}")
    assert r2.status_code == 200
    rep2 = r2.json()
    assert rep2["parcel_id"] == rep["parcel_id"]
    assert rep2["total_score"] == rep["total_score"]


@pytest.mark.asyncio
async def test_score_rejects_unresolvable_address():
    async with await _client() as c:
        r = await c.post(
            "/score",
            json={"address": "123 This Street Does Not Exist, Narnia, MA 00000"},
        )
    # Places returns ZERO_RESULTS -> ResolveError -> 422
    assert r.status_code in {422, 502}


@pytest.mark.asyncio
async def test_parcel_geojson_returns_wgs84_feature():
    # First score something to discover a real loc_id
    async with await _client() as c:
        r = await c.post("/score", json={"address": SEAPORT})
        assert r.status_code == 200
        pid = r.json()["report"]["parcel_id"]

        r2 = await c.get(f"/parcel/{pid}/geojson")
    assert r2.status_code == 200
    feat = r2.json()
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    # Coordinates should be WGS84 (longitude in [-72, -70], lat in [41, 43] for MA)
    coords = feat["geometry"]["coordinates"]
    # Drill to a point regardless of Multi/Single
    pt = coords
    while isinstance(pt, list) and isinstance(pt[0], list):
        pt = pt[0]
    lon, lat = pt[:2]
    assert -74 < lon < -69, f"lon {lon} not in MA range"
    assert 41 < lat < 43, f"lat {lat} not in MA range"
    assert feat["properties"]["loc_id"] == pid


@pytest.mark.asyncio
async def test_parcel_geojson_404_on_unknown_loc_id():
    async with await _client() as c:
        r = await c.get("/parcel/DOES_NOT_EXIST/geojson")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_report_404():
    async with await _client() as c:
        r = await c.get("/report/999999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_score_batch_runs_concurrently_and_ranks():
    addresses = [KENDALL, EAST_EAGLE, SEAPORT, WORTHINGTON]
    async with await _client() as c:
        r = await c.post(
            "/score/batch",
            json={"addresses": addresses, "project_type": "substation"},
        )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["summary"]["n"] == 4
    assert j["summary"]["n_ok"] >= 3
    items = j["items"]
    assert len(items) == 4
    # Ranked descending by score among ok items
    ok_scores = [i["total_score"] for i in items if i["ok"]]
    assert ok_scores == sorted(ok_scores, reverse=True)
    # Buckets are a dict counting known values
    for b in j["summary"]["bucket_counts"]:
        assert b in {"SUITABLE", "CONDITIONALLY SUITABLE", "CONSTRAINED"}


@pytest.mark.asyncio
async def test_score_batch_caps_at_50():
    async with await _client() as c:
        r = await c.post(
            "/score/batch",
            json={"addresses": ["x"] * 51},
        )
    # pydantic rejects max_length before the handler runs
    assert r.status_code == 422
