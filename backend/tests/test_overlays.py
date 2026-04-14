"""Integration tests for GET /parcel/{id}/overlays."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import score as score_api
from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("CIVO_SKIP_API_TESTS") == "1", reason="CIVO_SKIP_API_TESTS=1"
)

KENDALL = "Kendall Square, Cambridge, MA 02142"
FALMOUTH = "Falmouth Tap area, Falmouth, MA 02540"


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _resolve_parcel_id(address: str) -> str:
    async with await _client() as c:
        r = await c.post("/score", json={"address": address})
    assert r.status_code == 200, r.text
    return r.json()["report"]["parcel_id"]


@pytest.mark.asyncio
async def test_overlays_default_radius_returns_feature_collection():
    pid = await _resolve_parcel_id(KENDALL)
    score_api._overlay_cache.clear()
    async with await _client() as c:
        r = await c.get(f"/parcel/{pid}/overlays")
    assert r.status_code == 200, r.text
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert fc["properties"]["radius_m"] == 2000
    assert fc["properties"]["feature_cap"] == 500
    assert isinstance(fc["properties"]["truncated"], bool)
    # Parcel is always the first feature.
    assert fc["features"][0]["properties"]["layer"] == "parcel"
    assert fc["features"][0]["properties"]["loc_id"] == pid
    # Every feature carries a layer key.
    allowed_layers = {
        "parcel", "esmp", "biomap_core", "biomap_cnl", "nhesp_priority",
        "nhesp_estimated", "fema_flood", "wetlands", "article97",
    }
    for feat in fc["features"]:
        assert feat["properties"]["layer"] in allowed_layers
    # counts dict covers every requested layer.
    for layer in allowed_layers:
        assert layer in fc["properties"]["counts"]


@pytest.mark.asyncio
async def test_overlays_radius_bounds_rejected():
    pid = await _resolve_parcel_id(KENDALL)
    async with await _client() as c:
        r_small = await c.get(f"/parcel/{pid}/overlays?radius_m=100")
        r_big = await c.get(f"/parcel/{pid}/overlays?radius_m=20000")
    # FastAPI returns 422 for Query(ge=..., le=...) violations
    assert r_small.status_code == 422
    assert r_big.status_code == 422


@pytest.mark.asyncio
async def test_overlays_truncates_and_flags():
    # 10km buffer in dense Cambridge will blow past the 500-feature cap.
    pid = await _resolve_parcel_id(KENDALL)
    score_api._overlay_cache.clear()
    async with await _client() as c:
        r = await c.get(f"/parcel/{pid}/overlays?radius_m=10000")
    assert r.status_code == 200
    fc = r.json()
    assert len(fc["features"]) <= 500
    assert fc["properties"]["truncated"] is True


@pytest.mark.asyncio
async def test_overlays_cache_hits():
    pid = await _resolve_parcel_id(KENDALL)
    score_api._overlay_cache.clear()
    async with await _client() as c:
        r1 = await c.get(f"/parcel/{pid}/overlays?radius_m=1500")
    assert r1.status_code == 200
    # cache was populated for this (pid, 1500); next call should hit it.
    assert (pid, 1500) in score_api._overlay_cache
    async with await _client() as c:
        r2 = await c.get(f"/parcel/{pid}/overlays?radius_m=1500")
    # identical payloads
    assert r1.json() == r2.json()


@pytest.mark.asyncio
async def test_overlays_404_on_unknown_parcel():
    async with await _client() as c:
        r = await c.get("/parcel/DOES_NOT_EXIST/overlays")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_overlay_properties_include_layer_specific_metadata():
    # Falmouth area will include ESMP + flood features — we can assert
    # layer-specific property keys on whichever features landed.
    pid = await _resolve_parcel_id(FALMOUTH)
    score_api._overlay_cache.clear()
    async with await _client() as c:
        r = await c.get(f"/parcel/{pid}/overlays?radius_m=3000")
    assert r.status_code == 200, r.text
    fc = r.json()
    by_layer: dict[str, list[dict]] = {}
    for feat in fc["features"]:
        by_layer.setdefault(feat["properties"]["layer"], []).append(feat["properties"])
    if by_layer.get("esmp"):
        p = by_layer["esmp"][0]
        # Required ESMP metadata per spec
        for k in ("name", "mw_added", "target_isd", "coordinate_confidence"):
            assert k in p, f"ESMP feature missing {k}: {p}"
    if by_layer.get("fema_flood"):
        p = by_layer["fema_flood"][0]
        for k in ("FLD_ZONE", "STATIC_BFE"):
            assert k in p
    if by_layer.get("wetlands"):
        p = by_layer["wetlands"][0]
        assert "WETCODE" in p
