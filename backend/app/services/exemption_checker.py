"""Exemption checker for 225 CMR 29.07(1).

Six rules from the MA Small Clean Energy Infrastructure Siting regulation:

  1. Site footprint < 1 acre
  2. Solar with rated nameplate capacity ≤ 25 kW AC
  3. Behind-the-meter generation facility (any size)
  4. Accessory-use behind-the-meter facility
  5. T&D facilities located in existing public right of way
  6. T&D facilities with design rating ≤ 20 kV AC

Pure function; no DB access, no external calls. The caller supplies
whatever project spec fields they know; unknowns stay None and the
checker returns ``is_exempt=None`` with the list of missing fields so
the UI can ask for the right inputs rather than guess.

Project-type codes follow the existing Civo enum
(see ``municipality.ProjectTypeCode``):

  solar_ground_mount / solar_rooftop / solar_canopy
  bess_standalone / bess_colocated
  substation / transmission
  ev_charging
"""

from __future__ import annotations

from app.scoring.models import ExemptionCheck

SOLAR_TYPES = {"solar_ground_mount", "solar_rooftop", "solar_canopy"}
TD_TYPES = {"transmission", "substation"}  # T&D per 225 CMR 29.07(1)


def check_exemption(
    project_type: str,
    nameplate_capacity_kw: float | None = None,
    site_footprint_acres: float | None = None,
    is_behind_meter: bool = False,
    is_accessory_use: bool = False,
    in_existing_public_row: bool = False,
    td_design_rating_kv: float | None = None,
) -> ExemptionCheck:
    """Evaluate exemption rules in 225 CMR 29.07(1) precedence order.

    Checks in this order (first match wins):
      1. Behind-the-meter (any size) — covers rules 3 and 4.
      2. T&D in existing public ROW or ≤ 20 kV — covers rules 5 and 6.
      3. Solar ≤ 25 kW AC — rule 2.
      4. Site footprint < 1 acre — rule 1.

    Returns ``is_exempt=None`` with ``missing_fields`` populated when
    the caller hasn't provided enough info to decide.
    """

    # -------------------------------------------------------------------
    # Rule 3 + 4 — behind-the-meter (regardless of size).
    # -------------------------------------------------------------------
    if is_behind_meter:
        reason = (
            "behind-the-meter accessory-use facility"
            if is_accessory_use
            else "behind-the-meter generation facility"
        )
        return ExemptionCheck(is_exempt=True, reason=reason)

    # -------------------------------------------------------------------
    # Rules 5 + 6 — T&D (transmission / substation) exemptions.
    # -------------------------------------------------------------------
    if project_type in TD_TYPES:
        if in_existing_public_row:
            return ExemptionCheck(
                is_exempt=True,
                reason="T&D facility in existing public right of way",
            )
        if td_design_rating_kv is not None and td_design_rating_kv <= 20.0:
            return ExemptionCheck(
                is_exempt=True,
                reason=f"T&D facility rated ≤ 20 kV AC ({td_design_rating_kv:g} kV)",
            )
        # T&D that's not in ROW and not ≤20 kV isn't exempt on those rules,
        # but could still be exempt under the <1 acre rule below.

    # -------------------------------------------------------------------
    # Rule 2 — solar with capacity ≤ 25 kW AC (the household-scale threshold).
    # -------------------------------------------------------------------
    if project_type in SOLAR_TYPES:
        if nameplate_capacity_kw is not None and nameplate_capacity_kw <= 25.0:
            return ExemptionCheck(
                is_exempt=True,
                reason=f"solar ≤ 25 kW AC ({nameplate_capacity_kw:g} kW nameplate)",
            )

    # -------------------------------------------------------------------
    # Rule 1 — site footprint < 1 acre applies to any project type.
    # -------------------------------------------------------------------
    if site_footprint_acres is not None and site_footprint_acres < 1.0:
        return ExemptionCheck(
            is_exempt=True,
            reason=f"site footprint < 1 acre ({site_footprint_acres:g} acres)",
        )

    # -------------------------------------------------------------------
    # No rule matched. Decide between "not exempt" and "insufficient data".
    # -------------------------------------------------------------------
    missing: list[str] = []
    if site_footprint_acres is None:
        missing.append("site_footprint_acres")
    if project_type in SOLAR_TYPES and nameplate_capacity_kw is None:
        missing.append("nameplate_capacity_kw")
    if project_type in TD_TYPES and td_design_rating_kv is None:
        missing.append("td_design_rating_kv")

    if missing:
        return ExemptionCheck(
            is_exempt=None,
            reason="insufficient_data",
            missing_fields=missing,
        )

    return ExemptionCheck(
        is_exempt=False,
        reason="no exemption rule in 225 CMR 29.07(1) applies",
    )
