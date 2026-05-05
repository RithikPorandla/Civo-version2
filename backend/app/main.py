"""Civo FastAPI app."""

from __future__ import annotations

import os
import threading

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.data_sources import router as data_sources_router
from app.api.candidates import router as candidates_router
from app.api.discover import router as discover_router
from app.api.doer import router as doer_router
from app.api.municipality import router as municipality_router
from app.api.pdf import router as pdf_router
from app.api.portfolio import router as portfolio_router
from app.api.score import router as score_router
from app.db import SessionLocal, get_session
from app.services.jurisdiction_risk import refresh_all

app = FastAPI(title="Civo API", version="0.1.0")

_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(score_router)
app.include_router(pdf_router)
app.include_router(portfolio_router)
app.include_router(municipality_router)
app.include_router(doer_router)
app.include_router(candidates_router)
app.include_router(data_sources_router)
app.include_router(discover_router)


@app.on_event("startup")
def _refresh_jurisdiction_risk_on_startup() -> None:
    """Refresh town_jurisdiction_risk in a background thread at startup.

    Runs in a daemon thread so it never blocks the server from accepting
    requests. Takes ~1s for 11 towns; safe to re-run anytime data changes.
    """
    def _run() -> None:
        import time
        for attempt in range(3):
            try:
                with SessionLocal() as session:
                    n = refresh_all(session)
                    print(f"[jurisdiction_risk] refreshed {n} rows")
                return
            except Exception as e:
                if attempt < 2:
                    time.sleep(5)
                else:
                    print(f"[jurisdiction_risk] failed after 3 attempts: {e}")

    threading.Thread(target=_run, daemon=True).start()


@app.post("/admin/seed-bylaws", tags=["admin"])
def seed_bylaws_endpoint() -> dict:
    """Seed project_type_bylaws for all towns that exist in the municipalities table."""
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.seed_bylaws import TOWN_BYLAWS

    seeded, skipped = [], []
    with SessionLocal() as session:
        for town_name, bylaws in TOWN_BYLAWS.items():
            row = session.execute(
                text("SELECT town_id FROM municipalities WHERE UPPER(town_name) = UPPER(:tn) LIMIT 1"),
                {"tn": town_name},
            ).scalar()
            if row is None:
                skipped.append(town_name)
                continue
            session.execute(
                text("""
                    INSERT INTO municipalities (town_id, town_name, project_type_bylaws, last_refreshed_at)
                    VALUES (:tid, :tn, CAST(:b AS jsonb), NOW())
                    ON CONFLICT (town_id) DO UPDATE
                    SET project_type_bylaws = EXCLUDED.project_type_bylaws,
                        last_refreshed_at   = NOW()
                """),
                {"tid": row, "tn": town_name, "b": json.dumps(bylaws)},
            )
            seeded.append(town_name)
        session.commit()
    return {"seeded": seeded, "skipped": skipped}


@app.post("/admin/refresh-jurisdiction-risk", tags=["admin"])
def refresh_jurisdiction_risk() -> dict:
    """Manually trigger a jurisdiction risk refresh (e.g. after seeding new DOER data)."""
    with SessionLocal() as session:
        n = refresh_all(session)
    return {"rows_upserted": n}


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
