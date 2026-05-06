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
from app.scoring.parcel_classifier import ParcelClassification, classify as classify_parcel

CONFIG_ROOT = Path(__file__).resolve().parents[2] / "config" / "scoring"

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
    "ej_populations": "https://www.mass.gov/info-details/environmental-justice-populations-in-massachusetts",
    "dcr_priority_forests": "https://www.mass.gov/info-details/massgis-data-dcr-priority-forests",
    "coastal_flood_risk": "https://eeaonline.eea.state.ma.us/ResilientMAMapViewer/",
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
    cfg = yaml.safe_load(p.read_text())

    # If this config declares a base_config, merge weight overrides on top of it.
    # This allows project-type configs (ma-eea-2026-v1-bess.yaml) to inherit all
    # anchors, thresholds, and ineligibility rules while only changing weights.
    base_name = cfg.get("base_config")
    if base_name:
        base_path = CONFIG_ROOT / f"{base_name}.yaml"
        if not base_path.exists():
            raise ScoringError(f"base config {base_name!r} not found (referenced by {config_version!r})")
        base = yaml.safe_load(base_path.read_text())
        overrides = cfg.get("criteria_weight_overrides") or {}
        for key, weight in overrides.items():
            if key in (base.get("criteria") or {}):
                base["criteria"][key]["weight"] = weight
        # Merge top-level keys from child config (buckets, buffer, etc.)
        for k, v in cfg.items():
            if k not in ("base_config", "criteria_weight_overrides"):
                base[k] = v
        return base

    return cfg


# Maps project_type → scoring config version.
# Used by the discovery engine and batch scorer to pick the right weights.
PROJECT_TYPE_CONFIG: dict[str, str] = {
    "bess_standalone":  "ma-eea-2026-v1-bess",
    "bess_colocated":   "ma-eea-2026-v1-bess",
    "solar_ground_mount": "ma-eea-2026-v1-solar",
    "solar_canopy":     "ma-eea-2026-v1-solar",
}

DEFAULT_CONFIG = "ma-eea-2026-v1"


def config_for_project_type(project_type: str | None) -> str:
    """Return the scoring config version appropriate for a given project type."""
    return PROJECT_TYPE_CONFIG.get(project_type or "", DEFAULT_CONFIG)


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
            SELECT loc_id, site_addr, town_name, city, use_code,
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
                SourceCitation(dataset="Eversource/National Grid ESMP", url=_MASSGIS_URLS["esmp"])
            ],
        )

    dist_m = float(row["dist_m"])
    raw = _interp(c["distance_anchors_m"], dist_m)
    caps = c.get("siting_status_caps", {})
    status_cap = caps.get(row["siting_status"] or "", 10)
    raw = min(raw, status_cap)
    if row["coordinate_confidence"] == "pending_siting":
        raw = min(raw, c["pending_siting_cap"])
    raw = max(0.0, min(10.0, raw))

    # HCA bonus: if a hosting_capacity point is within 5km with available
    # capacity, boost the score to reflect real interconnection headroom.
    hca_row = (
        session.execute(
            text("""
                SELECT h.substation_name, h.utility, h.available_mw,
                       ST_Distance(p.geom, h.geom) AS dist_m
                FROM parcels p, hosting_capacity h
                WHERE p.loc_id = :pid
                  AND h.available_mw > 0
                ORDER BY p.geom <-> h.geom
                LIMIT 1
            """),
            {"pid": ctx["loc_id"]},
        )
        .mappings()
        .first()
    )
    hca_bonus = 0.0
    hca_citation: SourceCitation | None = None
    if hca_row and float(hca_row["dist_m"]) <= 5000:
        # Bonus: 0 MW→0, 5 MW→0.3, 20 MW→0.8, 50 MW→1.5 (capped to keep raw ≤10)
        hca_bonus = _interp([[0, 0], [5, 0.3], [20, 0.8], [50, 1.5]], float(hca_row["available_mw"]))
        raw = min(10.0, raw + hca_bonus)
        hca_citation = SourceCitation(
            dataset=f"{hca_row['utility']} Hosting Capacity Analysis",
            row_id=hca_row["substation_name"],
            detail=f"{hca_row['available_mw']:.1f} MW available, {int(hca_row['dist_m'])} m away",
        )

    source_filing = row.get("source_filing") or "DPU 24-10"
    utility_label = "Eversource" if "24-10" in source_filing else "National Grid"
    finding = (
        f"Nearest ESMP project is {row['project_name']} ({row['municipality']}), "
        f"{int(round(dist_m))} m away ({utility_label}, {source_filing}) — "
        f"siting status {row['siting_status'] or 'unknown'}."
    )
    if hca_bonus > 0:
        finding += (
            f" Hosting capacity data adds +{hca_bonus:.1f} points: "
            f"{hca_row['available_mw']:.1f} MW available at "
            f"{hca_row['substation_name'] or 'nearest substation'}."
        )
    if row["coordinate_confidence"] == "pending_siting":
        finding += " Score capped — ESMP project final site not yet chosen."

    citations = [
        SourceCitation(
            dataset=f"{utility_label} ESMP ({source_filing})",
            row_id=row["project_name"],
            url=_MASSGIS_URLS["esmp"],
            detail=f"{int(round(dist_m))} m from parcel centroid",
        )
    ]
    if hca_citation:
        citations.append(hca_citation)

    return CriterionScore(
        key="grid_alignment",
        name="Development Potential / Grid Alignment",
        weight=c["weight"],
        raw_score=raw,
        weighted_contribution=raw * c["weight"] * 10,
        finding=finding,
        citations=citations,
    )


# ---------------------------------------------------------------------------
# Criterion 2: Climate Resilience (flood exposure)
# ---------------------------------------------------------------------------
def _score_climate_resilience(session: Session, ctx: dict, cfg: dict) -> CriterionScore:
    c = cfg["criteria"]["climate_resilience"]

    # ── FEMA SFHA (all flood types — riverine + coastal) ────────────────────
    zones = tuple(c["sfha_zones"])
    fema_row = (
        session.execute(
            text(
                """
            SELECT COALESCE(SUM(
                     ST_Area(ST_Intersection(CAST(:buf AS geometry), f.geom))
                   ), 0) AS overlap_sqm,
                   STRING_AGG(DISTINCT f.fld_zone, ',') AS zones
            FROM flood_zones f
            WHERE f.fld_zone = ANY(:zones) AND ST_Intersects(CAST(:buf AS geometry), f.geom)
            """
            ),
            {"buf": ctx["buffer_ewkt"], "zones": list(zones)},
        )
        .mappings()
        .first()
    )
    assert fema_row is not None
    fema_overlap = float(fema_row["overlap_sqm"] or 0)
    fema_pct = max(0.0, min(1.0, fema_overlap / ctx["buffer_area_sqm"])) if ctx["buffer_area_sqm"] else 0.0
    fema_raw = _interp(c["sfha_anchors_pct"], fema_pct)
    fema_zones = fema_row["zones"] or ""

    # ── MC-FRM coastal flood risk (2030/2050/2070 × 1pct/0.1pct) ───────────
    # Only active if the coastal_flood_risk table has been ingested.
    mcfrm_loaded: bool = bool(
        session.execute(text("SELECT 1 FROM coastal_flood_risk LIMIT 1")).first()
    )

    # Collect pct overlaps for all scenario/aep combinations in one query.
    mcfrm_pcts: dict[tuple[str, str], float] = {}
    if mcfrm_loaded:
        mcfrm_rows = (
            session.execute(
                text("""
                    SELECT cf.scenario, cf.aep,
                           COALESCE(SUM(
                               ST_Area(ST_Intersection(CAST(:buf AS geometry), cf.geom))
                           ), 0) AS overlap_sqm
                    FROM coastal_flood_risk cf
                    WHERE ST_Intersects(CAST(:buf AS geometry), cf.geom)
                    GROUP BY cf.scenario, cf.aep
                """),
                {"buf": ctx["buffer_ewkt"]},
            )
            .mappings()
            .all()
        )
        buf_area = ctx["buffer_area_sqm"] or 1.0
        for r in mcfrm_rows:
            pct = max(0.0, min(1.0, float(r["overlap_sqm"] or 0) / buf_area))
            mcfrm_pcts[(r["scenario"], r["aep"])] = pct

    # Primary MC-FRM constraint: 2050 1% AEP (mid-term 100-year coastal event).
    primary_scenario = c.get("mcfrm_primary_scenario", "2050")
    primary_aep = c.get("mcfrm_primary_aep", "1pct")
    mcfrm_primary_pct = mcfrm_pcts.get((primary_scenario, primary_aep), 0.0)
    mcfrm_raw = _interp(c["mcfrm_anchors_pct"], mcfrm_primary_pct)

    # Long-horizon flag: 2070 0.1% AEP intersection is a viability warning
    # for 25–30 year assets even if the primary score is fine.
    longterm_pct = mcfrm_pcts.get(("2070", "0.1pct"), 0.0)

    # ── Combine: take the more conservative (lower) raw score ───────────────
    if mcfrm_loaded:
        raw = min(fema_raw, mcfrm_raw)
        binding = "mc-frm" if mcfrm_raw < fema_raw else "fema"
    else:
        raw = fema_raw
        binding = "fema"

    # ── Finding text ─────────────────────────────────────────────────────────
    parts: list[str] = []
    if fema_pct > 0:
        parts.append(
            f"FEMA SFHA ({fema_zones}): {fema_pct * 100:.1f}% of the analysis zone."
        )
    else:
        parts.append("No FEMA SFHA overlap.")

    if mcfrm_loaded:
        if mcfrm_primary_pct > 0:
            parts.append(
                f"MC-FRM {primary_scenario} {primary_aep} coastal flood: "
                f"{mcfrm_primary_pct * 100:.1f}% overlap — "
                f"{'binding constraint' if binding == 'mc-frm' else 'below FEMA constraint'}."
            )
        else:
            parts.append(
                f"Parcel is outside the MC-FRM {primary_scenario} {primary_aep} coastal "
                f"inundation zone — no coastal climate flood deduction."
            )
        if longterm_pct > 0:
            parts.append(
                f"Long-horizon flag: {longterm_pct * 100:.1f}% overlap with MC-FRM 2070 "
                f"0.1% AEP (1000-year event). Asset viability beyond 2050 should be "
                f"assessed under the higher sea-level-rise scenario."
            )

    if raw == 10.0 and not fema_pct and not mcfrm_primary_pct:
        finding = "No flood risk detected. Parcel is outside all FEMA SFHA zones and MC-FRM coastal inundation envelopes."
    else:
        finding = " ".join(parts)

    # ── Citations ────────────────────────────────────────────────────────────
    citations = [
        SourceCitation(
            dataset="FEMA National Flood Hazard Layer (MassGIS)",
            url=_MASSGIS_URLS["fema_flood"],
            detail=f"{fema_pct * 100:.2f}% SFHA overlap",
        )
    ]
    if mcfrm_loaded:
        citations.append(
            SourceCitation(
                dataset=f"MA Coastal Flood Risk Model (MC-FRM) {primary_scenario} {primary_aep}",
                url=_MASSGIS_URLS["coastal_flood_risk"],
                detail=f"{mcfrm_primary_pct * 100:.2f}% overlap — {'binding' if binding == 'mc-frm' else 'secondary'}",
            )
        )
        if longterm_pct > 0:
            citations.append(
                SourceCitation(
                    dataset="MC-FRM 2070 0.1% AEP (long-horizon)",
                    url=_MASSGIS_URLS["coastal_flood_risk"],
                    detail=f"{longterm_pct * 100:.2f}% overlap",
                )
            )

    return CriterionScore(
        key="climate_resilience",
        name="Climate Resilience",
        weight=c["weight"],
        raw_score=raw,
        weighted_contribution=raw * c["weight"] * 10,
        finding=finding,
        citations=citations,
    )


# ---------------------------------------------------------------------------
# Criterion 3: Carbon Storage
# ---------------------------------------------------------------------------
def _score_carbon_storage(session: Session, ctx: dict, cfg: dict) -> CriterionScore:
    c = cfg["criteria"]["carbon_storage"]

    # Check whether the DCR Priority Forests layer has been ingested.
    dcr_loaded: bool = bool(
        session.execute(text("SELECT 1 FROM dcr_priority_forests LIMIT 1")).first()
    )

    if dcr_loaded:
        row = (
            session.execute(
                text(
                    """
                SELECT COALESCE(SUM(
                         ST_Area(ST_Intersection(CAST(:buf AS geometry), d.geom))
                       ), 0) AS overlap_sqm
                FROM dcr_priority_forests d
                WHERE ST_Intersects(CAST(:buf AS geometry), d.geom)
                """
                ),
                {"buf": ctx["buffer_ewkt"]},
            )
            .mappings()
            .first()
        )
        assert row is not None
        overlap = float(row["overlap_sqm"] or 0)
        pct = overlap / ctx["buffer_area_sqm"] if ctx["buffer_area_sqm"] else 0.0
        pct = max(0.0, min(1.0, pct))
        raw = _interp(c["dcr_anchors_pct"], pct)
        ineligibility_pct = c.get("ineligibility_min_pct", 0.20)
        status: CriterionStatus = (
            "ineligible" if pct >= ineligibility_pct else ("flagged" if pct > 0.05 else "ok")
        )
        finding = (
            f"{pct * 100:.1f}% of the project footprint (parcel + {ctx['buffer_m']:.0f} m buffer) "
            f"intersects DCR Priority Forests (top-20% carbon storage statewide). "
            + (
                f"Overlap ≥ {ineligibility_pct * 100:.0f}% triggers an ineligibility flag "
                f"under 225 CMR 29.06 — carbon_top20 overlay."
                if pct >= ineligibility_pct
                else ""
            )
        )
        return CriterionScore(
            key="carbon_storage",
            name="Carbon Storage",
            weight=c["weight"],
            raw_score=raw,
            weighted_contribution=raw * c["weight"] * 10,
            finding=finding,
            status=status,
            citations=[
                SourceCitation(
                    dataset="DCR Priority Forests — Top-20% Carbon Storage (MassGIS)",
                    url=_MASSGIS_URLS["dcr_priority_forests"],
                    detail=f"{pct * 100:.2f}% overlap with priority forest polygons",
                )
            ],
        )

    # Use MassGIS 2016 Land Cover — the authoritative statewide forested-cover dataset.
    # Forested cover fraction is the accepted proxy for carbon storage risk in
    # environmental impact assessment when site-specific carbon stock data is unavailable.
    forested = c["forested_cover_codes"]
    proxy_row = (
        session.execute(
            text(
                """
            SELECT COALESCE(SUM(
                     ST_Area(ST_Intersection(CAST(:buf AS geometry), l.geom))
                   ), 0) AS overlap_sqm
            FROM land_use l
            WHERE l.covercode = ANY(:codes)
              AND ST_Intersects(CAST(:buf AS geometry), l.geom)
            """
            ),
            {"buf": ctx["buffer_ewkt"], "codes": list(forested)},
        )
        .mappings()
        .first()
    )
    assert proxy_row is not None
    overlap = float(proxy_row["overlap_sqm"] or 0)
    pct = overlap / ctx["buffer_area_sqm"] if ctx["buffer_area_sqm"] else 0.0
    pct = max(0.0, min(1.0, pct))
    raw = _interp(c["forest_anchors_pct"], pct)
    finding = (
        f"{pct * 100:.1f}% of the project footprint (parcel + {ctx['buffer_m']:.0f} m buffer) "
        f"is forested cover per MassGIS 2016 Land Cover (Deciduous Forest, Evergreen Forest, "
        f"Palustrine Forested Wetland). Higher forested fraction indicates greater carbon stock "
        f"at risk and lower siting suitability."
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
                detail=f"{pct * 100:.2f}% forested cover (cover codes 9, 10, 13)",
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

    # Single round-trip for all four habitat layers.
    bio_rows = (
        session.execute(
            text(
                """
                SELECT src,
                       COALESCE(SUM(ST_Area(ST_Intersection(
                           CAST(:buf AS geometry), geom))), 0) AS overlap_sqm,
                       STRING_AGG(DISTINCT label, ', ') AS labels
                FROM (
                    SELECT 'biomap_core' AS src, geom,
                           COALESCE(attrs->>'COMMNAME', attrs->>'COMPNAME') AS label
                    FROM habitat_biomap_core
                    WHERE CAST(:buf AS geometry) && geom
                      AND ST_Intersects(CAST(:buf AS geometry), geom)
                    UNION ALL
                    SELECT 'biomap_cnl', geom, NULL
                    FROM habitat_biomap_cnl
                    WHERE CAST(:buf AS geometry) && geom
                      AND ST_Intersects(CAST(:buf AS geometry), geom)
                    UNION ALL
                    SELECT 'nhesp_priority', geom, attrs->>'PRIHAB_ID'
                    FROM habitat_nhesp_priority
                    WHERE CAST(:buf AS geometry) && geom
                      AND ST_Intersects(CAST(:buf AS geometry), geom)
                    UNION ALL
                    SELECT 'nhesp_estimated', geom, attrs->>'ESTHAB_ID'
                    FROM habitat_nhesp_estimated
                    WHERE CAST(:buf AS geometry) && geom
                      AND ST_Intersects(CAST(:buf AS geometry), geom)
                ) sub
                GROUP BY src
                """
            ),
            {"buf": ctx["buffer_ewkt"]},
        )
        .mappings()
        .all()
    )
    bio: dict[str, tuple[float, list[str]]] = {}
    buf_area = ctx["buffer_area_sqm"] or 1.0
    for r in bio_rows:
        pct = max(0.0, min(1.0, float(r["overlap_sqm"] or 0) / buf_area))
        labels = [r["labels"]] if r["labels"] else []
        bio[r["src"]] = (pct, labels)

    def _bio(key: str) -> tuple[float, list[str]]:
        return bio.get(key, (0.0, []))

    core_pct, core_labels = _bio("biomap_core")
    cnl_pct, _ = _bio("biomap_cnl")
    pri_pct, pri_labels = _bio("nhesp_priority")
    est_pct, _ = _bio("nhesp_estimated")

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
    income_threshold: float = (
        c["ma_statewide_median_hh_income"] * c["burdened_area_income_threshold_pct"]
    )

    # Area-weighted intersection: avoids centroid bias on large parcels.
    # Numeric scores are weighted by overlap area; categorical fields come
    # from the dominant (largest-overlap) block group.
    row = (
        session.execute(
            text("""
                SELECT
                    SUM(m.cumulative_score    * sub.a) / NULLIF(SUM(sub.a), 0) AS cumulative_score,
                    SUM(m.pollution_score     * sub.a) / NULLIF(SUM(sub.a), 0) AS pollution_score,
                    SUM(m.vulnerability_score * sub.a) / NULLIF(SUM(sub.a), 0) AS vulnerability_score,
                    (array_agg(m.geoid          ORDER BY sub.a DESC))[1] AS geoid,
                    (array_agg(m.ej_designation ORDER BY sub.a DESC))[1] AS ej_designation,
                    (array_agg(m.attrs          ORDER BY sub.a DESC))[1] AS attrs
                FROM (
                    SELECT m.id,
                           ST_Area(ST_Intersection(p.geom, m.geom)) AS a
                    FROM   parcels p
                    JOIN   massenviroscreen m ON ST_Intersects(p.geom, m.geom)
                    WHERE  p.loc_id = :pid
                ) sub
                JOIN massenviroscreen m ON m.id = sub.id
                WHERE sub.a > 0
            """),
            {"pid": ctx["loc_id"]},
        )
        .mappings()
        .first()
    )

    if not row or row["cumulative_score"] is None:
        return CriterionScore(
            key="burdens",
            name="Social & Environmental Burdens",
            weight=c["weight"],
            raw_score=5.0,
            weighted_contribution=5.0 * c["weight"] * 10,
            status="data_unavailable",
            finding="No MassEnviroScreen data covers this parcel. Score defaults to neutral.",
            citations=[SourceCitation(
                dataset="MassEnviroScreen (OEJE)",
                url=_MASSGIS_URLS["massenviroscreen"],
            )],
        )

    mes         = float(row["cumulative_score"]    or 0)
    pollution   = float(row["pollution_score"]     or 0)
    vuln        = float(row["vulnerability_score"] or 0)
    raw         = _interp(c["mes_anchors"], mes)

    # Parse demographic fields from the dominant block group's attrs jsonb.
    attrs        = row["attrs"] or {}
    minority_pct = float(attrs.get("minorityPctE") or 0)
    lim_eng_pct  = float(attrs.get("limitEngpctE") or 0)
    med_income   = float(attrs.get("medHHincE")    or 0)
    ma_median    = float(attrs.get("medHHincMA")   or c["ma_statewide_median_hh_income"])
    income_pct   = (med_income / ma_median * 100) if ma_median > 0 and med_income > 0 else None
    uba          = (attrs.get("UBA") or "").upper() == "YES"
    fire_pct     = float(attrs.get("CLIMpctilFIRE") or 0)
    heat_pct     = float(attrs.get("CLIMpctilHEAT") or 0)

    # Official MA EJ Population 2020 layer — authoritative EJ designation and criteria.
    # Uses centroid containment (single block group is fine for the EJ label;
    # area-weighted scores above handle numeric values for large parcels).
    ej_pop = (
        session.execute(
            text("""
                SELECT geo_area_name, ej, ej_criteria, ej_crit_desc,
                       pct_minority, bg_mhhi, bg_mhhi_pct_ma, lim_eng_pct,
                       muni_mhhi, muni_mhhi_pct_ma, total_pop, total_hh
                FROM   ej_populations
                WHERE  ST_Contains(geom, ST_Centroid(
                           (SELECT geom FROM parcels WHERE loc_id = :pid)
                       ))
                LIMIT 1
            """),
            {"pid": ctx["loc_id"]},
        )
        .mappings()
        .first()
    )

    if ej_pop:
        # Use official 2020 ACS values from the EJ layer directly.
        is_ej         = bool(ej_pop["ej"])
        ej_crit_code  = ej_pop["ej_criteria"] or ""   # 'M', 'I', 'E', 'IM', etc.
        ej_crit_desc  = ej_pop["ej_crit_desc"]        # 'Minority and income', etc.
        geo_area_name = ej_pop["geo_area_name"]
        minority_pct  = float(ej_pop["pct_minority"] or minority_pct)
        lim_eng_pct   = float(ej_pop["lim_eng_pct"]  or lim_eng_pct)
        muni_mhhi     = float(ej_pop["muni_mhhi"]    or 0) or None
        muni_mhhi_pct = float(ej_pop["muni_mhhi_pct_ma"] or 0) or None
        total_pop     = int(ej_pop["total_pop"] or 0) or None
        total_hh      = int(ej_pop["total_hh"]  or 0) or None
    else:
        # Fallback: derive from MassEnviroScreen attrs when ej_populations has no match.
        is_ej         = (row["ej_designation"] or "").lower() in ("yes", "y", "true", "1")
        ej_crit_code  = ""
        ej_crit_desc  = None
        geo_area_name = attrs.get("NAME")
        muni_mhhi     = float(attrs.get("medHHincMUNIE")   or 0) or None
        muni_mhhi_pct = float(attrs.get("medHHincMUNIPCT") or 0) or None
        total_pop     = int(attrs.get("TotalPopE") or 0) or None
        total_hh      = int(attrs.get("TotalHHE")  or 0) or None

    # MA EJ Policy 2020 official thresholds:
    #   Minority  ≥ 40%   (non-white / Hispanic)
    #   Income    ≤ 65%   of MA MHHI
    #   Language  ≥ 25%   of households with limited English
    # When the official EJ layer matched, use its ej_crit_code to build display
    # strings. Otherwise compute from demographics against the same thresholds.
    ej_criteria: list[str] = []
    if ej_pop and ej_crit_code:
        if "M" in ej_crit_code:
            ej_criteria.append(f"Minority {minority_pct:.0f}%")
        if "I" in ej_crit_code:
            ej_criteria.append(
                f"Income ${med_income:,.0f} ({income_pct:.0f}% of MA median)" if income_pct else
                f"Income ${med_income:,.0f}"
            )
        if "E" in ej_crit_code:
            ej_criteria.append(f"Limited English {lim_eng_pct:.0f}%")
    else:
        # Derived fallback — official MA EJ Policy 2020 thresholds.
        min_thr = c.get("ej_minority_threshold_pct", 0.40) * 100
        lang_thr = c.get("ej_language_threshold_pct", 0.25) * 100
        if minority_pct >= min_thr:
            ej_criteria.append(f"Minority {minority_pct:.0f}%")
        if med_income > 0 and med_income <= income_threshold:
            ej_criteria.append(
                f"Income ${med_income:,.0f} ({income_pct:.0f}% of MA median)" if income_pct else
                f"Income ${med_income:,.0f}"
            )
        if lim_eng_pct >= lang_thr:
            ej_criteria.append(f"Limited English {lim_eng_pct:.0f}%")

    # 2024 Climate Act Burdened Area
    is_mes_burdened    = mes >= 75.0
    is_income_burdened = med_income > 0 and med_income <= income_threshold
    is_burdened_area   = is_mes_burdened or is_income_burdened or uba

    # ── Finding text: scannable, one idea per sentence ───────────────────────
    parts: list[str] = []

    if geo_area_name:
        parts.append(geo_area_name + ".")

    if is_ej or ej_criteria:
        crit_str = " + ".join(ej_criteria) if ej_criteria else (ej_crit_desc or "designated")
        parts.append(f"EJ population — {crit_str}.")
    else:
        demo_parts = [f"Minority {minority_pct:.0f}%"]
        if income_pct:
            demo_parts.append(f"MHHI ${med_income:,.0f} ({income_pct:.0f}% of MA median)")
        if lim_eng_pct:
            demo_parts.append(f"Limited English {lim_eng_pct:.0f}%")
        parts.append(f"Not an EJ population — {' · '.join(demo_parts)}.")

    if muni_mhhi and muni_mhhi_pct:
        parts.append(f"Municipality MHHI ${muni_mhhi:,.0f} ({muni_mhhi_pct:.0f}% of MA median).")
    if total_pop and total_hh:
        parts.append(f"Population {total_pop:,} in {total_hh:,} households.")

    parts.append(
        f"MES {mes:.1f}/100 — Pollution burden {pollution:.1f} · "
        f"Household vulnerability {vuln:.1f}."
    )

    if is_burdened_area:
        triggers: list[str] = []
        if is_mes_burdened:
            triggers.append(f"MES {mes:.1f} ≥ 75th percentile")
        if is_income_burdened:
            triggers.append(f"MHHI ${med_income:,.0f} ≤ ${income_threshold:,.0f}")
        if uba:
            triggers.append("UBA designation")
        parts.append(
            f"BURDENED AREA ({'; '.join(triggers)}). "
            f"EFSB projects require Cumulative Impact Analysis + Community Benefit Plan."
        )
    if is_ej or ej_criteria:
        parts.append("225 CMR 29.09: extended notice, translated materials, additional public comment.")

    if fire_pct >= 75 or heat_pct >= 75:
        climate: list[str] = []
        if fire_pct >= 75:
            climate.append(f"Fire {fire_pct:.0f}th percentile")
        if heat_pct >= 75:
            climate.append(f"Heat {heat_pct:.0f}th percentile")
        parts.append(f"Elevated climate risk: {' · '.join(climate)}.")

    finding = " ".join(parts)
    status: CriterionStatus = "flagged" if (is_burdened_area or is_ej or bool(ej_criteria)) else "ok"

    return CriterionScore(
        key="burdens",
        name="Social & Environmental Burdens",
        weight=c["weight"],
        raw_score=raw,
        weighted_contribution=raw * c["weight"] * 10,
        status=status,
        finding=finding,
        citations=[
            SourceCitation(
                dataset="MA EJ Population 2020 (OEJE / MassGIS)",
                row_id=row["geoid"],
                url=_MASSGIS_URLS["ej_populations"],
                detail=(
                    f"EJ={is_ej}; criteria={ej_crit_desc or ('|'.join(ej_criteria) or 'None')}; "
                    f"minority={minority_pct:.1f}%; lim_eng={lim_eng_pct:.1f}%"
                ),
            ),
            SourceCitation(
                dataset="MassEnviroScreen cumulative burden (OEJE)",
                row_id=row["geoid"],
                url=_MASSGIS_URLS["massenviroscreen"],
                detail=(
                    f"MES {mes:.1f}; pollution {pollution:.1f}; vulnerability {vuln:.1f}; "
                    f"burdened={is_burdened_area}; UBA={uba}"
                ),
            ),
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
                                THEN ST_Area(ST_Intersection(CAST(:buf AS geometry), f.geom))
                                ELSE 0 END), 0) AS prime_sqm,
              COALESCE(SUM(CASE WHEN f.farmland_class ~ :statewide_re
                                THEN ST_Area(ST_Intersection(CAST(:buf AS geometry), f.geom))
                                ELSE 0 END), 0) AS statewide_sqm
            FROM prime_farmland f
            WHERE ST_Intersects(CAST(:buf AS geometry), f.geom)
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
    config_version: str | None = None,
) -> SuitabilityReport:
    # Auto-select project-type-specific config when none is explicitly given.
    if config_version is None:
        config_version = config_for_project_type(project_type)
    cfg = load_config(config_version)
    buffer_m = float(
        cfg.get("project_buffer_m", {}).get(project_type)
        or cfg.get("project_buffer_m", {}).get("default", 200)
    )
    ctx = _parcel_context(session, parcel_id, buffer_m=buffer_m)

    parcel_classification: ParcelClassification = classify_parcel(ctx.get("use_code"))

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
        parcel_classification=parcel_classification,
        criteria=criteria,
        citations=report_citations,
    )
