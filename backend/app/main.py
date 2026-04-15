"""Civo FastAPI app."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.municipality import router as municipality_router
from app.api.portfolio import router as portfolio_router
from app.api.score import router as score_router
from app.db import get_session

app = FastAPI(title="Civo API", version="0.1.0")
app.include_router(score_router)
app.include_router(portfolio_router)
app.include_router(municipality_router)


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    """Report DB reachability, PostGIS / pgvector versions, and row counts."""
    out: dict = {
        "database": False,
        "postgis": None,
        "pgvector": None,
        "parcels_loaded": 0,
        "esmp_projects_loaded": 0,
        "municipalities_loaded": 0,
    }
    try:
        out["database"] = session.execute(text("SELECT 1")).scalar() == 1
        out["postgis"] = session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname='postgis'")
        ).scalar()
        out["pgvector"] = session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        ).scalar()
        out["parcels_loaded"] = session.execute(text("SELECT COUNT(*) FROM parcels")).scalar()
        out["esmp_projects_loaded"] = session.execute(
            text("SELECT COUNT(*) FROM esmp_projects")
        ).scalar()
        out["municipalities_loaded"] = session.execute(
            text("SELECT COUNT(*) FROM municipalities")
        ).scalar()
        out["status"] = (
            "ok" if out["database"] and out["postgis"] and out["pgvector"] else "degraded"
        )
    except Exception as e:  # pragma: no cover
        out["status"] = "error"
        out["error"] = str(e)
    return out
