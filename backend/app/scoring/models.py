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

CriterionStatus = Literal["ok", "flagged", "ineligible", "data_unavailable"]
Bucket = Literal["SUITABLE", "CONDITIONALLY SUITABLE", "CONSTRAINED"]


class SourceCitation(BaseModel):
    """Pointer back to the exact dataset row that drove a claim."""

    dataset: str = Field(..., description="Human-readable dataset name")
    row_id: str | None = Field(
        default=None, description="PK / natural key for the underlying row"
    )
    url: str | None = Field(default=None, description="Public URL for the dataset")
    detail: str | None = Field(
        default=None, description="Short free text, e.g. '14.2% overlap'"
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

    criteria: list[CriterionScore]
    citations: list[SourceCitation] = Field(
        default_factory=list,
        description="Report-level citations (config, methodology, data limitations)",
    )
