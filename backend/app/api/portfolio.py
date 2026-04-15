"""Portfolio API — persist a multi-parcel scoring run under a shareable slug.

Routes
------
- POST   /portfolio          — score N addresses, persist, return slug + items
- GET    /portfolio/{id}     — read back a stored portfolio
- DELETE /portfolio/{id}     — remove one (no auth; matches anonymous MVP)

Portfolios are denormalized snapshots. If the user re-scores a parcel
later, the portfolio keeps its original results until they explicitly
re-run. The ``config_version`` field preserves methodology reproducibility.
"""

from __future__ import annotations

import asyncio
import secrets
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.score import (
    BATCH_MAX,
    DEFAULT_CONFIG,
    ScoreBatchItem,
    _score_one_for_batch,
)
from app.db import get_session

router = APIRouter()

PORTFOLIO_ID_PREFIX = "port_"
PORTFOLIO_ID_ALPHABET = string.ascii_lowercase + string.digits


class PortfolioCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    addresses: list[str] = Field(..., min_length=1, max_length=BATCH_MAX)
    project_type: str = "generic"
    config_version: str = DEFAULT_CONFIG


class PortfolioItem(BaseModel):
    rank: int
    address: str
    parcel_id: str | None = None
    score_report_id: int | None = None
    total_score: float | None = None
    bucket: str | None = None
    resolution_mode: str | None = None
    ok: bool
    error: str | None = None


class PortfolioEnvelope(BaseModel):
    id: str
    state: str = "MA"
    name: str | None = None
    project_type: str | None = None
    config_version: str
    created_at: datetime
    scored_at: datetime
    items: list[PortfolioItem]


def _new_portfolio_id() -> str:
    slug = "".join(secrets.choice(PORTFOLIO_ID_ALPHABET) for _ in range(10))
    return f"{PORTFOLIO_ID_PREFIX}{slug}"


def _batch_item_to_portfolio_item(rank: int, bi: ScoreBatchItem) -> PortfolioItem:
    return PortfolioItem(
        rank=rank,
        address=bi.address,
        parcel_id=None,  # score_history has it; we skip a join for v1
        score_report_id=bi.report_id,
        total_score=bi.total_score,
        bucket=bi.bucket,
        resolution_mode=bi.resolution_mode,
        ok=bi.ok,
        error=bi.error,
    )


@router.post("/portfolio", response_model=PortfolioEnvelope)
async def post_portfolio(req: PortfolioCreateRequest) -> PortfolioEnvelope:
    tasks = [_score_one_for_batch(a, req.project_type, req.config_version) for a in req.addresses]
    batch_items = await asyncio.gather(*tasks)
    batch_items.sort(key=lambda i: (i.ok, i.total_score or -1.0), reverse=True)
    items = [_batch_item_to_portfolio_item(i + 1, bi) for i, bi in enumerate(batch_items)]

    # Resolve parcel_id per item (one round-trip).
    loc_ids_by_report: dict[int, str] = {}
    report_ids = [i.score_report_id for i in items if i.score_report_id]

    # Write + resolve in a single thread-hop to keep the event loop free.
    def _persist() -> tuple[str, datetime, datetime]:
        from app.db import SessionLocal

        pid = _new_portfolio_id()
        with SessionLocal() as session:
            if report_ids:
                rows = session.execute(
                    text("SELECT id, parcel_loc_id FROM score_history WHERE id = ANY(:ids)"),
                    {"ids": report_ids},
                ).mappings()
                for row in rows:
                    loc_ids_by_report[row["id"]] = row["parcel_loc_id"]
            scored_at = datetime.now(timezone.utc)
            items_json = [i.model_dump() for i in items]
            for it in items_json:
                if it["score_report_id"] in loc_ids_by_report:
                    it["parcel_id"] = loc_ids_by_report[it["score_report_id"]]
            session.execute(
                text(
                    """
                    INSERT INTO portfolios (
                        id, state, name, items, project_type, config_version, scored_at
                    ) VALUES (
                        :id, 'MA', :name, CAST(:items AS jsonb), :pt, :cfg, :scored_at
                    )
                    """
                ),
                {
                    "id": pid,
                    "name": req.name,
                    "items": __import__("json").dumps(items_json),
                    "pt": req.project_type,
                    "cfg": req.config_version,
                    "scored_at": scored_at,
                },
            )
            created_row = (
                session.execute(
                    text("SELECT created_at FROM portfolios WHERE id = :id"),
                    {"id": pid},
                )
                .mappings()
                .first()
            )
            session.commit()
            assert created_row is not None  # just inserted; row must exist
            return pid, created_row["created_at"], scored_at

    pid, created_at, scored_at = await asyncio.to_thread(_persist)
    # Patch parcel_id into the response envelope too.
    for it in items:
        if it.score_report_id in loc_ids_by_report:
            it.parcel_id = loc_ids_by_report[it.score_report_id]

    return PortfolioEnvelope(
        id=pid,
        name=req.name,
        project_type=req.project_type,
        config_version=req.config_version,
        created_at=created_at,
        scored_at=scored_at,
        items=items,
    )


@router.get("/portfolio/{portfolio_id}", response_model=PortfolioEnvelope)
def get_portfolio(portfolio_id: str, session: Session = Depends(get_session)) -> PortfolioEnvelope:
    row = (
        session.execute(
            text(
                """
            SELECT id, state, name, project_type, config_version,
                   created_at, scored_at, items
            FROM portfolios
            WHERE id = :id
            """
            ),
            {"id": portfolio_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, f"portfolio {portfolio_id!r} not found")
    return PortfolioEnvelope(
        id=row["id"],
        state=row["state"],
        name=row["name"],
        project_type=row["project_type"],
        config_version=row["config_version"],
        created_at=row["created_at"],
        scored_at=row["scored_at"],
        items=[PortfolioItem(**it) for it in (row["items"] or [])],
    )


@router.delete("/portfolio/{portfolio_id}", status_code=204)
def delete_portfolio(portfolio_id: str, session: Session = Depends(get_session)) -> None:
    res = session.execute(text("DELETE FROM portfolios WHERE id = :id"), {"id": portfolio_id})
    session.commit()
    if not res.rowcount:  # type: ignore[attr-defined]
        raise HTTPException(404, f"portfolio {portfolio_id!r} not found")
