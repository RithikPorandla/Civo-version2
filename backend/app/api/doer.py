"""DOER + exemption endpoints.

Routes
------
- GET  /towns/{town_id}/doer-status   — solar + BESS adoption + solar diff
- POST /exemption-check               — 225 CMR 29.07(1) check for a project spec

The overview endpoint (``/doer/adoption-overview``) is intentionally
deferred — with 5 seeded towns, a rollup is meaningless. It'll come
back when N ≥ 50 towns have adoption rows.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.doer.models import (
    DoerAdoptionDetail,
    DoerComparisonResult,
    DoerProjectType,
    DoerStatusResponse,
)
from app.scoring.models import ExemptionCheck
from app.services.doer_comparison import compare_solar_to_doer_model
from app.services.exemption_checker import check_exemption

router = APIRouter()

DOER_DEADLINE = date(2026, 11, 30)


# ---------------------------------------------------------------------------
# GET /towns/{town_id}/doer-status
# ---------------------------------------------------------------------------
@router.get("/towns/{town_id}/doer-status", response_model=DoerStatusResponse)
def get_town_doer_status(
    town_id: int, session: Session = Depends(get_session)
) -> DoerStatusResponse:
    muni = (
        session.execute(
            text(
                """
                SELECT town_id, town_name, project_type_bylaws
                FROM municipalities
                WHERE town_id = :tid
                """
            ),
            {"tid": town_id},
        )
        .mappings()
        .first()
    )
    if not muni:
        raise HTTPException(404, f"municipality {town_id} not found")

    # Active DOER models, keyed by project type.
    model_rows = (
        session.execute(
            text(
                """
                SELECT project_type, version, parsed_data, source_url
                FROM doer_model_bylaws
                WHERE state = 'MA'
                ORDER BY project_type, parsed_at DESC
                """
            )
        )
        .mappings()
        .all()
    )
    active_models: dict[str, dict] = {}
    for r in model_rows:
        active_models.setdefault(r["project_type"], dict(r))

    # Adoption rows for this town.
    adoption_rows = (
        session.execute(
            text(
                """
                SELECT project_type, adoption_status, adopted_date,
                       town_meeting_article, current_local_bylaw_url,
                       modification_summary, doer_circuit_rider,
                       doer_version_ref, source_url, source_type,
                       confidence, extracted_at
                FROM municipal_doer_adoption
                WHERE municipality_id = :tid
                """
            ),
            {"tid": town_id},
        )
        .mappings()
        .all()
    )
    adoption_by_type = {r["project_type"]: dict(r) for r in adoption_rows}

    # Solar: run comparison on demand; BESS: adoption only (deferred).
    solar_detail = _build_adoption_detail(
        project_type="solar",
        adoption=adoption_by_type.get("solar"),
        doer_model_row=active_models.get("solar"),
        town_project_bylaws=muni["project_type_bylaws"],
        run_comparison=True,
    )
    bess_detail = _build_adoption_detail(
        project_type="bess",
        adoption=adoption_by_type.get("bess"),
        doer_model_row=active_models.get("bess"),
        town_project_bylaws=muni["project_type_bylaws"],
        run_comparison=False,  # BESS comparison deferred to next sprint
    )

    days_remaining = max(0, (DOER_DEADLINE - date.today()).days)

    return DoerStatusResponse(
        town_id=muni["town_id"],
        town_name=muni["town_name"],
        solar=solar_detail,
        bess=bess_detail,
        deadline=DOER_DEADLINE,
        days_remaining=days_remaining,
    )


def _build_adoption_detail(
    project_type: DoerProjectType,
    adoption: dict | None,
    doer_model_row: dict | None,
    town_project_bylaws: dict,
    run_comparison: bool,
) -> DoerAdoptionDetail | None:
    if adoption is None and doer_model_row is None:
        return None

    # If the town has no adoption row but a DOER model exists, surface a
    # synthetic "unknown" detail so the UI always has something to render.
    if adoption is None:
        adoption = {
            "adoption_status": "unknown",
            "adopted_date": None,
            "town_meeting_article": None,
            "current_local_bylaw_url": None,
            "modification_summary": None,
            "doer_circuit_rider": None,
            "doer_version_ref": (doer_model_row or {}).get("version"),
            "source_url": (doer_model_row or {}).get("source_url", ""),
            "source_type": "manual_entry",
            "confidence": 0.0,
            "extracted_at": datetime.now(timezone.utc),
        }

    comparison: DoerComparisonResult | None = None
    if run_comparison and project_type == "solar" and doer_model_row:
        comparison = compare_solar_to_doer_model(
            town_project_bylaws, doer_model_row["parsed_data"]
        )

    safe_harbor = _derive_safe_harbor(adoption["adoption_status"], comparison)

    return DoerAdoptionDetail(
        project_type=project_type,
        adoption_status=adoption["adoption_status"],
        adopted_date=adoption.get("adopted_date"),
        town_meeting_article=adoption.get("town_meeting_article"),
        current_local_bylaw_url=adoption.get("current_local_bylaw_url"),
        modification_summary=adoption.get("modification_summary"),
        doer_circuit_rider=adoption.get("doer_circuit_rider"),
        doer_version_ref=adoption.get("doer_version_ref"),
        confidence=float(adoption.get("confidence") or 0.0),
        source_url=adoption["source_url"],
        source_type=adoption["source_type"],
        last_checked=adoption.get("extracted_at"),
        comparison=comparison,
        safe_harbor_status=safe_harbor,
    )


def _derive_safe_harbor(status: str, comparison: DoerComparisonResult | None) -> str:
    if status == "adopted":
        return "safe"
    if comparison and comparison.comparison_available:
        if comparison.dover_amendment_risk:
            return "at_risk"
        if comparison.deviation_counts.get("major", 0) > 0:
            return "at_risk"
        if comparison.deviation_counts.get("moderate", 0) == 0:
            return "safe"
    return "unknown"


# ---------------------------------------------------------------------------
# POST /exemption-check
# ---------------------------------------------------------------------------
class ExemptionCheckRequest(BaseModel):
    project_type: str = Field(
        ...,
        description="solar_ground_mount | solar_rooftop | solar_canopy | "
        "bess_standalone | bess_colocated | substation | transmission | ev_charging",
    )
    nameplate_capacity_kw: float | None = None
    site_footprint_acres: float | None = None
    is_behind_meter: bool = False
    is_accessory_use: bool = False
    in_existing_public_row: bool = False
    td_design_rating_kv: float | None = None


@router.post("/exemption-check", response_model=ExemptionCheck)
def post_exemption_check(req: ExemptionCheckRequest) -> ExemptionCheck:
    return check_exemption(
        project_type=req.project_type,
        nameplate_capacity_kw=req.nameplate_capacity_kw,
        site_footprint_acres=req.site_footprint_acres,
        is_behind_meter=req.is_behind_meter,
        is_accessory_use=req.is_accessory_use,
        in_existing_public_row=req.in_existing_public_row,
        td_design_rating_kv=req.td_design_rating_kv,
    )
