"""Pydantic v2 schemas for the MA EEA Site Suitability report.

These are the contract between the scoring engine, the FastAPI response
serializer, and any downstream consumers (frontend, PDF generator).
Every field that can be cited MUST carry a ``SourceCitation`` so users
can click back to the MassGIS row that drove the number.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.scoring.parcel_classifier import ParcelClassification  # noqa: F401 — re-exported

CriterionStatus = Literal["ok", "flagged", "ineligible", "data_unavailable"]
Bucket = Literal["SUITABLE", "CONDITIONALLY SUITABLE", "CONSTRAINED"]


class LinkHealthInfo(BaseModel):
    """Runtime health signal attached to a citation at serve time.

    Populated by app.services.link_health — never by the scoring engine
    (which runs offline) nor by the agent. Frontend uses this to decide
    whether to render the canonical URL, a "archived ↗" fallback to the
    Wayback Machine, or a muted "link unavailable" state.
    """

    status: Literal["healthy", "broken"]
    status_code: int | None = None
    wayback_url: str | None = None
    final_url: str | None = None
    checked_at: str | None = None


class SourceCitation(BaseModel):
    """Pointer back to the exact dataset row that drove a claim."""

    dataset: str = Field(..., description="Human-readable dataset name")
    row_id: str | None = Field(default=None, description="PK / natural key for the underlying row")
    url: str | None = Field(default=None, description="Public URL for the dataset")
    detail: str | None = Field(default=None, description="Short free text, e.g. '14.2% overlap'")
    health: LinkHealthInfo | None = Field(
        default=None,
        description="Runtime health status. None when the URL hasn't been probed yet.",
    )


class CriterionScore(BaseModel):
    key: str = Field(..., description="Stable machine key, e.g. 'grid_alignment'")
    name: str = Field(..., description="Human-readable criterion name")
    weight: float = Field(..., ge=0.0, le=1.0)
    raw_score: float = Field(..., ge=0.0, le=10.0, description="0-10 criterion score")
    weighted_contribution: float = Field(
        ..., ge=0.0, le=100.0, description="raw_score * weight * 10 — sums to total_score"
    )
    status: CriterionStatus = "ok"
    finding: str = Field(..., description="2-4 sentence explanation shown to the user")
    citations: list[SourceCitation] = Field(default_factory=list)


class ExemptionCheck(BaseModel):
    """Result of checking a project against 225 CMR 29.07(1) exemptions.

    ``is_exempt=None`` when there isn't enough information to decide
    (e.g. capacity or footprint missing). In that case the UI should
    prompt the user to provide the missing fields rather than assume
    non-exempt. Never fabricate a boolean when the inputs don't support one.
    """

    is_exempt: bool | None = Field(
        default=None,
        description=(
            "True if the project qualifies for exemption under 225 CMR 29.07(1); "
            "False if it does not; None if inputs are insufficient."
        ),
    )
    reason: str | None = Field(
        default=None,
        description="Short, human-readable explanation (e.g. 'solar ≤ 25 kW AC').",
    )
    regulation_reference: str = Field(
        default="225 CMR 29.07(1)",
        description="The exemption rule this result is keyed to.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="When is_exempt is None, which input fields the caller needs to supply.",
    )


class ResolutionInfo(BaseModel):
    """How the scored parcel relates to the user's original query.

    Attached by /score and /report/{id} so the UI can show a
    transparency banner when the resolver had to snap from the typed
    address to a different parcel (nearest-match or ESMP-anchored).
    """

    mode: Literal["contains", "esmp_anchored", "nearest", "addr_match"]
    original_query: str
    formatted_address: str | None = None
    resolved_site_addr: str | None = None
    resolved_town: str | None = None
    distance_m: float = Field(
        default=0.0,
        description="Straight-line distance from geocoded point to resolved parcel, meters.",
    )


class SuitabilityReport(BaseModel):
    parcel_id: str
    address: str | None = None
    project_type: str = "generic"
    config_version: str
    methodology: str
    computed_at: datetime

    total_score: float = Field(..., ge=0.0, le=100.0)
    bucket: Bucket
    primary_constraint: str | None = Field(
        default=None, description="Criterion key driving the lowest sub-score"
    )
    ineligible_flags: list[str] = Field(
        default_factory=list,
        description="225 CMR 29.06 ineligibility layer keys that overlap this parcel",
    )

    # What kind of parcel this actually is — hospital, park, gov building, etc.
    # Derived from the MA assessor use_code on the L3 parcel record.
    parcel_classification: ParcelClassification | None = Field(
        default=None,
        description="Assessor use-code classification: what the parcel is and who owns it.",
    )

    criteria: list[CriterionScore]
    citations: list[SourceCitation] = Field(
        default_factory=list,
        description="Report-level citations (config, methodology, data limitations)",
    )
    resolution: ResolutionInfo | None = Field(
        default=None,
        description="Metadata about how the user query resolved to this parcel.",
    )
