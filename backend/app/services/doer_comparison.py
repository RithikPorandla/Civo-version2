"""Compare a municipality's bylaw against the DOER solar model bylaw.

This is the engine that turns "DOER says site-plan-review for 25-250 kW
primary use" + "Acton requires special permit for industrial solar" into
a structured deviation with severity and Dover Amendment risk flag.

Scope this sprint: **solar only**. BESS tiers have different structure
(kWh + NFPA 855) and need their own engine; the surface renders
BESS adoption status but skips BESS deviation diff.

Public API
----------
compare_town_to_doer_model(town_bylaws, doer_model) -> DoerComparisonResult

Inputs are plain dicts (pulled from the project_type_bylaws JSONB on
the municipality row and the parsed_data JSONB on the doer_model_bylaws
row) so this module stays pure-Python and trivially unit-testable.
"""

from __future__ import annotations

import re
from typing import Any

from app.doer.models import (
    DoerComparisonResult,
    DoerDeviation,
    DoerProjectType,
    Severity,
)

# ---------------------------------------------------------------------------
# Buckets — the four enforcement ranges on the solar ground-mount axis.
# Town-side ``solar_ground_mount`` has no size dimension; the engine
# compares the town's single rule against every DOER bucket and surfaces
# a deviation per bucket where the town diverges.
# ---------------------------------------------------------------------------
_PROCESS_SEVERITY = {
    "by_right": 0,
    "building_permit": 0,  # town-side alias for by_right
    "site_plan_review": 1,
    "special_permit": 2,
    "state_siting": 3,
}

_DOER_GROUND_MOUNT_BUCKETS: list[dict[str, Any]] = [
    {
        "tier": "Ground-Mount Small (0–25 kW)",
        "size_kw": (0, 25),
        "doer_tier_name": "Ground-Mounted Small",
        "doer_path": "by_right",
    },
    {
        "tier": "Ground-Mount Medium Primary (25–250 kW)",
        "size_kw": (25, 250),
        "doer_tier_name": "Ground-Mounted Medium - Primary Use",
        "doer_path": "site_plan_review",
    },
    {
        "tier": "Ground-Mount Large I (250–1,000 kW)",
        "size_kw": (250, 1000),
        "doer_tier_name": "Ground-Mounted Large I",
        "doer_path": "special_permit",
    },
    {
        "tier": "Ground-Mount Large II (1,000–25,000 kW)",
        "size_kw": (1000, 25000),
        "doer_tier_name": "Ground-Mounted Large II",
        "doer_path": "special_permit",
    },
]

# Categories auto-flagged as potential Dover Amendment violations.
# Precedent cases live in docstrings here and in the DOER parsed_data.
_DOVER_RISK_CATEGORIES = {
    "uniform_treatment",  # Tracer Lane II v. Waltham (2022)
    "acreage_cap_restriction",  # Tracer Lane / Kearsarge
    "overlay_restriction",  # Kearsarge Walpole v. ZBA Walpole (2024)
}


def _parse_ft(s: Any) -> int | None:
    """Extract the first integer ft value from a string like '50 ft (75 ft if abutting ...)'."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return int(s)
    m = re.search(r"(\d+)\s*ft", str(s), flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.match(r"\s*(\d+)\s*$", str(s))
    return int(m.group(1)) if m else None


def _process_severity_delta(town_process: str, doer_process: str) -> Severity | None:
    """Return the severity of a town's process being stricter than DOER's.

    None when town process is equal or more lenient. We only flag
    town-stricter deviations — a town that's more lenient than DOER is
    already safe-harbored.
    """
    town_s = _PROCESS_SEVERITY.get(town_process, 1)
    doer_s = _PROCESS_SEVERITY.get(doer_process, 0)
    diff = town_s - doer_s
    if diff <= 0:
        return None
    if diff >= 2:
        return "major"
    return "moderate"


def _find_doer_tier(doer_model: dict, tier_name: str) -> dict | None:
    for t in doer_model.get("tiers", []):
        if t.get("tier_name") == tier_name:
            return t
    return None


def _doer_setback(doer_tier: dict, field: str) -> int | None:
    """Extract a DOER setback value in ft for a given bucket + field."""
    if not doer_tier:
        return None
    return _parse_ft((doer_tier.get("setback_requirements") or {}).get(field))


def _town_setback(town_bylaw: dict, field: str) -> int | None:
    """Extract a town's setback value. Town-side uses
    ``setbacks_ft: {front, side, rear}`` (see scripts/seed_bylaws.py).
    """
    if not town_bylaw.get("setbacks_ft"):
        return None
    return _parse_ft(town_bylaw["setbacks_ft"].get(field))


# ---------------------------------------------------------------------------
# Per-bucket comparison
# ---------------------------------------------------------------------------
def _compare_bucket(town_bylaw: dict, doer_model: dict, bucket: dict) -> list[DoerDeviation]:
    out: list[DoerDeviation] = []
    doer_tier = _find_doer_tier(doer_model, bucket["doer_tier_name"]) or {}
    town_process = town_bylaw.get("process") or "site_plan_review"

    # ---- 1. Process severity
    sev = _process_severity_delta(town_process, bucket["doer_path"])
    if sev is not None:
        out.append(
            DoerDeviation(
                category="process_severity",
                severity=sev,
                tier_context=bucket["tier"],
                town_value=town_process.replace("_", " "),
                doer_value=bucket["doer_path"].replace("_", " "),
                summary=(
                    f"Town requires {town_process.replace('_', ' ')} "
                    f"where DOER model permits {bucket['doer_path'].replace('_', ' ')}."
                ),
                dover_risk=sev == "major",
                source_bylaw_ref=(town_bylaw.get("key_triggers") or [{}])[0].get("bylaw_ref"),
            )
        )

    # ---- 2. Setback delta — front/side/rear
    for field in ("front", "side", "rear"):
        town_ft = _town_setback(town_bylaw, field)
        doer_ft = _doer_setback(doer_tier, field)
        if town_ft is None or doer_ft is None:
            continue
        if town_ft <= doer_ft:
            continue
        ratio = town_ft / max(doer_ft, 1)
        if ratio >= 2.0:
            sev2: Severity = "major"
        elif ratio >= 1.5:
            sev2 = "moderate"
        else:
            sev2 = "minor"
        out.append(
            DoerDeviation(
                category="setback_delta",
                severity=sev2,
                tier_context=bucket["tier"],
                town_value=f"{town_ft} ft ({field})",
                doer_value=f"{doer_ft} ft ({field})",
                summary=(
                    f"Town {field} setback {town_ft} ft vs DOER model {doer_ft} ft "
                    f"({ratio:.1f}× stricter)."
                ),
                dover_risk=False,
            )
        )

    return out


# ---------------------------------------------------------------------------
# Town-wide checks (applied once, not per bucket)
# ---------------------------------------------------------------------------
def _compare_global(town_bylaw: dict, doer_model: dict) -> list[DoerDeviation]:
    out: list[DoerDeviation] = []

    # ---- Uniform treatment: town applies one process to all sizes
    # where DOER tiers by size. Fires specifically when the town's
    # single process is stricter than the *smallest* DOER tier (since
    # small/accessory solar is by-right under the model).
    town_process = town_bylaw.get("process") or "site_plan_review"
    smallest_doer_path = _DOER_GROUND_MOUNT_BUCKETS[0]["doer_path"]
    if _process_severity_delta(town_process, smallest_doer_path) is not None:
        out.append(
            DoerDeviation(
                category="uniform_treatment",
                severity="major",
                tier_context="all ground-mount tiers",
                town_value=f"{town_process} for all ground-mount solar",
                doer_value="tiered by size (by_right at ≤25 kW, SPR 25–250 kW, SP ≥250 kW)",
                summary=(
                    "Town applies a single process across all sizes where the DOER model "
                    "tiers by nameplate capacity. Tracer Lane II v. Waltham (2022) held "
                    "that restricting solar beyond what is needed to protect public "
                    "health/safety/welfare violates the Dover Amendment."
                ),
                dover_risk=True,
            )
        )

    # ---- Acreage cap
    cap = town_bylaw.get("acreage_cap")
    if cap is not None:
        out.append(
            DoerDeviation(
                category="acreage_cap_restriction",
                severity="major",
                tier_context="all ground-mount tiers",
                town_value=f"{cap}-acre cap",
                doer_value="no acreage cap in DOER model",
                summary=(
                    f"Town caps ground-mount solar at {cap} acres. DOER model imposes no "
                    "acreage cap; aggregate caps can trigger Dover Amendment scrutiny under "
                    "Tracer Lane II v. Waltham (2022)."
                ),
                dover_risk=True,
            )
        )

    # ---- Deforestation cap (Acton's 1-acre cap is the canonical example).
    defcap = town_bylaw.get("deforestation_cap_acres")
    if defcap is not None:
        out.append(
            DoerDeviation(
                category="deforestation_cap",
                severity="minor",
                tier_context="all ground-mount tiers",
                town_value=f"{defcap}-acre deforestation cap",
                doer_value="not addressed in DOER model",
                summary=(
                    f"Town imposes a {defcap}-acre deforestation cap per project. DOER "
                    "model does not address deforestation caps directly; this is "
                    "informational rather than a Dover Amendment risk."
                ),
                dover_risk=False,
            )
        )

    # ---- Overlay district restriction
    overlays = town_bylaw.get("overlay_districts") or []
    if overlays:
        out.append(
            DoerDeviation(
                category="overlay_restriction",
                severity="moderate",
                tier_context="all ground-mount tiers",
                town_value=f"permitted only in: {', '.join(overlays)}",
                doer_value="no overlay-only restriction",
                summary=(
                    "Town restricts ground-mount solar to specific overlay districts. "
                    "Kearsarge Walpole v. ZBA Walpole (2024) held that confining solar to "
                    "~2% overlay districts is impermissible under the Dover Amendment."
                ),
                dover_risk=True,
            )
        )

    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def compare_solar_to_doer_model(
    town_bylaws: dict | None,
    doer_model: dict,
) -> DoerComparisonResult:
    """Compare the town's ``solar_ground_mount`` rule to the DOER solar model.

    ``town_bylaws`` is the full ``project_type_bylaws`` JSONB from the
    municipality row (not just the solar section) so the engine can also
    surface cross-type flags later.
    """

    if not town_bylaws:
        return DoerComparisonResult(
            project_type="solar",
            comparison_available=False,
            reason_unavailable=(
                "No zoning data extracted for this town yet — run the research "
                "agent or seed via scripts.seed_bylaws."
            ),
            doer_version_compared=doer_model.get("version"),
        )

    solar_gm = town_bylaws.get("solar_ground_mount")
    if not solar_gm:
        return DoerComparisonResult(
            project_type="solar",
            comparison_available=False,
            reason_unavailable=(
                "Town's project_type_bylaws has no solar_ground_mount entry."
            ),
            doer_version_compared=doer_model.get("version"),
        )

    deviations: list[DoerDeviation] = []
    for bucket in _DOER_GROUND_MOUNT_BUCKETS:
        deviations.extend(_compare_bucket(solar_gm, doer_model, bucket))
    deviations.extend(_compare_global(solar_gm, doer_model))

    # Dedupe process_severity deviations that fire identically across buckets
    # (happens when the town has one rule covering multiple size ranges).
    seen: set[tuple] = set()
    deduped: list[DoerDeviation] = []
    for d in deviations:
        key = (
            d.category,
            d.severity,
            d.town_value,
            d.doer_value,
            # Uniform-treatment fires globally and already summarizes all tiers,
            # so if it's present suppress per-bucket process_severity dupes.
        )
        if d.category == "process_severity" and any(
            x.category == "uniform_treatment" for x in deviations
        ):
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(d)

    counts: dict[Severity, int] = {"minor": 0, "moderate": 0, "major": 0}
    for d in deduped:
        counts[d.severity] += 1

    return DoerComparisonResult(
        project_type="solar",
        comparison_available=True,
        deviations=deduped,
        deviation_counts=counts,
        dover_amendment_risk=any(d.dover_risk for d in deduped),
        doer_version_compared=doer_model.get("version"),
    )
