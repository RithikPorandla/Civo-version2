"""Integration tests for POST/GET/DELETE /portfolio."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("CIVO_SKIP_API_TESTS") == "1", reason="CIVO_SKIP_API_TESTS=1"
)

KENDALL = "Kendall Square, Cambridge, MA 02142"
SEAPORT = "Seaport District, Boston, MA 02210"
WORTHINGTON = "Worthington, MA 01098"


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_portfolio_create_persists_and_returns_ranked_items():
    async with await _client() as c:
        r = await c.post(
            "/portfolio",
            json={
                "name": "test-portfolio-1",
                "addresses": [KENDALL, SEAPORT, WORTHINGTON],
                "project_type": "substation",
            },
        )
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["id"].startswith("port_")
    assert len(env["id"]) == len("port_") + 10
    assert env["state"] == "MA"
    assert env["project_type"] == "substation"
    assert env["config_version"] == "ma-eea-2026-v1"
    assert len(env["items"]) == 3
    # Ranked top-to-bottom by score
    scores = [it["total_score"] for it in env["items"] if it["ok"]]
    assert scores == sorted(scores, reverse=True)
    ranks = [it["rank"] for it in env["items"]]
    assert ranks == [1, 2, 3]
    # Every ok item has a parcel_id + score_report_id + bucket
    for it in env["items"]:
        if it["ok"]:
            assert it["parcel_id"]
            assert it["score_report_id"]
            assert it["bucket"] in {"SUITABLE", "CONDITIONALLY SUITABLE", "CONSTRAINED"}


@pytest.mark.asyncio
async def test_portfolio_roundtrip_get_matches_create():
    async with await _client() as c:
        r = await c.post(
            "/portfolio",
            json={"addresses": [KENDALL, SEAPORT]},
        )
    pid = r.json()["id"]
    async with await _client() as c:
        r2 = await c.get(f"/portfolio/{pid}")
    assert r2.status_code == 200
    env = r2.json()
    assert env["id"] == pid
    assert len(env["items"]) == 2


@pytest.mark.asyncio
async def test_portfolio_get_404_on_unknown_id():
    async with await _client() as c:
        r = await c.get("/portfolio/port_nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_portfolio_delete_removes_row():
    async with await _client() as c:
        r = await c.post("/portfolio", json={"addresses": [KENDALL]})
    pid = r.json()["id"]
    async with await _client() as c:
        r_del = await c.delete(f"/portfolio/{pid}")
    assert r_del.status_code == 204
    async with await _client() as c:
        r_get = await c.get(f"/portfolio/{pid}")
    assert r_get.status_code == 404


@pytest.mark.asyncio
async def test_portfolio_delete_404_on_unknown_id():
    async with await _client() as c:
        r = await c.delete("/portfolio/port_nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_portfolio_rejects_empty_and_oversize_address_lists():
    async with await _client() as c:
        r_empty = await c.post("/portfolio", json={"addresses": []})
        r_big = await c.post("/portfolio", json={"addresses": ["x"] * 51})
    assert r_empty.status_code == 422
    assert r_big.status_code == 422
