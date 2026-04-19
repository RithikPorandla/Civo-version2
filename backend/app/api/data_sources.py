"""GET /data-sources — public data provenance index.

Reads ``config/data_sources.yaml``, joins live row counts for any DB-backed
entry, and returns the structured list grouped by category. Public, no
auth — this is the trust artifact Civo points to when asked "what's behind
your scores?"

Why YAML and not the DB: the index is deliberately hand-curated. Every
source here has to be *explained* (what it feeds, why, which criterion),
not just enumerated. A migration-authored list would lose that context.
Row counts come from the DB so we don't have to manually refresh them.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[3]
YAML_PATH = REPO_ROOT / "config" / "data_sources.yaml"

Category = Literal["spatial", "regulatory", "municipal", "benchmark", "external"]
Status = Literal["ingested", "planned", "external"]

# Safelist of table names we allow to be row-counted. Protects against
# accidental injection via YAML if the file ever gets edited by an outsider.
_SAFE_TABLES: set[str] = {
    "parcels",
    "habitat_biomap_core",
    "habitat_biomap_cnl",
    "habitat_nhesp_priority",
    "habitat_nhesp_estimated",
    "flood_zones",
    "wetlands",
    "prime_farmland",
    "article97",
    "land_use",
    "massenviroscreen",
    "esmp_projects",
    "municipalities",
    "doer_model_bylaws",
    "municipal_doer_adoption",
    "precedents",
}

# Columns allowed in count_filter. Prevents a poisoned YAML from turning the
# COUNT query into something it shouldn't be.
_SAFE_FILTER_COLUMNS: set[str] = {
    "source_filing",
    "project_type",
    "siting_status",
}


def _build_where(filt: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Build a parameterized WHERE clause from a safelisted filter dict."""
    if not filt:
        return "", {}
    conds = []
    params: dict[str, str] = {}
    for col, val in filt.items():
        if col not in _SAFE_FILTER_COLUMNS:
            continue
        pname = f"f_{col}"
        conds.append(f"{col} = :{pname}")
        params[pname] = val
    if not conds:
        return "", {}
    return "WHERE " + " AND ".join(conds), params


class DataSource(BaseModel):
    id: str
    name: str
    agency: str
    category: Category
    url: str | None = None
    docket: str | None = None
    coverage: str | None = None
    used_by: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    count_filter: dict[str, str] | None = None
    row_count: int | None = None
    last_refreshed: str | None = None
    last_reviewed: str | None = None
    citation_format: str | None = None
    status: Status = "ingested"
    notes: str | None = None


class DataSourcesResponse(BaseModel):
    last_reviewed: str
    total_sources: int
    by_category: dict[str, int]
    sources: list[DataSource]


@lru_cache(maxsize=1)
def _load_raw() -> dict:
    """Parse the YAML once per process. Bump the Python process to reload."""
    return yaml.safe_load(YAML_PATH.read_text()) or {}


@router.get("/data-sources", response_model=DataSourcesResponse)
def list_data_sources(session: Session = Depends(get_session)) -> DataSourcesResponse:
    """Return the full data-provenance index with live row counts."""
    raw = _load_raw()
    raw_sources = raw.get("sources", [])

    enriched: list[DataSource] = []
    by_category: dict[str, int] = {}

    for entry in raw_sources:
        src = DataSource(**entry)
        by_category[src.category] = by_category.get(src.category, 0) + 1

        # Sum row counts across all safelisted tables for this source.
        # Optional `count_filter` narrows the COUNT to a subset — e.g. each
        # utility's ESMP projects filtered by source_filing, so three rows
        # backed by the shared esmp_projects table get three accurate counts.
        if src.tables and src.status == "ingested":
            total = 0
            any_counted = False
            where_clause, params = _build_where(src.count_filter or {})
            for t in src.tables:
                if t not in _SAFE_TABLES:
                    continue
                try:
                    total += session.execute(
                        text(f"SELECT COUNT(*) FROM {t} {where_clause}"), params
                    ).scalar_one()
                    any_counted = True
                except Exception:  # pragma: no cover — table missing / DB down
                    pass
            if any_counted:
                src.row_count = total

        enriched.append(src)

    return DataSourcesResponse(
        last_reviewed=raw.get("metadata", {}).get("last_reviewed", ""),
        total_sources=len(enriched),
        by_category=by_category,
        sources=enriched,
    )
