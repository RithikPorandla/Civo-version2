"""MA EEA Site Suitability scoring engine.

Public entry point: ``score_site(parcel_id, project_type, config_version)``.

Design notes
------------
- All spatial math runs against parcel polygons in EPSG:26986 (meters).
- Every criterion is a pure function of (session, parcel_context, config)
  so it can be unit-tested without the full engine.
- No fallbacks or silent defaults: if a required layer is missing for a
  parcel, the criterion returns ``status='data_unavailable'`` with a clear
  finding, and the engine scales the remaining weights proportionally so
  the total still lands in 0-100.
- Citations: each criterion contributes at least one citation that points
  back to a specific row or dataset. Report-level citations carry the
  config version and methodology.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.scoring.models import (
    Bucket,
    CriterionScore,
    CriterionStatus,
    SourceCitation,
    SuitabilityReport,
)

CONFIG_ROOT = Path(__file__).resolve().parents[3] / "config" / "scoring"

# MassGIS dataset URLs (for citations).
_MASSGIS_URLS = {
    "parcels": "https://www.mass.gov/info-details/massgis-data-property-tax-parcels",
    "biomap_core": "https://gis.data.mass.gov/maps/f78bb54093d743189779d0f9c833001b",
    "biomap_cnl": "https://www.arcgis.com/home/item.html?id=7d0e5b65e884473da40f7e4cd67c53c6",
    "nhesp_priority": "https://www.arcgis.com/home/item.html?id=a953ef7fe0744ef2b2a8fb49118c51c7",
    "nhesp_estimated": "https://www.arcgis.com/home/item.html?id=e99c0aae177247ae85636102db6ede5f",
    "fema_flood": "https://www.mass.gov/info-details/massgis-data-fema-national-flood-hazard-layer",
    "wetlands": "https://gis.data.mass.gov/search?q=massdep%20wetlands",
    "land_use": "https://www.mass.gov/info-details/massgis-data-2016-land-coverland-use",
    "prime_farmland": "https://gis.data.mass.gov/search?q=noaa%20soils",
    "massenviroscreen": "https://mass-eoeea.maps.arcgis.com/apps/instant/sidebar/index.html?appid=4be63e892a3d42d69334615a64095a39",
    "esmp": "https://eeaonline.eea.state.ma.us/DPU/Fileroom/dockets/get/?num=24-10",
    "regulation": "https://www.mass.gov/regulations/225-CMR-29-225-cmr-2900-small-clean-energy-infrastructure-facility-siting-and-permitting-draft-regulation",
}


class ScoringError(Exception):
    """Raised when scoring cannot proceed (e.g. unknown parcel)."""


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_config(config_version: str) -> dict:
    p = CONFIG_ROOT / f"{config_version}.yaml"
    if not p.exists():
        raise ScoringError(f"scoring config {config_version!r} not found at {p}")
    return yaml.safe_load(p.read_text())


# ---------------------------------------------------------------------------
# Interpolation helper
# ---------------------------------------------------------------------------
def _interp(anchors: list[list[float]], x: float) -> float:
    """Piecewise-linear interpolation across (x_i, y_i) anchors.

    Anchors must be strictly increasing in x. Values outside the range
    clamp to the endpoints. This is the single shared math across every
    criterion's raw-score curve so the YAML can tune thresholds without
    code changes.
    """
    if not anchors:
        raise ValueError("empty anchors")
    if x <= anchors[0][0]:
        return float(anchors[0][1])
    if x >= anchors[-1][0]:
        return float(anchors[-1][1])
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return float(y0)
            t = (x - x0) / (x1 - x0)
            return float(y0 + t * (y1 - y0))
    return float(anchors[-1][1])


# ---------------------------------------------------------------------------
# Parcel context
# ---------------------------------------------------------------------------
def _parcel_context(session: Session, parcel_id: str, buffer_m: float) -> dict[str, Any]:
    """Fetch the parcel's geometry, area, and a buffered analysis geometry.

    ``buffer_m`` comes from the scoring config, keyed on project_type.
    We materialize the buffered geometry and its area here so the
    sensitivity criteria can do ``ST_Intersection(parcel_buffer, habitat)``
    against the analysis zone rather than the raw parcel polygon.
    """
    row = (
        session.execute(
            text(
                """
            SELECT loc_id, site_addr, town_name, city,
                   ST_Area(geom) AS area_sqm,
                   ST_AsText(ST_Centroid(geom)) AS centroid_wkt,
                   ST_AsEWKT(geom) AS geom_ewkt,
                   ST_AsEWKT(ST_Buffer(geom, :buf)) AS buffer_ewkt,
                   ST_Area(ST_Buffer(geom, :buf)) AS buffer_area_sqm
            FROM parcels
            WHERE loc_id = :pid
            """
            ),
            {"pid": parcel_id, "buf": buffer_m},
        )
        .mappings()
        .first()
    )
    if not row:
        raise ScoringError(f"parcel {parcel_id!r} not found")
    out = dict(row)
    out["buffer_m"] = buffer_m
    return out


# ---------------------------------------------------------------------------
# Criterion 1: Grid Alignment
# ---------------------------------------------------------------------------
def _score_grid_alignment(session: Session, ctx: dict, cfg: dict) -> CriterionScore:
    c = cfg["criteria"]["grid_alignment"]
    row = (
        session.execute(
            text(
                """
            SELECT e.project_name, e.municipality, e.coordinate_confidence,
                   e.siting_status, ST_Distance(p.geom, e.geom) AS dist_m
            FROM parcels p, esmp_projects e
            WHERE p.loc_id = :pid
            ORDER BY p.geom <-> e.geom
            LIMIT 1
            """
            ),
            {"pid": ctx["loc_id"]},
        )
        .mappings()
        .first()
    )
    if not row:
        return CriterionScore(
            key="grid_alignment",
            name="Development Potential / Grid Alignment",
            weight=c["weight"],
            raw_score=0.0,
            weighted_contribution=0.0,
            status="data_unavailable",
            finding="No ESMP projects loaded; grid alignment cannot be evaluated.",
            citations=[
                SourceCitation(dataset="Eversource ESMP pipeline", url=_MASSGIS_URLS["esmp"])
            ],
        )

    dist_m = float(row["dist_m"])
    raw = _interp(c["distance_anchors_m"], dist_m)
    # Cap by siting_status — a 'planned' or 'pending_siting' project isn't
    # existing grid infrastructure, so don't reward proximity to it as if
    # it were.
    caps = c.get("siting_status_caps", {})
    status_cap = caps.get(row["siting_status"] or "", 10)
    raw = min(raw, status_cap)
    if row["coordinate_confidence"] == "pending_siting":
        raw = min(raw, c["pending_siting_cap"])
    raw = max(0.0, min(10.0, raw))
    finding = (
        f"Nearest Eversource ESMP project is {row['project_name']} "
        f"({row['municipality']}), {int(round(dist_m))} m away — siting status "
        f"{row['siting_status'] or 'unknown'}, coordinate confidence "
        f"{row['coordinate_confidence']}. Closer proximity to planned grid "
        f"investment strengthens this criterion."
    )
    if row["coordinate_confidence"] == "pending_siting":
        finding += " Score capped because the ESMP project's final site has not been chosen."
    return CriterionScore(
        key="grid_alignment",
        name="Development Potential / Grid Alignment",
        weight=c["weight"],
        raw_score=raw,
        weighted_contribution=raw * c["weight"] * 10,
        finding=finding,
        citations=[
            SourceCitation(
                dataset="Eversource ESMP pipeline (DPU 24-10)",
                row_id=row["project_name"],
                url=_MASSGIS_URLS["esmp"],
                detail=f"{int(round(dist_m))} m from parcel centroid",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Criterion 2: Climate Resilience (flood exposure)
# ---------------------------------------------------------------------------
def _score_climate_resilience(session: Session, ctx: dict, cfg: dict) -> CriterionScore:
    c = cfg["criteria"]["climate_resilience"]
    zones = tuple(c["sfha_zones"])
    row = (
        session.execute(
            text(
                """
            SELECT COALESCE(SUM(
                     ST_Area(ST_Intersection(CAST(:buf AS geometry), ST_MakeValid(f.geom)))
                   ), 0) AS overlap_sqm,
                   STRING_AGG(DISTINCT f.fld_zone, ',') AS zones
            FROM flood_zones f
            WHERE f.fld_zone = ANY(:zones) AND ST_Intersects(CAST(:buf AS geometry), ST_MakeValid(f.geom))
            """
            ),
            {"buf": ctx["buffer_ewkt"], "zones": list(zones)},
        )
        .mappings()
        .first()
    )
    assert row is not None  # aggregate query always returns a row
    overlap = float(row["overlap_sqm"] or 0)
    pct = overlap / ctx["buffer_area_sqm"] if ctx["buffer_area_sqm"] else 0.0
    pct = max(0.0, min(1.0, pct))
    raw = _interp(c["sfha_anchors_pct"], pct)
    detected_zones = row["zones"] or ""
    if pct <= 0:
        finding = (
            "Parcel does not intersect any FEMA SFHA (A/AE/AO/AH/V/VE) flood "
            "zone. No climate resilience deduction."
        )
    else:
        finding = (
            f"{pct * 100:.1f}% of the parcel area is in a FEMA Special Flood "
            f"Hazard Area (zones {detected_zones}). Construction in SFHA "
            f"triggers elevated BFE, insurance, and resilience-design "
            f"requirements under ResilientMass standards."
        )
    return CriterionScore(
        key="climate_resilience",
        name="Climate Resilience",
        weight=c["weight"],
        raw_score=raw,
        weighted_contribution=raw * c["weight"] * 10,
        finding=finding,
        citations=[
            SourceCitation(
                dataset="FEMA National Flood Hazard Layer (MassGIS)",
                url=_MASSGIS_URLS["fema_flood"],
                detail=f"{pct * 100:.2f}% SFHA overlap",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Criterion 3: Carbon Storage (forest-cover proxy)
# ---------------------------------------------------------------------------
def _score_carbon_storage(session: Session, ctx: dict, cfg: dict) -> CriterionScore:
    c = cfg["criteria"]["carbon_storage"]
    forested = c["forested_cover_codes"]
    row = (
        session.execute(
            text(
                """
            SELECT COALESCE(SUM(
                     ST_Area(ST_Intersection(CAST(:buf AS geometry), ST_MakeValid(l.geom)))
                   ), 0) AS overlap_sqm
            FROM land_use l
            WHERE l.covercode = ANY(:codes)
              AND ST_Intersects(CAST(:buf AS geometry), ST_MakeValid(l.geom))
            """
            ),
            {"buf": ctx["buffer_ewkt"], "codes": list(forested)},
        )
        .mappings()
        .first()
    )
    assert row is not None  # aggregate query always returns a row
    overlap = float(row["overlap_sqm"] or 0)
    pct = overlap / ctx["buffer_area_sqm"] if ctx["buffer_area_sqm"] else 0.0
    pct = max(0.0, min(1.0, pct))
    raw = _interp(c["forest_anchors_pct"], pct)
    finding = (
        f"{pct * 100:.1f}% of the project footprint (parcel + {ctx['buffer_m']:.0f} m buffer) "
        f"is forested cover (MassGIS 2016: "
        f"Deciduous/Evergreen Forest + Palustrine Forested Wetland). This is "
        f"a proxy for carbon storage. {c['proxy_note'].strip()}"
    )
    return CriterionScore(
        key="carbon_storage",
        name="Carbon Storage",
        weight=c["weight"],
        raw_score=raw,
        weighted_contribution=raw * c["weight"] * 10,
        finding=finding,
        status="flagged" if pct > 0.3 else "ok",
        citations=[
            SourceCitation(
                dataset="MassGIS Land Cover / Land Use 2016",
                url=_MASSGIS_URLS["land_use"],
                detail=f"{pct * 100:.2f}% forested cover",
            ),
            SourceCitation(
                dataset="Methodology limitation",
                detail=(
                    "DCR Top-20% carbon forest layer is a v2 dependency; "
                    "forested-cover fraction is the v1 proxy."
                ),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Criterion 4: Biodiversity
# ---------------------------------------------------------------------------
def _score_biodiversity(session: Session, ctx: dict, cfg: dict) -> tuple[CriterionScore, list[str]]:
    c = cfg["criteria"]["biodiversity"]
    weights = c["layer_weights"]
    min_ineligible = c["ineligibility_min_pct"]

    def _overlap(table: str) -> tuple[float, list[str]]:
        row = (
            session.execute(
                text(
                    f"""
                SELECT COALESCE(SUM(
                         ST_Area(ST_Intersection(CAST(:buf AS geometry), ST_MakeValid(h.geom)))
                       ), 0) AS overlap_sqm,
                       COUNT(h.id) AS n_rows,
                       STRING_AGG(DISTINCT COALESCE(h.attrs->>'COMMNAME',
                                                    h.attrs->>'COMPNAME',
                                                    h.attrs->>'PRIHAB_ID',
                                                    h.attrs->>'ESTHAB_ID'),
                                  ', ') AS labels
                FROM {table} h
                WHERE ST_Intersects(CAST(:buf AS geometry), ST_MakeValid(h.geom))
                """
                ),
                {"buf": ctx["buffer_ewkt"]},
            )
            .mappings()
            .first()
        )
        assert row is not None  # aggregate query always returns a row
        overlap = float(row["overlap_sqm"] or 0)
        pct = overlap / ctx["buffer_area_sqm"] if ctx["buffer_area_sqm"] else 0.0
        label = row["labels"] or ""
        return max(0.0, min(1.0, pct)), [label] if label else []

    core_pct, core_labels = _overlap("habitat_biomap_core")
    cnl_pct, _ = _overlap("habitat_biomap_cnl")
    pri_pct, pri_labels = _overlap("habitat_nhesp_priority")
    est_pct, _ = _overlap("habitat_nhesp_estimated")

    weighted_overlap = (
        weights["biomap_core"] * core_pct
        + weights["biomap_cnl"] * cnl_pct
        + weights["nhesp_priority"] * pri_pct
        + weights["nhesp_estimated"] * est_pct
    )
    weighted_overlap = max(0.0, min(1.0, weighted_overlap))
    # Anchor-based curve: small overlap with high-weight layers (Core,
    # Priority) still produces a material deduction.
    raw = _interp(c["overlap_anchors"], weighted_overlap)
    raw = max(0.0, min(10.0, raw))

    ineligible: list[str] = []
    if core_pct >= min_ineligible:
        ineligible.append("biomap_core")
    if pri_pct >= min_ineligible:
        ineligible.append("nhesp_priority")

    status: CriterionStatus = (
        "ineligible" if ineligible else ("flagged" if weighted_overlap > 0.1 else "ok")
    )
    finding = (
        f"BioMap Core {core_pct * 100:.1f}% / CNL {cnl_pct * 100:.1f}% / NHESP "
        f"Priority {pri_pct * 100:.1f}% / NHESP Estimated {est_pct * 100:.1f}% "
        f"overlap with the parcel."
    )
    if ineligible:
        finding += (
            " Overlap with BioMap Core or NHESP Priority triggers ineligibility "
            "under 225 CMR 29.06 for generation / storage projects."
        )

    cites = [
        SourceCitation(
            dataset="BioMap Core Habitat Components (MassGIS)",
            url=_MASSGIS_URLS["biomap_core"],
            detail=f"{core_pct * 100:.2f}% overlap"
            + (f" — {core_labels[0]}" if core_labels and core_labels[0] else ""),
        ),
        SourceCitation(
            dataset="BioMap Critical Natural Landscape (MassGIS)",
            url=_MASSGIS_URLS["biomap_cnl"],
            detail=f"{cnl_pct * 100:.2f}% overlap",
        ),
        SourceCitation(
            dataset="NHESP Priority Habitats of Rare Species (MassGIS)",
            url=_MASSGIS_URLS["nhesp_priority"],
            detail=f"{pri_pct * 100:.2f}% overlap"
            + (f" — {pri_labels[0]}" if pri_labels and pri_labels[0] else ""),
        ),
        SourceCitation(
            dataset="NHESP Estimated Habitats of Rare Wildlife (MassGIS)",
            url=_MASSGIS_URLS["nhesp_estimated"],
            detail=f"{est_pct * 100:.2f}% overlap",
        ),
    ]
    return (
        CriterionScore(
            key="biodiversity",
            name="Biodiversity",
            weight=c["weight"],
            raw_score=raw,
            weighted_contribution=raw * c["weight"] * 10,
            status=status,
            finding=finding,
            citations=cites,
        ),
        ineligible,
    )


# ---------------------------------------------------------------------------
# Criterion 5: Social & Environmental Burdens
# ---------------------------------------------------------------------------
def _score_burdens(session: Session, ctx: dict, cfg: dict) -> CriterionScore:
    c = cfg["criteria"]["burdens"]
    row = (
        session.execute(
            text(
                """
            SELECT m.geoid, m.ej_designation, m.cumulative_score
            FROM parcels p
            JOIN massenviroscreen m ON ST_Contains(m.geom, ST_Centroid(p.geom))
            WHERE p.loc_id = :pid
            LIMIT 1
            """
            ),
            {"pid": ctx["loc_id"]},
        )
        .mappings()
        .first()
    )
    if not row:
        return CriterionScore(
            key="burdens",
            name="Social & Environmental Burdens",
            weight=c["weight"],
            raw_score=5.0,
            weighted_contribution=5.0 * c["weight"] * 10,
            status="data_unavailable",
            finding=(
                "No MassEnviroScreen block group covers this parcel's "
                "centroid. Burden score defaults to neutral (5/10)."
            ),
            citations=[
                SourceCitation(
                    dataset="MassEnviroScreen (OEJE)",
                    url=_MASSGIS_URLS["massenviroscreen"],
                )
            ],
        )
    mes = float(row["cumulative_score"] or 0)
    raw = _interp(c["mes_anchors"], mes)
    is_ej = (row["ej_designation"] or "") in c["ej_flag_values"] or (
        row["ej_designation"] or ""
    ).startswith("Yes")
    finding = (
        f"MassEnviroScreen cumulative burden at the parcel's block group "
        f"({row['geoid']}) is {mes:.1f}/100 — {'EJ-designated' if is_ej else 'not EJ-designated'}. "
        "Higher burden indicates existing environmental/health stress; "
        "siting additional burdening infrastructure here requires a "
        "Cumulative Impact Analysis under the 2024 Climate Act."
    )
    return CriterionScore(
        key="burdens",
        name="Social & Environmental Burdens",
        weight=c["weight"],
        raw_score=raw,
        weighted_contribution=raw * c["weight"] * 10,
        status="flagged" if is_ej else "ok",
        finding=finding,
        citations=[
            SourceCitation(
                dataset="MassEnviroScreen cumulative burden (OEJE)",
                row_id=row["geoid"],
                url=_MASSGIS_URLS["massenviroscreen"],
                detail=f"score {mes:.1f}; EJ={row['ej_designation']}",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Criterion 6: Social & Environmental Benefits (brownfield / built-env bonus)
# ---------------------------------------------------------------------------
def _score_benefits(session: Session, ctx: dict, cfg: dict) -> CriterionScore:
    c = cfg["criteria"]["benefits"]
    row = (
        session.execute(
            text(
                """
            SELECT COALESCE(SUM(
                     ST_Area(ST_Intersection(p.geom, l.geom))
                   ), 0) AS overlap_sqm
            FROM parcels p
            LEFT JOIN land_use l
              ON l.covercode = ANY(:codes) AND ST_Intersects(p.geom, l.geom)
            WHERE p.loc_id = :pid
            """
            ),
            {"pid": ctx["loc_id"], "codes": list(c["built_env_cover_codes"])},
        )
        .mappings()
        .first()
    )
    assert row is not None  # aggregate query always returns a row
    overlap = float(row["overlap_sqm"] or 0)
    pct = overlap / ctx["area_sqm"] if ctx["area_sqm"] else 0.0
    pct = max(0.0, min(1.0, pct))
    raw = _interp(c["built_env_anchors_pct"], pct)
    finding = (
        f"{pct * 100:.1f}% of the parcel is already in built-environment cover "
        f"(Impervious or Developed Open Space). Siting on previously-developed "
        f"land earns the brownfield / built-environment bonus."
    )
    return CriterionScore(
        key="benefits",
        name="Social & Environmental Benefits",
        weight=c["weight"],
        raw_score=raw,
        weighted_contribution=raw * c["weight"] * 10,
        finding=finding,
        citations=[
            SourceCitation(
                dataset="MassGIS Land Cover / Land Use 2016",
                url=_MASSGIS_URLS["land_use"],
                detail=f"{pct * 100:.2f}% built-environment cover",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Criterion 7: Agricultural Production
# ---------------------------------------------------------------------------
def _score_agriculture(session: Session, ctx: dict, cfg: dict) -> CriterionScore:
    c = cfg["criteria"]["agriculture"]
    prime_re = c["prime_farmland_regex"]
    statewide_re = c["statewide_farmland_regex"]
    row = (
        session.execute(
            text(
                """
            SELECT
              COALESCE(SUM(CASE WHEN f.farmland_class ~ :prime_re
                                THEN ST_Area(ST_Intersection(CAST(:buf AS geometry), ST_MakeValid(f.geom)))
                                ELSE 0 END), 0) AS prime_sqm,
              COALESCE(SUM(CASE WHEN f.farmland_class ~ :statewide_re
                                THEN ST_Area(ST_Intersection(CAST(:buf AS geometry), ST_MakeValid(f.geom)))
                                ELSE 0 END), 0) AS statewide_sqm
            FROM prime_farmland f
            WHERE ST_Intersects(CAST(:buf AS geometry), ST_MakeValid(f.geom))
            """
            ),
            {"buf": ctx["buffer_ewkt"], "prime_re": prime_re, "statewide_re": statewide_re},
        )
        .mappings()
        .first()
    )
    assert row is not None  # aggregate query always returns a row
    denom = ctx["buffer_area_sqm"] or 1
    prime_pct = float(row["prime_sqm"] or 0) / denom
    state_pct = float(row["statewide_sqm"] or 0) / denom
    effective_pct = max(0.0, min(1.0, prime_pct + c["statewide_weight"] * state_pct))
    raw = _interp(c["prime_anchors_pct"], effective_pct)
    finding = (
        f"{prime_pct * 100:.1f}% of the parcel is NRCS Prime Farmland "
        f"(+{state_pct * 100:.1f}% statewide-importance soils counted at "
        f"{c['statewide_weight']:.0%}). Effective ag-land fraction for "
        f"scoring: {effective_pct * 100:.1f}%."
    )
    return CriterionScore(
        key="agriculture",
        name="Agricultural Production",
        weight=c["weight"],
        raw_score=raw,
        weighted_contribution=raw * c["weight"] * 10,
        status="flagged" if effective_pct > 0.2 else "ok",
        finding=finding,
        citations=[
            SourceCitation(
                dataset="USDA NRCS Prime Farmland Soils (MassGIS)",
                url=_MASSGIS_URLS["prime_farmland"],
                detail=(f"prime {prime_pct * 100:.2f}%, statewide {state_pct * 100:.2f}%"),
            )
        ],
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def score_site(
    session: Session,
    parcel_id: str,
    project_type: str = "generic",
    config_version: str = "ma-eea-2026-v1",
) -> SuitabilityReport:
    cfg = load_config(config_version)
    buffer_m = float(
        cfg.get("project_buffer_m", {}).get(project_type)
        or cfg.get("project_buffer_m", {}).get("default", 200)
    )
    ctx = _parcel_context(session, parcel_id, buffer_m=buffer_m)

    grid = _score_grid_alignment(session, ctx, cfg)
    flood = _score_climate_resilience(session, ctx, cfg)
    carbon = _score_carbon_storage(session, ctx, cfg)
    biodiv, ineligible_from_biodiv = _score_biodiversity(session, ctx, cfg)
    burdens = _score_burdens(session, ctx, cfg)
    benefits = _score_benefits(session, ctx, cfg)
    ag = _score_agriculture(session, ctx, cfg)

    criteria = [grid, flood, carbon, biodiv, burdens, benefits, ag]

    # Scale out any data_unavailable weights so the total stays 0-100.
    active = [c for c in criteria if c.status != "data_unavailable"]
    active_weight = sum(c.weight for c in active) or 1.0
    total = sum(
        (c.weighted_contribution / c.weight if c.weight else 0.0) * (c.weight / active_weight)
        for c in active
    )
    total = max(0.0, min(100.0, total))

    # Ineligibility cap: if BioMap Core or NHESP Priority overlap exceeded
    # the threshold, clamp the total to the soft cap defined in config.
    hard_flags = [f for f in ineligible_from_biodiv if ":" not in f]
    cap = cfg.get("ineligibility_total_cap")
    if hard_flags and cap is not None:
        total = min(total, float(cap))

    bucket: Bucket
    b = cfg["buckets"]
    if total >= b["suitable_min"]:
        bucket = "SUITABLE"
    elif total >= b["conditional_min"]:
        bucket = "CONDITIONALLY SUITABLE"
    else:
        bucket = "CONSTRAINED"

    # Surface the lowest-scoring criterion as primary_constraint.
    primary = min(active, key=lambda c: c.raw_score).key if active else None

    # Ineligibility flags from data we have + placeholders for layers not yet ingested.
    ineligible = list(ineligible_from_biodiv)
    if project_type in cfg.get("generation_storage_project_types", []):
        for layer in cfg["ineligibility_layers"]:
            if layer in {"article97", "carbon_top20", "state_register"} and layer not in ineligible:
                ineligible.append(layer + ":data_unavailable")

    report_citations = [
        SourceCitation(
            dataset="225 CMR 29.00 Site Suitability Criteria (MA EEA)",
            url=_MASSGIS_URLS["regulation"],
            detail=cfg["version"],
        ),
        SourceCitation(
            dataset="MassGIS L3 Property Tax Parcels",
            row_id=ctx["loc_id"],
            url=_MASSGIS_URLS["parcels"],
            detail=f"town={ctx['town_name']}",
        ),
    ]

    return SuitabilityReport(
        parcel_id=ctx["loc_id"],
        address=ctx.get("site_addr"),
        project_type=project_type,
        config_version=cfg["version"],
        methodology=cfg["methodology"],
        computed_at=datetime.now(timezone.utc),
        total_score=round(total, 2),
        bucket=bucket,
        primary_constraint=primary,
        ineligible_flags=ineligible,
        criteria=criteria,
        citations=report_citations,
    )
