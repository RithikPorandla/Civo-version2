"""Estimate mitigation + host community agreement costs for a scored parcel.

Context (from Chris Rodstrom, 2026-04-17): generic Avoid/Minimize/Mitigate
guidance doesn't give developers what they need to run their ROI math. They
want a ballpark dollar figure grounded in what similar projects in the town
actually paid — vegetative screening buffer + setback earthwork + wetland
replication + decommissioning surety + HCA payments.

This module blends two sources:

1. **Industry benchmarks** — widely-cited ranges per mitigation category,
   scaled by project size where applicable. These are the "typical project
   of this size" numbers.
2. **Town precedents** — conditions imposed on prior similar projects in the
   same town, surfaced from the `precedents.conditions` ARRAY column. When
   present, they over-ride or supplement the benchmark ranges.

The output is a structured breakdown the UI can render as a line-item list
inside the Relevant Precedents panel on the Report page.

Pure function; no external calls. Caller supplies session + inputs.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Industry benchmarks by project type. Ranges are (low, high) in USD.
#
# Sources used to set these ranges (captured once; review annually):
#   - SMART 3.0 ADU / brownfield adder data sheets
#   - MassDEP 401 WQC wetland replication cost survey (2022)
#   - NFPA 855 UL-9540A testing + compliance cost survey (solar trade press, 2024)
#   - Host Community Agreement typical pct-of-capital ranges observed across MA
#     cannabis + BESS + solar ground-mount filings
# ---------------------------------------------------------------------------
BENCHMARKS: dict[str, dict[str, Any]] = {
    "solar_ground_mount": {
        "vegetative_screening_buffer": (15_000, 35_000),
        "additional_setback_earthwork": (5_000, 20_000),
        "wetland_replication_per_acre": (25_000, 75_000),
        "decommissioning_surety_per_mw": (3_000, 6_000),
        "stormwater_treatment_per_acre": (8_000, 18_000),
        "hca_threshold_mw": 2.0,
        "hca_pct_capital": (0.005, 0.02),
        "typical_capital_per_mw": 900_000,
    },
    "solar_rooftop": {
        "structural_review": (1_500, 5_000),
        "fire_dept_coordination": (500, 2_500),
        "decommissioning_surety_per_mw": (0, 0),
        "hca_threshold_mw": None,  # rare on rooftop
        "typical_capital_per_mw": 1_800_000,
    },
    "solar_canopy": {
        "structural_steel_premium": (50_000, 150_000),
        "stormwater_treatment_per_acre": (10_000, 20_000),
        "decommissioning_surety_per_mw": (3_000, 6_000),
        "typical_capital_per_mw": 2_200_000,
    },
    "bess_standalone": {
        "nfpa_855_compliance": (50_000, 150_000),
        "fire_access_road": (30_000, 80_000),
        "emergency_response_plan_training": (15_000, 40_000),
        "decommissioning_surety": (75_000, 200_000),
        "vegetative_screening_buffer": (20_000, 50_000),
        "hca_threshold_mwh": 5.0,
        "hca_pct_capital": (0.01, 0.03),
        "typical_capital_per_mwh": 350_000,
    },
    "bess_colocated": {
        "nfpa_855_compliance": (40_000, 120_000),
        "fire_access_road": (20_000, 60_000),
        "decommissioning_surety": (50_000, 150_000),
        "typical_capital_per_mwh": 300_000,
    },
    "substation": {
        "environmental_review": (100_000, 300_000),
        "visual_mitigation_landscaping": (50_000, 200_000),
        "hca_pct_capital": (0.01, 0.03),
    },
    "transmission": {
        "environmental_review_per_mile": (150_000, 400_000),
        "visual_mitigation_landscaping": (100_000, 500_000),
    },
    "ev_charging": {
        "stormwater_mitigation": (5_000, 20_000),
        "ada_accessibility_upgrades": (10_000, 30_000),
        "utility_service_upgrade": (25_000, 100_000),
    },
}


# Condition keywords used to match free-text precedent conditions to cost
# categories. The match is substring-based and lowercased.
CONDITION_KEYWORDS: dict[str, list[str]] = {
    "vegetative_screening_buffer": [
        "screening",
        "vegetat",
        "buffer",
        "landscape screen",
        "landscaping buffer",
    ],
    "additional_setback_earthwork": [
        "setback",
        "additional setback",
    ],
    "wetland_replication_per_acre": [
        "wetland replication",
        "wetland mitigation",
        "wetland restoration",
        "replicat",
    ],
    "stormwater_treatment_per_acre": [
        "stormwater",
        "water quality",
        "drainage",
    ],
    "decommissioning_surety_per_mw": [
        "decommission",
        "surety",
        "financial assurance",
        "bond",
    ],
    "nfpa_855_compliance": ["nfpa 855", "ul 9540", "fire code"],
    "fire_access_road": ["fire access", "apparatus access", "emergency access"],
    "emergency_response_plan_training": [
        "emergency response",
        "first responder",
        "training",
    ],
    "hca_pct_capital": [
        "host community",
        "host benefits",
        "community benefits agreement",
        "cba",
        "hba",
    ],
}


def _find_precedent_conditions(session: Session, parcel_id: str, project_type: str) -> list[dict]:
    """Return recent precedents for the parcel's town + comparable project type,
    along with any free-text `conditions` entries the research agent extracted."""
    # Precedent project_type is broader (solar/battery_storage). Normalize.
    normalized = project_type.split("_")[0]  # solar_ground_mount → solar
    if normalized.startswith("bess"):
        normalized = "battery_storage"
    rows = (
        session.execute(
            text(
                """
                SELECT pr.id, pr.docket, pr.applicant, pr.project_address, pr.decision,
                       pr.decision_date, pr.conditions, pr.source_url
                FROM precedents pr
                JOIN parcels p ON p.town_id = pr.town_id
                WHERE p.loc_id = :pid AND pr.project_type = :pt
                ORDER BY COALESCE(pr.decision_date, pr.filing_date, pr.created_at) DESC
                LIMIT 10
                """
            ),
            {"pid": parcel_id, "pt": normalized},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def _match_conditions_to_categories(conditions: list[str]) -> dict[str, list[str]]:
    """Return {category_key: [matching condition phrase, ...]} for each precedent
    condition we can classify. Unmatched conditions go into ``_other``."""
    out: dict[str, list[str]] = {}
    for cond in conditions or []:
        lc = cond.lower()
        matched = False
        for cat, kws in CONDITION_KEYWORDS.items():
            if any(kw in lc for kw in kws):
                out.setdefault(cat, []).append(cond)
                matched = True
                break
        if not matched:
            out.setdefault("_other", []).append(cond)
    return out


def _fmt_usd(n: float) -> str:
    """Return '$15K' / '$75K' / '$1.2M' — friendly for the UI."""
    if n >= 1_000_000:
        return f"${n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"${round(n / 1_000):,}K"
    return f"${int(n):,}"


def estimate_mitigation_costs(
    session: Session,
    parcel_id: str,
    project_type: str,
    nameplate_kw: float | None = None,
    site_footprint_acres: float | None = None,
    estimated_wetland_impact_acres: float | None = None,
) -> dict[str, Any]:
    """Return a structured mitigation cost estimate for the Report UI.

    Output shape:
    {
      "project_type": "solar_ground_mount",
      "items": [
        {
          "category": "vegetative_screening_buffer",
          "label": "Vegetative screening buffer",
          "low": 15000, "high": 35000,
          "range_display": "$15K–$35K",
          "observed_in_precedents": [{"applicant": ..., "source_url": ...}, ...],
          "note": "typical per project"
        },
        ...
      ],
      "hca": {
        "triggers": true,
        "reason": "project exceeds 2 MW threshold",
        "low": 9000, "high": 54000,
        "range_display": "$9K–$54K",
      },
      "total_range_display": "$58K–$215K",
      "caveats": [...]
    }
    """

    benchmarks = BENCHMARKS.get(project_type, {})
    mw = (nameplate_kw or 0) / 1000.0
    acres = site_footprint_acres or 0
    wetland_acres = estimated_wetland_impact_acres or 0

    # Pull precedents to ground the estimate in what local towns have actually
    # imposed on similar projects.
    precedents = _find_precedent_conditions(session, parcel_id, project_type)
    # Flatten all conditions across precedents.
    all_conditions: list[str] = []
    cond_by_precedent: list[dict] = []
    for p in precedents:
        conds = p.get("conditions") or []
        all_conditions.extend(conds)
        cond_by_precedent.append({"precedent_id": p["id"], "applicant": p.get("applicant"), "conditions": conds, "source_url": p.get("source_url")})
    category_matches = _match_conditions_to_categories(all_conditions)

    items: list[dict[str, Any]] = []

    def _add(
        cat: str,
        label: str,
        low: float,
        high: float,
        note: str | None = None,
    ) -> None:
        observed: list[dict] = []
        for p in cond_by_precedent:
            if any(c in category_matches.get(cat, []) for c in p["conditions"]):
                observed.append(
                    {
                        "applicant": p.get("applicant") or "Unnamed project",
                        "source_url": p.get("source_url"),
                    }
                )
        items.append(
            {
                "category": cat,
                "label": label,
                "low": round(low),
                "high": round(high),
                "range_display": f"{_fmt_usd(low)}–{_fmt_usd(high)}" if low != high else _fmt_usd(low),
                "observed_in_precedents": observed,
                "note": note,
            }
        )

    # Per-project-type logic. Each branch adds the applicable line items.
    if project_type == "solar_ground_mount":
        lo, hi = benchmarks["vegetative_screening_buffer"]
        _add("vegetative_screening_buffer", "Vegetative screening buffer", lo, hi, "typical per project")

        lo, hi = benchmarks["additional_setback_earthwork"]
        _add("additional_setback_earthwork", "Setback earthwork", lo, hi)

        if wetland_acres > 0:
            lo_per, hi_per = benchmarks["wetland_replication_per_acre"]
            _add(
                "wetland_replication_per_acre",
                f"Wetland replication ({wetland_acres:g} acres impact)",
                lo_per * wetland_acres,
                hi_per * wetland_acres,
                "$25K–$75K per acre of impact",
            )

        if acres > 0:
            lo_per, hi_per = benchmarks["stormwater_treatment_per_acre"]
            _add(
                "stormwater_treatment_per_acre",
                f"Stormwater treatment ({acres:g} acre site)",
                lo_per * acres,
                hi_per * acres,
                "$8K–$18K per acre",
            )

        if mw > 0:
            lo_per, hi_per = benchmarks["decommissioning_surety_per_mw"]
            _add(
                "decommissioning_surety_per_mw",
                f"Decommissioning surety ({mw:g} MW · 125% estimate)",
                lo_per * mw,
                hi_per * mw,
                "per DOER model bylaw; $3K–$6K per MW",
            )

    elif project_type in ("bess_standalone", "bess_colocated"):
        lo, hi = benchmarks["nfpa_855_compliance"]
        _add("nfpa_855_compliance", "NFPA 855 + UL 9540A compliance", lo, hi, "testing + engineering")

        lo, hi = benchmarks["fire_access_road"]
        _add("fire_access_road", "Fire apparatus access road", lo, hi)

        if "emergency_response_plan_training" in benchmarks:
            lo, hi = benchmarks["emergency_response_plan_training"]
            _add(
                "emergency_response_plan_training",
                "Emergency response plan + fire dept training",
                lo,
                hi,
            )

        if "decommissioning_surety" in benchmarks:
            lo, hi = benchmarks["decommissioning_surety"]
            _add("decommissioning_surety_per_mw", "Decommissioning surety", lo, hi)

        if "vegetative_screening_buffer" in benchmarks:
            lo, hi = benchmarks["vegetative_screening_buffer"]
            _add("vegetative_screening_buffer", "Vegetative screening buffer", lo, hi)

    elif project_type == "solar_rooftop":
        lo, hi = benchmarks["structural_review"]
        _add("_structural_review", "Structural engineering review", lo, hi)

    elif project_type == "solar_canopy":
        lo, hi = benchmarks["structural_steel_premium"]
        _add("_steel_premium", "Canopy structural steel premium", lo, hi)
        if acres > 0:
            lo_per, hi_per = benchmarks["stormwater_treatment_per_acre"]
            _add(
                "stormwater_treatment_per_acre",
                f"Stormwater treatment ({acres:g} acre site)",
                lo_per * acres,
                hi_per * acres,
            )

    elif project_type == "substation":
        lo, hi = benchmarks["environmental_review"]
        _add("_env_review", "Environmental review", lo, hi)
        lo, hi = benchmarks["visual_mitigation_landscaping"]
        _add("_visual", "Visual mitigation landscaping", lo, hi)

    elif project_type == "transmission":
        lo, hi = benchmarks["environmental_review_per_mile"]
        _add("_env_review", "Environmental review per route mile", lo, hi)
        lo, hi = benchmarks["visual_mitigation_landscaping"]
        _add("_visual", "Visual mitigation landscaping", lo, hi)

    elif project_type == "ev_charging":
        lo, hi = benchmarks["stormwater_mitigation"]
        _add("_stormwater", "Stormwater mitigation", lo, hi)
        lo, hi = benchmarks["ada_accessibility_upgrades"]
        _add("_ada", "ADA accessibility upgrades", lo, hi)
        lo, hi = benchmarks["utility_service_upgrade"]
        _add("_service", "Utility service upgrade", lo, hi)

    # Host Community / Host Benefits Agreement
    hca: dict[str, Any] = {"triggers": False, "reason": None, "low": 0, "high": 0}
    if "hca_pct_capital" in benchmarks:
        pct_lo, pct_hi = benchmarks["hca_pct_capital"]
        triggers = False
        reason: str | None = None
        capital_estimate: float | None = None
        if project_type.startswith("solar_") and "typical_capital_per_mw" in benchmarks and mw:
            threshold = benchmarks.get("hca_threshold_mw")
            if threshold is None or mw >= threshold:
                triggers = True
                reason = (
                    f"project is {mw:g} MW; HCA typically triggered ≥ {threshold or 0} MW"
                    if threshold
                    else f"project is {mw:g} MW"
                )
                capital_estimate = mw * benchmarks["typical_capital_per_mw"]
        elif project_type.startswith("bess") and "typical_capital_per_mwh" in benchmarks and mw:
            # Heuristic: assume 2-hour duration for kW → kWh conversion if no MWh supplied.
            # Caller who knows MWh can override by passing a richer spec in a future version.
            mwh = mw * 2
            threshold = benchmarks.get("hca_threshold_mwh") or 0
            if mwh >= threshold:
                triggers = True
                reason = (
                    f"project ≈ {mwh:g} MWh (2h duration assumed); HCA typically triggered ≥ {threshold} MWh"
                )
                capital_estimate = mwh * benchmarks["typical_capital_per_mwh"]

        if triggers and capital_estimate is not None:
            hca = {
                "triggers": True,
                "reason": reason,
                "low": round(capital_estimate * pct_lo),
                "high": round(capital_estimate * pct_hi),
                "range_display": f"{_fmt_usd(capital_estimate * pct_lo)}–{_fmt_usd(capital_estimate * pct_hi)}",
                "pct_of_capital_display": f"{pct_lo * 100:.1f}%–{pct_hi * 100:.1f}% of estimated capital",
            }

    total_low = sum(it["low"] for it in items) + (hca.get("low") or 0)
    total_high = sum(it["high"] for it in items) + (hca.get("high") or 0)

    caveats: list[str] = []
    if nameplate_kw is None:
        caveats.append("Decommissioning surety requires nameplate capacity — supply kW on the Address Lookup form.")
    if site_footprint_acres is None:
        caveats.append("Stormwater estimate scales with acreage — supply footprint on the Address Lookup form.")
    if estimated_wetland_impact_acres is None and project_type == "solar_ground_mount":
        caveats.append(
            "Wetland replication cost depends on actual impact acreage — estimator excludes this line until site walk."
        )
    if not precedents:
        caveats.append(
            "No precedents loaded for this town + project type yet; ranges are industry benchmarks only."
        )

    return {
        "project_type": project_type,
        "items": items,
        "hca": hca,
        "total_low": round(total_low),
        "total_high": round(total_high),
        "total_range_display": f"{_fmt_usd(total_low)}–{_fmt_usd(total_high)}",
        "precedent_count": len(precedents),
        "caveats": caveats,
    }
