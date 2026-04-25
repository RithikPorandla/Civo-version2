"""Municipality + project-type bylaws API.

Routes
------
- GET /municipalities                                    — list every seeded town
- GET /municipality/{town_id}                            — full town record
- GET /municipality/{town_id}/bylaws/{project_type}      — one project type's bylaws

Project type codes
------------------
solar_ground_mount | bess | substation | wind | transmission
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session

router = APIRouter()

ProjectTypeCode = Literal[
    "solar_ground_mount",
    "solar_rooftop",
    "solar_canopy",
    "bess_standalone",
    "bess_colocated",
    "substation",
    "transmission",
    "ev_charging",
]


def _moratorium_active(moratoriums: dict | None) -> bool:
    if not moratoriums:
        return False
    for m in moratoriums.values():
        if m.get("active") is True:
            return True
        start = m.get("start_date")
        end = m.get("end_date")
        if start and not end:
            return True
        if start and end:
            try:
                if date.fromisoformat(str(end)) > date.today():
                    return True
            except ValueError:
                pass
    return False


class MunicipalitySummary(BaseModel):
    town_id: int
    town_name: str
    project_types: list[str]
    last_refreshed_at: str | None = None
    moratorium_active: bool = False
    moratoriums: dict | None = None


class MunicipalityDetail(BaseModel):
    town_id: int
    town_name: str
    county: str | None = None
    project_type_bylaws: dict
    last_refreshed_at: str | None = None
    moratorium_active: bool = False
    moratoriums: dict | None = None


@router.get("/municipalities", response_model=list[MunicipalitySummary])
def list_municipalities(session: Session = Depends(get_session)) -> list[MunicipalitySummary]:
    rows = (
        session.execute(
            text(
                """
                SELECT town_id, town_name, project_type_bylaws, last_refreshed_at, moratoriums
                FROM municipalities
                WHERE project_type_bylaws <> '{}'::jsonb
                ORDER BY town_name
                """
            )
        )
        .mappings()
        .all()
    )
    return [
        MunicipalitySummary(
            town_id=r["town_id"],
            town_name=r["town_name"],
            project_types=sorted((r["project_type_bylaws"] or {}).keys()),
            last_refreshed_at=r["last_refreshed_at"].isoformat() if r["last_refreshed_at"] else None,
            moratorium_active=_moratorium_active(r["moratoriums"]),
            moratoriums=r["moratoriums"],
        )
        for r in rows
    ]


@router.get("/municipality/{town_id}", response_model=MunicipalityDetail)
def get_municipality(
    town_id: int, session: Session = Depends(get_session)
) -> MunicipalityDetail:
    row = (
        session.execute(
            text(
                """
                SELECT town_id, town_name, county, project_type_bylaws,
                       last_refreshed_at, moratoriums
                FROM municipalities
                WHERE town_id = :tid
                """
            ),
            {"tid": town_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, f"municipality {town_id} not found")
    return MunicipalityDetail(
        town_id=row["town_id"],
        town_name=row["town_name"],
        county=row["county"],
        project_type_bylaws=row["project_type_bylaws"] or {},
        last_refreshed_at=row["last_refreshed_at"].isoformat() if row["last_refreshed_at"] else None,
        moratorium_active=_moratorium_active(row["moratoriums"]),
        moratoriums=row["moratoriums"],
    )


@router.get("/municipality/{town_id}/bylaws/{project_type}")
def get_project_type_bylaws(
    town_id: int,
    project_type: ProjectTypeCode,
    session: Session = Depends(get_session),
) -> dict:
    row = (
        session.execute(
            text(
                """
                SELECT town_name, project_type_bylaws -> :pt AS bylaws
                FROM municipalities
                WHERE town_id = :tid
                """
            ),
            {"tid": town_id, "pt": project_type},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, f"municipality {town_id} not found")
    if not row["bylaws"]:
        raise HTTPException(
            404, f"no bylaws seeded for project_type={project_type} in {row['town_name']}"
        )
    return {
        "town_id": town_id,
        "town_name": row["town_name"],
        "project_type": project_type,
        "bylaws": row["bylaws"],
    }
