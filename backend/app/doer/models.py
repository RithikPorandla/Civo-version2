"""Pydantic contracts for the DOER adoption + comparison surfaces.

These are the wire format for `/towns/{town_id}/doer-status` and for the
frontend `DoerAlignmentStrip` / `DoerAlignmentCard` components. Every
deviation entry carries enough context (tier, severity, precedent) that
the UI can render the deep-drawer view without a second API round-trip.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

DoerProjectType = Literal["solar", "bess"]

AdoptionStatus = Literal["adopted", "in_progress", "not_started", "unknown"]

AdoptionSourceType = Literal[
    "town_website",
    "town_meeting_warrant",
    "agent_extraction",
    "manual_entry",
]

DeviationCategory = Literal[
    "process_severity",
    "uniform_treatment",
    "setback_delta",
    "acreage_cap_restriction",
    "deforestation_cap",
    "overlay_restriction",
    "missing_ineligibility_alignment",
    "decommissioning_surety_delta",
]

Severity = Literal["minor", "moderate", "major"]


class DoerDeviation(BaseModel):
    category: DeviationCategory
    severity: Severity
    tier_context: str = Field(
        ...,
        description="Which DOER tier bucket this deviation applies to (e.g. "
        "'Ground-Mount Small (0-25 kW)', or 'all tiers' for uniform town rules).",
    )
    town_value: str | None = Field(
        default=None,
        description="What the town's bylaw says for this field (human-readable).",
    )
    doer_value: str | None = Field(
        default=None, description="What the DOER model says (human-readable)."
    )
    summary: str = Field(..., description="One-sentence explanation for the UI.")
    dover_risk: bool = Field(
        default=False,
        description="True when the deviation is of a type the MA AG or courts "
        "have flagged as a potential Dover Amendment (M.G.L. c. 40A §3) violation.",
    )
    source_bylaw_ref: str | None = None


class DoerComparisonResult(BaseModel):
    """Structured diff of a town's bylaw for one project type vs the DOER model."""

    project_type: DoerProjectType
    comparison_available: bool = Field(
        ...,
        description="False when the town has no extracted bylaw data for this "
        "project type — UI should render 'not yet analyzed'.",
    )
    reason_unavailable: str | None = None
    deviations: list[DoerDeviation] = Field(default_factory=list)
    deviation_counts: dict[Severity, int] = Field(default_factory=dict)
    dover_amendment_risk: bool = Field(default=False)
    doer_version_compared: str | None = Field(
        default=None,
        description="The DOER model version this comparison was run against. "
        "Pinning this matters when DOER publishes a revised draft.",
    )


class DoerAdoptionDetail(BaseModel):
    project_type: DoerProjectType
    adoption_status: AdoptionStatus
    adopted_date: date | None = None
    town_meeting_article: str | None = None
    current_local_bylaw_url: str | None = None
    modification_summary: str | None = None
    doer_circuit_rider: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_url: str
    source_type: AdoptionSourceType
    last_checked: datetime | None = None
    doer_version_ref: str | None = Field(
        default=None,
        description="The DOER version this town adopted (if adopted). Lets us "
        "detect stale adoptions when DOER ships an update.",
    )
    comparison: DoerComparisonResult | None = None
    safe_harbor_status: Literal["safe", "at_risk", "unknown"] = Field(
        default="unknown",
        description="Derived: 'safe' if adopted OR comparison has no moderate/major "
        "deviations; 'at_risk' if there's a Dover Amendment risk flag; 'unknown' "
        "when comparison is unavailable.",
    )


class DoerStatusResponse(BaseModel):
    town_id: int
    town_name: str
    solar: DoerAdoptionDetail | None = None
    bess: DoerAdoptionDetail | None = None
    deadline: date = Field(
        default=date(2026, 11, 30),
        description="November 30, 2026 — statutory adoption deadline.",
    )
    days_remaining: int
    other_project_types_note: str = Field(
        default=(
            "No DOER model bylaw exists for wind, transmission/distribution, or "
            "anaerobic digestion. For these project types, local rules apply exclusively."
        )
    )
