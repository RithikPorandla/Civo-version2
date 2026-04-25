"""Candidate site discovery endpoints.

Routes
------
- GET /esmp-projects                       — list every ESMP project (for the discover UI picker)
- GET /esmp-projects/{project_id}          — anchor details for one project
- GET /esmp-projects/{project_id}/candidates
    ?project_type=X&radius_m=5000&min_acres=...&max_acres=...&limit=10
  Returns ranked candidate parcels near the anchor.

The endpoint lives separately from /score so the scoring API stays
focused on single-parcel evaluation; candidate discovery is its own
batch-ish workflow.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.candidate_finder import find_candidate_sites

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class EsmpAnchor(BaseModel):
    id: int
    project_name: str
    project_type: str | None
    mw: float | None
    municipality: str | None
    source_filing: str
    siting_status: str | None
    utility: str  # Eversource / National Grid / Unitil — derived from source_filing
    lat: float
    lon: float


class CandidateSiteOut(BaseModel):
    parcel_id: str
    site_addr: str | None
    town_name: str | None
    lot_size_acres: float | None
    distance_to_anchor_m: float
    distance_to_anchor_mi: float
    use_code: str | None
    total_val: int | None
    total_score: float | None
    bucket: str | None
    primary_constraint: str | None
    composite_rank: float


class CandidateSearchResponse(BaseModel):
    anchor: dict[str, Any]
    project_type: str
    radius_m: float
    min_acres: float
    max_acres: float
    config_version: str
    pre_filter_count: int
    scored_count: int
    candidates: list[CandidateSiteOut]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_UTILITY_BY_FILING = {
    "DPU 24-10": "Eversource",
    "DPU 24-11": "National Grid",
    "DPU 24-12": "Unitil",
}


def _utility(source_filing: str | None) -> str:
    if not source_filing:
        return "Unknown"
    for prefix, name in _UTILITY_BY_FILING.items():
        if source_filing.startswith(prefix):
            return name
    return "Unknown"


# ---------------------------------------------------------------------------
# GET /esmp-projects
# ---------------------------------------------------------------------------
@router.get("/esmp-projects")
def list_esmp_projects(
    utility: str | None = Query(None, description="Filter by utility — Eversource / National Grid / Unitil"),
    siting_status: str | None = Query(None),
    session: Session = Depends(get_session),
) -> list[EsmpAnchor]:
    rows = (
        session.execute(
            text(
                """
                SELECT id, project_name, project_type, mw, municipality,
                       source_filing, siting_status,
                       ST_X(ST_Transform(geom, 4326)) AS lon,
                       ST_Y(ST_Transform(geom, 4326)) AS lat
                FROM esmp_projects
                ORDER BY municipality NULLS LAST, project_name
                """
            )
        )
        .mappings()
        .all()
    )
    out: list[EsmpAnchor] = []
    for r in rows:
        u = _utility(r["source_filing"])
        if utility and u.lower() != utility.lower():
            continue
        if siting_status and (r["siting_status"] or "").lower() != siting_status.lower():
            continue
        out.append(
            EsmpAnchor(
                id=r["id"],
                project_name=r["project_name"],
                project_type=r["project_type"],
                mw=float(r["mw"]) if r["mw"] is not None else None,
                municipality=r["municipality"],
                source_filing=r["source_filing"],
                siting_status=r["siting_status"],
                utility=u,
                lat=r["lat"],
                lon=r["lon"],
            )
        )
    return out


# ---------------------------------------------------------------------------
# GET /esmp-projects/{project_id}/candidates
# ---------------------------------------------------------------------------
@router.get("/esmp-projects/{project_id}/candidates", response_model=CandidateSearchResponse)
def get_candidate_sites(
    project_id: int,
    project_type: str = Query(..., description="bess_standalone | solar_ground_mount | ..."),
    radius_m: float = Query(5000.0, ge=100.0, le=25000.0),
    min_acres: float | None = Query(None, ge=0.0),
    max_acres: float | None = Query(None, ge=0.0),
    limit: int = Query(10, ge=1, le=50),
    score_pool_size: int = Query(15, ge=1, le=30),
    session: Session = Depends(get_session),
) -> CandidateSearchResponse:
    try:
        result = find_candidate_sites(
            session,
            project_type=project_type,
            anchor_project_id=project_id,
            radius_m=radius_m,
            min_acres=min_acres,
            max_acres=max_acres,
            score_pool_size=score_pool_size,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e

    # Attach utility label to the anchor for UI convenience.
    anchor = dict(result.anchor)
    if "source_filing" in anchor:
        anchor["utility"] = _utility(anchor["source_filing"])

    candidates_out = [
        CandidateSiteOut(
            parcel_id=c.parcel_id,
            site_addr=c.site_addr,
            town_name=c.town_name,
            lot_size_acres=c.lot_size_acres,
            distance_to_anchor_m=round(c.distance_to_anchor_m, 1),
            distance_to_anchor_mi=round(c.distance_to_anchor_m / 1609.0, 2),
            use_code=c.use_code,
            total_val=c.total_val,
            total_score=c.total_score,
            bucket=c.bucket,
            primary_constraint=c.primary_constraint,
            composite_rank=round(c.composite_rank, 2),
        )
        for c in result.candidates
    ]

    return CandidateSearchResponse(
        anchor=anchor,
        project_type=result.project_type,
        radius_m=result.radius_m,
        min_acres=result.min_acres,
        max_acres=result.max_acres,
        config_version=result.config_version,
        pre_filter_count=result.pre_filter_count,
        scored_count=result.scored_count,
        candidates=candidates_out,
    )
