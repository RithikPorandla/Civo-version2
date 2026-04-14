"""Score API — address-in, SuitabilityReport-out.

Routes
------
- POST /score                    — one address, one report
- POST /score/batch              — up to 50 addresses concurrently
- GET  /report/{report_id}       — re-read a persisted report by id
- GET  /parcel/{parcel_id}/geojson  — parcel polygon in WGS84 for maps

Concurrency
-----------
The scoring engine is synchronous (GeoAlchemy2 + psycopg2). Async endpoints
call it through ``asyncio.to_thread`` so the FastAPI event loop keeps
serving other requests. The batch endpoint fans out up to N calls with
``asyncio.gather``.
"""

from __future__ import annotations

import asyncio
from statistics import median
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_session
from app.scoring.engine import score_site
from app.scoring.models import SuitabilityReport
from app.scoring.resolver import ResolveError, resolve_parcel

router = APIRouter()

BATCH_MAX = 50
DEFAULT_CONFIG = "ma-eea-2026-v1"

ResolutionMode = Literal["contains", "nearest", "esmp_anchored"]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class ScoreRequest(BaseModel):
    address: str = Field(..., min_length=3)
    project_type: str = "generic"
    config_version: str = DEFAULT_CONFIG


class ScoreBatchRequest(BaseModel):
    addresses: list[str] = Field(..., min_length=1, max_length=BATCH_MAX)
    project_type: str = "generic"
    config_version: str = DEFAULT_CONFIG


class ScoreEnvelope(BaseModel):
    report_id: int
    address: str
    resolution_mode: ResolutionMode
    report: SuitabilityReport


class ScoreBatchItem(BaseModel):
    address: str
    ok: bool
    report_id: int | None = None
    resolution_mode: ResolutionMode | None = None
    total_score: float | None = None
    bucket: str | None = None
    error: str | None = None


class ScoreBatchSummary(BaseModel):
    n: int
    n_ok: int
    median_score: float | None = None
    bucket_counts: dict[str, int]


class ScoreBatchResponse(BaseModel):
    summary: ScoreBatchSummary
    items: list[ScoreBatchItem]


# ---------------------------------------------------------------------------
# Core scoring (sync; wrapped with to_thread for async callers)
# ---------------------------------------------------------------------------
def _score_and_persist(req: ScoreRequest) -> ScoreEnvelope:
    """Open a fresh session, resolve + score + persist. One call = one tx."""
    with SessionLocal() as session:
        try:
            loc_id, mode = resolve_parcel(session, req.address)
        except ResolveError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        report = score_site(
            session,
            parcel_id=loc_id,
            project_type=req.project_type,
            config_version=req.config_version,
        )

        report_id = session.execute(
            text(
                """
                INSERT INTO score_history (
                    parcel_loc_id, address, config_version,
                    total_score, bucket, report
                ) VALUES (
                    :pid, :addr, :cfg, :total, :bucket, CAST(:report AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "pid": report.parcel_id,
                "addr": req.address,
                "cfg": report.config_version,
                "total": report.total_score,
                "bucket": report.bucket,
                "report": report.model_dump_json(),
            },
        ).scalar_one()
        session.commit()

    return ScoreEnvelope(
        report_id=report_id,
        address=req.address,
        resolution_mode=mode,
        report=report,
    )


# ---------------------------------------------------------------------------
# POST /score
# ---------------------------------------------------------------------------
@router.post("/score", response_model=ScoreEnvelope)
async def post_score(req: ScoreRequest) -> ScoreEnvelope:
    return await asyncio.to_thread(_score_and_persist, req)


# ---------------------------------------------------------------------------
# POST /score/batch
# ---------------------------------------------------------------------------
async def _score_one_for_batch(
    address: str, project_type: str, config_version: str
) -> ScoreBatchItem:
    req = ScoreRequest(
        address=address, project_type=project_type, config_version=config_version
    )
    try:
        env = await asyncio.to_thread(_score_and_persist, req)
    except HTTPException as e:
        return ScoreBatchItem(address=address, ok=False, error=str(e.detail))
    except Exception as e:  # pragma: no cover — guard against any scoring crash
        return ScoreBatchItem(address=address, ok=False, error=f"{type(e).__name__}: {e}")
    return ScoreBatchItem(
        address=address,
        ok=True,
        report_id=env.report_id,
        resolution_mode=env.resolution_mode,
        total_score=env.report.total_score,
        bucket=env.report.bucket,
    )


@router.post("/score/batch", response_model=ScoreBatchResponse)
async def post_score_batch(req: ScoreBatchRequest) -> ScoreBatchResponse:
    if len(req.addresses) > BATCH_MAX:
        raise HTTPException(422, f"batch size capped at {BATCH_MAX}")
    tasks = [
        _score_one_for_batch(a, req.project_type, req.config_version)
        for a in req.addresses
    ]
    items = await asyncio.gather(*tasks)

    # Rank by score desc; failures sink to the bottom.
    items.sort(key=lambda i: (i.ok, i.total_score or -1.0), reverse=True)

    ok_scores = [i.total_score for i in items if i.ok and i.total_score is not None]
    buckets: dict[str, int] = {}
    for i in items:
        if i.bucket:
            buckets[i.bucket] = buckets.get(i.bucket, 0) + 1
    return ScoreBatchResponse(
        summary=ScoreBatchSummary(
            n=len(items),
            n_ok=sum(1 for i in items if i.ok),
            median_score=float(median(ok_scores)) if ok_scores else None,
            bucket_counts=buckets,
        ),
        items=items,
    )


# ---------------------------------------------------------------------------
# GET /report/{report_id}
# ---------------------------------------------------------------------------
@router.get("/report/{report_id}", response_model=SuitabilityReport)
def get_report(report_id: int, session: Session = Depends(get_session)) -> SuitabilityReport:
    row = session.execute(
        text(
            "SELECT report FROM score_history WHERE id = :rid"
        ),
        {"rid": report_id},
    ).scalar()
    if row is None:
        raise HTTPException(404, f"report {report_id} not found")
    return SuitabilityReport.model_validate(row)


# ---------------------------------------------------------------------------
# GET /parcel/{parcel_id}/geojson
# ---------------------------------------------------------------------------
@router.get("/parcel/{parcel_id}/geojson")
def get_parcel_geojson(
    parcel_id: str, session: Session = Depends(get_session)
) -> dict:
    row = session.execute(
        text(
            """
            SELECT loc_id, site_addr, town_name, city, total_val, lot_size,
                   ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geom
            FROM parcels
            WHERE loc_id = :pid
            """
        ),
        {"pid": parcel_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, f"parcel {parcel_id!r} not found")
    import json

    return {
        "type": "Feature",
        "geometry": json.loads(row["geom"]),
        "properties": {
            "loc_id": row["loc_id"],
            "site_addr": row["site_addr"],
            "town_name": row["town_name"],
            "city": row["city"],
            "total_val": row["total_val"],
            "lot_size": row["lot_size"],
        },
    }
