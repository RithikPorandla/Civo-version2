"""Discover API — NL-powered site discovery endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.discovery_engine import DiscoveryFilters, run_discovery
from app.services.narrative_generator import generate_narrative
from app.services.query_interpreter import InterpretedQuery, interpret_query

router = APIRouter(prefix="/discover", tags=["discover"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class DiscoverRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(50, ge=1, le=200)


class FollowUpRequest(BaseModel):
    query_id: str
    follow_up: str = Field(..., min_length=1)
    limit: int = Field(50, ge=1, le=200)


class DiscoverResultItem(BaseModel):
    parcel_id: str
    site_addr: str | None
    town_name: str
    lot_size_acres: float | None
    lat: float
    lon: float
    total_score: float | None
    bucket: str | None
    primary_constraint: str | None
    in_biomap_core: bool
    in_nhesp_priority: bool
    in_flood_zone: bool
    in_wetlands: bool
    in_article97: bool
    moratorium_active: bool
    doer_status: str | None
    risk_multiplier: float
    ml_score: float | None = None
    blended_score: float | None = None


class InterpretedFilters(BaseModel):
    municipalities: list[str]
    sub_region: str | None
    min_acres: float | None
    max_acres: float | None
    exclude_layers: list[str]
    include_layers: list[str]
    doer_bess_status: str | None
    doer_solar_status: str | None
    project_type: str | None
    project_size_mw: float | None
    min_score: float | None
    sort_by: str


class DiscoverResponse(BaseModel):
    query_id: str
    intent_type: str
    interpreted_filters: InterpretedFilters
    results: list[DiscoverResultItem]
    narrative: str | None
    citations: list[dict[str, Any]]
    total_count: int
    confidence: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_response(
    interpreted: InterpretedQuery,
    results: list[dict[str, Any]],
    narrative: str | None,
    citations: list[dict[str, Any]],
) -> DiscoverResponse:
    items = [
        DiscoverResultItem(
            parcel_id=str(r["parcel_id"]),
            site_addr=r.get("site_addr"),
            town_name=r.get("town_name") or "",
            lot_size_acres=float(r["lot_size_acres"]) if r.get("lot_size_acres") is not None else None,
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            total_score=float(r["total_score"]) if r.get("total_score") is not None else None,
            bucket=r.get("bucket"),
            primary_constraint=r.get("primary_constraint"),
            in_biomap_core=bool(r.get("in_biomap_core")),
            in_nhesp_priority=bool(r.get("in_nhesp_priority")),
            in_flood_zone=bool(r.get("in_flood_zone")),
            in_wetlands=bool(r.get("in_wetlands")),
            in_article97=bool(r.get("in_article97")),
            moratorium_active=bool(r.get("moratorium_active")),
            doer_status=r.get("doer_status"),
            risk_multiplier=float(r.get("risk_multiplier") or 1.0),
            ml_score=float(r["ml_score"]) if r.get("ml_score") is not None else None,
            blended_score=float(r["blended_score"]) if r.get("blended_score") is not None else None,
        )
        for r in results
    ]
    return DiscoverResponse(
        query_id=str(uuid.uuid4()),
        intent_type=interpreted.intent_type,
        interpreted_filters=InterpretedFilters(
            municipalities=interpreted.municipalities,
            sub_region=interpreted.sub_region,
            min_acres=interpreted.min_acres,
            max_acres=interpreted.max_acres,
            exclude_layers=interpreted.exclude_layers,
            include_layers=interpreted.include_layers,
            doer_bess_status=interpreted.doer_bess_status,
            doer_solar_status=interpreted.doer_solar_status,
            project_type=interpreted.project_type,
            project_size_mw=interpreted.project_size_mw,
            min_score=interpreted.min_score,
            sort_by=interpreted.sort_by,
        ),
        results=items,
        narrative=narrative,
        citations=citations,
        total_count=len(items),
        confidence=interpreted.confidence,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=DiscoverResponse)
def discover(
    req: DiscoverRequest,
    session: Session = Depends(get_session),
) -> DiscoverResponse:
    """Main NL site-discovery endpoint. Classifies intent → runs PostGIS → narrates."""
    interpreted = interpret_query(req.query)
    filters = DiscoveryFilters.from_interpreted(interpreted, limit=req.limit)
    results = run_discovery(session, filters)
    narrative, citations = generate_narrative(interpreted, results)
    return _build_response(interpreted, results, narrative, citations)


@router.get("/suggestions")
def suggestions(
    q: str = Query("", description="Partial query string for autocomplete"),
) -> list[str]:
    """Query bar autocomplete suggestions."""
    defaults = [
        "Find parcels in EMA-North Metro West suitable for 5MW BESS, not in BioMap Core",
        "Solar sites in towns with DOER adoption, over 10 acres",
        "Parcels >10 acres, no habitat constraints, near Eversource ESMP",
        "Compare Acton vs Burlington for BESS permitting risk",
        "5MW BESS near EMA-North substations",
        "Towns in western MA with high ConCom solar approval rates",
        "Denied battery storage projects in Middlesex County 2024-2026",
        "Which EMA-South towns haven't started DOER BESS adoption?",
        "Ground-mount solar parcels in Cape Cod not in wetlands",
        "Parcels >5 acres near planned Eversource substations, score above 60",
    ]
    if not q:
        return defaults[:6]
    q_lower = q.lower()
    return [s for s in defaults if q_lower in s.lower()][:8]


@router.post("/followup", response_model=DiscoverResponse)
def followup(
    req: FollowUpRequest,
    session: Session = Depends(get_session),
) -> DiscoverResponse:
    """Refine a previous discovery query with a follow-up question."""
    interpreted = interpret_query(req.follow_up)
    filters = DiscoveryFilters.from_interpreted(interpreted, limit=req.limit)
    results = run_discovery(session, filters)
    narrative, citations = generate_narrative(interpreted, results)
    return _build_response(interpreted, results, narrative, citations)
