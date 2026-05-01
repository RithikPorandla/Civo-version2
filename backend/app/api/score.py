"""Score API — address-in, SuitabilityReport-out.

Routes
------
- POST /score                    — one address, one report
- POST /score/batch              — up to 50 addresses concurrently
- GET  /report/{report_id}       — re-read a persisted report by id
- GET  /parcel/{parcel_id}/geojson  — parcel polygon in WGS84 for maps

Concurrency
-----------
The scoring engine is synchronous (GeoAlchemy2 + psycopg2). Async endpoints
call it through ``asyncio.to_thread`` so the FastAPI event loop keeps
serving other requests. The batch endpoint fans out up to N calls with
``asyncio.gather``.
"""

from __future__ import annotations

import asyncio
import json
import time
from statistics import median
from typing import Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_session
from app.scoring.engine import score_site
from app.scoring.models import SuitabilityReport
from app.scoring.resolver import ResolveError, resolve_parcel_detailed
from app.services.link_health import enrich_citations_in_place
from app.services.mitigation_costs import estimate_mitigation_costs
from app.services.site_vision import analyze_site

router = APIRouter()

BATCH_MAX = 50
DEFAULT_CONFIG = "ma-eea-2026-v1"

ResolutionMode = Literal["contains", "nearest", "esmp_anchored", "addr_match"]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class ScoreRequest(BaseModel):
    address: str = Field(..., min_length=3)
    project_type: str = "generic"
    config_version: str = DEFAULT_CONFIG


class ScoreBatchRequest(BaseModel):
    addresses: list[str] = Field(..., min_length=1, max_length=BATCH_MAX)
    project_type: str = "generic"
    config_version: str = DEFAULT_CONFIG


class ScoreEnvelope(BaseModel):
    report_id: int
    address: str
    resolution_mode: ResolutionMode
    report: SuitabilityReport


class ScoreBatchItem(BaseModel):
    address: str
    ok: bool
    report_id: int | None = None
    resolution_mode: ResolutionMode | None = None
    total_score: float | None = None
    bucket: str | None = None
    error: str | None = None


class ScoreBatchSummary(BaseModel):
    n: int
    n_ok: int
    median_score: float | None = None
    bucket_counts: dict[str, int]


class ScoreBatchResponse(BaseModel):
    summary: ScoreBatchSummary
    items: list[ScoreBatchItem]


# ---------------------------------------------------------------------------
# Core scoring (sync; wrapped with to_thread for async callers)
# ---------------------------------------------------------------------------
def _score_and_persist(req: ScoreRequest) -> ScoreEnvelope:
    """Open a fresh session, resolve + score + persist. One call = one tx."""
    with SessionLocal() as session:
        try:
            resolved = resolve_parcel_detailed(
                session, req.address, project_type=req.project_type
            )
        except ResolveError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        report = score_site(
            session,
            parcel_id=resolved.loc_id,
            project_type=req.project_type,
            config_version=req.config_version,
        )

        # Stash resolution metadata INSIDE the report JSONB so GET /report/{id}
        # can surface it later without a schema change. The SuitabilityReport
        # pydantic is permissive about unknown keys in the raw JSON, but we
        # attach after model_dump to avoid model-layer churn.
        report_dict = report.model_dump(mode="json")
        report_dict["resolution"] = {
            "mode": resolved.resolution_mode,
            "original_query": resolved.original_query,
            "formatted_address": resolved.formatted_address,
            "resolved_site_addr": resolved.resolved_site_addr,
            "resolved_town": resolved.resolved_town,
            "distance_m": round(resolved.distance_m, 1),
        }

        report_id = session.execute(
            text(
                """
                INSERT INTO score_history (
                    parcel_loc_id, address, config_version,
                    total_score, bucket, report
                ) VALUES (
                    :pid, :addr, :cfg, :total, :bucket, CAST(:report AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "pid": report.parcel_id,
                "addr": req.address,
                "cfg": report.config_version,
                "total": report.total_score,
                "bucket": report.bucket,
                "report": json.dumps(report_dict),
            },
        ).scalar_one()
        session.commit()

    # Link-health enrichment is deferred — it probes external URLs (8s
    # timeout each) and must not block the score response. The GET
    # /report/{id} path serves enriched citations once the cache warms.
    return ScoreEnvelope(
        report_id=report_id,
        address=req.address,
        resolution_mode=cast(ResolutionMode, resolved.resolution_mode),
        report=SuitabilityReport.model_validate(report_dict),
    )


# ---------------------------------------------------------------------------
# Background link-health warmer
# ---------------------------------------------------------------------------
def _warm_link_health(report_id: int) -> None:
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT report FROM score_history WHERE id = :rid"),
            {"rid": report_id},
        ).scalar()
        if row is None:
            return
        enrich_citations_in_place(session, row)
        session.execute(
            text("UPDATE score_history SET report = CAST(:r AS jsonb) WHERE id = :rid"),
            {"r": json.dumps(row), "rid": report_id},
        )
        session.commit()


# ---------------------------------------------------------------------------
# POST /score
# ---------------------------------------------------------------------------
@router.post("/score", response_model=ScoreEnvelope)
async def post_score(req: ScoreRequest, bg: BackgroundTasks) -> ScoreEnvelope:
    envelope = await asyncio.to_thread(_score_and_persist, req)
    bg.add_task(asyncio.to_thread, _warm_link_health, envelope.report_id)
    return envelope


# ---------------------------------------------------------------------------
# POST /score/batch
# ---------------------------------------------------------------------------
async def _score_one_for_batch(
    address: str, project_type: str, config_version: str
) -> ScoreBatchItem:
    req = ScoreRequest(address=address, project_type=project_type, config_version=config_version)
    try:
        env = await asyncio.to_thread(_score_and_persist, req)
    except HTTPException as e:
        return ScoreBatchItem(address=address, ok=False, error=str(e.detail))
    except Exception as e:  # pragma: no cover — guard against any scoring crash
        return ScoreBatchItem(address=address, ok=False, error=f"{type(e).__name__}: {e}")
    return ScoreBatchItem(
        address=address,
        ok=True,
        report_id=env.report_id,
        resolution_mode=env.resolution_mode,
        total_score=env.report.total_score,
        bucket=env.report.bucket,
    )


@router.post("/score/batch", response_model=ScoreBatchResponse)
async def post_score_batch(req: ScoreBatchRequest) -> ScoreBatchResponse:
    if len(req.addresses) > BATCH_MAX:
        raise HTTPException(422, f"batch size capped at {BATCH_MAX}")
    tasks = [_score_one_for_batch(a, req.project_type, req.config_version) for a in req.addresses]
    items = await asyncio.gather(*tasks)

    # Rank by score desc; failures sink to the bottom.
    items.sort(key=lambda i: (i.ok, i.total_score or -1.0), reverse=True)

    ok_scores = [i.total_score for i in items if i.ok and i.total_score is not None]
    buckets: dict[str, int] = {}
    for i in items:
        if i.bucket:
            buckets[i.bucket] = buckets.get(i.bucket, 0) + 1
    return ScoreBatchResponse(
        summary=ScoreBatchSummary(
            n=len(items),
            n_ok=sum(1 for i in items if i.ok),
            median_score=float(median(ok_scores)) if ok_scores else None,
            bucket_counts=buckets,
        ),
        items=items,
    )


# ---------------------------------------------------------------------------
# GET /report/{report_id}
# ---------------------------------------------------------------------------
@router.get("/report/{report_id}", response_model=SuitabilityReport)
def get_report(report_id: str, session: Session = Depends(get_session)) -> SuitabilityReport:
    # Accept both integer DB id and parcel loc_id (e.g. "F_756553_2967761")
    if report_id.lstrip("-").isdigit():
        row = session.execute(
            text("SELECT report FROM score_history WHERE id = :rid"),
            {"rid": int(report_id)},
        ).scalar()
    else:
        # Loc_id path — return the most recent report for that parcel
        row = session.execute(
            text(
                "SELECT report FROM score_history WHERE parcel_loc_id = :lid"
                " ORDER BY id DESC LIMIT 1"
            ),
            {"lid": report_id},
        ).scalar()
    if row is None:
        raise HTTPException(404, f"report {report_id!r} not found")
    enrich_citations_in_place(session, row)
    return SuitabilityReport.model_validate(row)


# ---------------------------------------------------------------------------
# GET /parcel/{parcel_id}/geojson
# ---------------------------------------------------------------------------
@router.get("/parcel/{parcel_id}/geojson")
def get_parcel_geojson(parcel_id: str, session: Session = Depends(get_session)) -> dict:
    row = (
        session.execute(
            text(
                """
            SELECT loc_id, site_addr, town_name, city, zip, owner1, use_code, fy,
                   total_val, lot_size, raw,
                   ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geom
            FROM parcels
            WHERE loc_id = :pid
            """
            ),
            {"pid": parcel_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, f"parcel {parcel_id!r} not found")

    raw = row["raw"] or {}
    return {
        "type": "Feature",
        "geometry": json.loads(row["geom"]),
        "properties": {
            "loc_id": row["loc_id"],
            "site_addr": row["site_addr"],
            "town_name": row["town_name"],
            "city": row["city"],
            "zip": row["zip"],
            "owner1": row["owner1"],
            "use_code": row["use_code"],
            "fy": row["fy"],
            "total_val": row["total_val"],
            "lot_size": row["lot_size"],
            "zoning": raw.get("ZONING"),
            "style": raw.get("STYLE"),
            "bldg_val": raw.get("BLDG_VAL"),
            "land_val": raw.get("LAND_VAL"),
            "bld_area": raw.get("BLD_AREA"),
            "year_built": raw.get("YEAR_BUILT"),
            "ls_price": raw.get("LS_PRICE"),
            "ls_date": raw.get("LS_DATE"),
            "stories": raw.get("STORIES"),
        },
    }


# ---------------------------------------------------------------------------
# GET /parcel/{parcel_id}/mitigation-costs
# ---------------------------------------------------------------------------
@router.get("/parcel/{parcel_id}/mitigation-costs")
def get_parcel_mitigation_costs(
    parcel_id: str,
    project_type: str = Query(..., description="e.g. solar_ground_mount"),
    nameplate_kw: float | None = Query(None, ge=0),
    site_footprint_acres: float | None = Query(None, ge=0),
    wetland_impact_acres: float | None = Query(None, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    """Return a line-item mitigation cost estimate grounded in town precedents
    and industry benchmarks. Feeds the "Relevant precedents" panel on the
    Report page."""
    return estimate_mitigation_costs(
        session,
        parcel_id=parcel_id,
        project_type=project_type,
        nameplate_kw=nameplate_kw,
        site_footprint_acres=site_footprint_acres,
        estimated_wetland_impact_acres=wetland_impact_acres,
    )


# ---------------------------------------------------------------------------
# GET /parcel/{parcel_id}/site-analysis
# ---------------------------------------------------------------------------
@router.get("/parcel/{parcel_id}/site-analysis")
def get_parcel_site_analysis(
    parcel_id: str,
    force: bool = Query(False, description="Bypass cache — bill a fresh vision call."),
    session: Session = Depends(get_session),
) -> dict:
    """Claude-vision characterization of a parcel — impervious %, canopy %,
    detected buildings, narrative — reconciled against MassGIS LU/LC.

    Lazy: first hit for a parcel fires a vision call (~5-10s, ~$0.10-$0.30).
    Subsequent hits return the cached row instantly. Cache key is
    (parcel_loc_id, vision_version) so bumping the prompt invalidates.
    """
    try:
        result = analyze_site(session, parcel_id, force=force)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"vision extraction failed: {e}") from e
    return result.model_dump(mode="json")


# ---------------------------------------------------------------------------
# GET /parcel/{parcel_id}/moratoriums
# ---------------------------------------------------------------------------
@router.get("/parcel/{parcel_id}/moratoriums")
def get_parcel_moratoriums(
    parcel_id: str, session: Session = Depends(get_session)
) -> dict:
    """Return any active moratoriums in the parcel's town, keyed by project
    type. Shape mirrors municipalities.moratoriums JSONB."""
    row = (
        session.execute(
            text(
                """
                SELECT m.town_id, m.town_name, m.moratoriums
                FROM parcels p
                JOIN municipalities m ON m.town_id = p.town_id
                WHERE p.loc_id = :pid
                """
            ),
            {"pid": parcel_id},
        )
        .mappings()
        .first()
    )
    if not row:
        # No municipality row — not an error; just return empty.
        return {"town_id": None, "town_name": None, "moratoriums": {}}
    mors = row["moratoriums"] or {}
    # Filter out the research-agent's _citations side-channel if present.
    filtered = {k: v for k, v in mors.items() if not k.startswith("_")}
    return {
        "town_id": row["town_id"],
        "town_name": row["town_name"],
        "moratoriums": filtered,
    }


# ---------------------------------------------------------------------------
# GET /parcel/{parcel_id}/precedents
# ---------------------------------------------------------------------------
@router.get("/parcel/{parcel_id}/precedents")
def get_parcel_precedents(
    parcel_id: str,
    limit: int = Query(5, ge=1, le=25),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Return recent ConCom/Planning precedents for the parcel's town.

    Phase 5 wiring: retrieval is filter-based (same town). Vector
    similarity comes when the embeddings backend is chosen.
    """
    rows = (
        session.execute(
            text(
                """
            SELECT pr.id, pr.docket, pr.project_type, pr.project_address,
                   pr.applicant, pr.decision, pr.decision_date, pr.filing_date,
                   pr.meeting_body, pr.source_url, pr.full_text, pr.confidence,
                   pr.created_at
            FROM precedents pr
            JOIN parcels p ON p.town_id = pr.town_id
            WHERE p.loc_id = :pid
            ORDER BY COALESCE(pr.decision_date, pr.filing_date, pr.created_at) DESC
            LIMIT :lim
            """
            ),
            {"pid": parcel_id, "lim": limit},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /parcel/{parcel_id}/overlays
# ---------------------------------------------------------------------------
OVERLAY_MAX_FEATURES = 500
OVERLAY_CACHE_TTL_S = 3600
_overlay_cache: dict[tuple[str, int], tuple[float, dict]] = {}


def _overlay_cache_get(key: tuple[str, int]) -> dict | None:
    hit = _overlay_cache.get(key)
    if not hit:
        return None
    ts, payload = hit
    if time.time() - ts > OVERLAY_CACHE_TTL_S:
        _overlay_cache.pop(key, None)
        return None
    return payload


def _overlay_cache_put(key: tuple[str, int], payload: dict) -> None:
    _overlay_cache[key] = (time.time(), payload)


# (layer_name, table, select_props_sql_expression). The SQL expression
# projects the raw row to a JSONB blob the frontend can drop straight into
# feature.properties without a second lookup.
_OVERLAY_SPECS: list[tuple[str, str, str]] = [
    (
        "esmp",
        "esmp_projects",
        (
            "jsonb_build_object("
            "'project_id', attrs->>'project_id', "
            "'name', project_name, "
            "'mw_added', mw, "
            "'target_isd', isd, "
            "'coordinate_confidence', coordinate_confidence, "
            "'siting_status', siting_status, "
            "'municipality', municipality)"
        ),
    ),
    (
        "biomap_core",
        "habitat_biomap_core",
        (
            "jsonb_build_object("
            "'BM_ID', COALESCE(attrs->>'COMPNAME', core_id, id::text), "
            "'TOWN', attrs->>'TOWN', "
            "'core_type', core_type)"
        ),
    ),
    (
        "biomap_cnl",
        "habitat_biomap_cnl",
        (
            "jsonb_build_object("
            "'BM_ID', COALESCE(attrs->>'COMPNAME', cnl_id, id::text), "
            "'TOWN', attrs->>'TOWN', "
            "'cnl_type', cnl_type)"
        ),
    ),
    (
        "nhesp_priority",
        "habitat_nhesp_priority",
        (
            "jsonb_build_object("
            "'PRIHAB_ID', COALESCE(priority_id, attrs->>'PRIHAB_ID', id::text), "
            "'HAB_DATE', attrs->>'HAB_DATE')"
        ),
    ),
    (
        "nhesp_estimated",
        "habitat_nhesp_estimated",
        (
            "jsonb_build_object("
            "'ESTHAB_ID', COALESCE(estimated_id, attrs->>'ESTHAB_ID', id::text), "
            "'HAB_DATE', attrs->>'HAB_DATE')"
        ),
    ),
    (
        "fema_flood",
        "flood_zones",
        (
            "jsonb_build_object("
            "'FLD_ZONE', fld_zone, "
            "'ZONE_SUBTY', zone_subty, "
            "'STATIC_BFE', static_bfe, "
            "'DFIRM_ID', dfirm_id)"
        ),
    ),
    (
        "wetlands",
        "wetlands",
        (
            "jsonb_build_object("
            "'WETCODE', COALESCE(attrs->>'WETCODE', iw_class), "
            "'iw_type', iw_type, "
            "'source', source)"
        ),
    ),
    (
        "article97",
        "article97",
        (
            "jsonb_build_object("
            "'site_name', site_name, "
            "'owner_type', owner_type, "
            "'owner_name', owner_name)"
        ),
    ),
]


@router.get("/parcel/{parcel_id}/overlays")
def get_parcel_overlays(
    parcel_id: str,
    radius_m: int = Query(
        2000, ge=500, le=10000, description="Buffer radius in meters (500-10000)"
    ),
    session: Session = Depends(get_session),
) -> dict:
    """Return every overlay feature that intersects the parcel + buffer.

    One FeatureCollection, WGS84, with a ``layer`` property on every
    feature so the frontend can style/filter without a second call.
    Truncated at :data:`OVERLAY_MAX_FEATURES` total features; truncation
    is surfaced in ``properties.truncated = true`` so the UI can tell
    the user to zoom in.
    """
    cache_key = (parcel_id, radius_m)
    cached = _overlay_cache_get(cache_key)
    if cached is not None:
        return cached

    parcel = (
        session.execute(
            text(
                """
            SELECT loc_id, site_addr, town_name, city, total_val, lot_size,
                   ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geom_4326,
                   ST_AsEWKT(geom) AS geom_ewkt,
                   ST_AsEWKT(ST_Buffer(geom, :r)) AS buffer_ewkt
            FROM parcels
            WHERE loc_id = :pid
            """
            ),
            {"pid": parcel_id, "r": radius_m},
        )
        .mappings()
        .first()
    )
    if not parcel:
        raise HTTPException(404, f"parcel {parcel_id!r} not found")

    features: list[dict] = []
    counts: dict[str, int] = {"parcel": 1}
    truncated = False
    remaining_budget = OVERLAY_MAX_FEATURES - 1  # reserve one slot for parcel

    # Parcel itself first for frontend convenience.
    features.append(
        {
            "type": "Feature",
            "geometry": json.loads(parcel["geom_4326"]),
            "properties": {
                "layer": "parcel",
                "loc_id": parcel["loc_id"],
                "site_addr": parcel["site_addr"],
                "town_name": parcel["town_name"],
                "city": parcel["city"],
                "total_val": parcel["total_val"],
                "lot_size": parcel["lot_size"],
            },
        }
    )

    for layer, table, props_expr in _OVERLAY_SPECS:
        if remaining_budget <= 0:
            truncated = True
            counts[layer] = 0
            continue
        rows = (
            session.execute(
                text(
                    f"""
                SELECT
                  ST_AsGeoJSON(ST_Transform(ST_MakeValid(geom), 4326)) AS geom,
                  {props_expr} AS props
                FROM {table}
                WHERE ST_Intersects(ST_MakeValid(geom), CAST(:buf AS geometry))
                LIMIT :lim
                """
                ),
                {"buf": parcel["buffer_ewkt"], "lim": remaining_budget + 1},
            )
            .mappings()
            .all()
        )
        added = 0
        for row in rows:
            if remaining_budget <= 0:
                truncated = True
                break
            geom = json.loads(row["geom"])
            props = dict(row["props"] or {})
            props["layer"] = layer
            features.append({"type": "Feature", "geometry": geom, "properties": props})
            remaining_budget -= 1
            added += 1
        counts[layer] = added
        if len(rows) > added:
            truncated = True

    payload = {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "parcel_id": parcel_id,
            "radius_m": radius_m,
            "truncated": truncated,
            "counts": counts,
            "feature_cap": OVERLAY_MAX_FEATURES,
        },
    }
    _overlay_cache_put(cache_key, payload)
    return payload
