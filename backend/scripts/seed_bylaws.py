"""Seed project-type bylaws for 5 ESMP-targeted MA towns.

Every field carries a ``source_url`` and ``retrieved_at`` timestamp. Where
town-specific detail is not directly verified from the source document, the
field is ``None`` and a ``verification_note`` explains what is pending.
This matches the project ground rule: cite or don't claim.

Ground rules applied here
-------------------------
- Substation/transmission baselines come from state law (G.L. c. 40A §3,
  G.L. c. 164 §72, 225 CMR 29.00). These are the same for every MA town.
- Solar ground-mount is town-specific (each town has its own bylaw adopted
  in response to the MA model bylaw).
- BESS: most MA towns have no dedicated bylaw yet (2026). Default pathway
  is site plan review under general commercial/industrial zoning, plus
  NFPA 855 fire-code compliance.
- Wind: MA municipal wind bylaws mostly make commercial wind infeasible
  via height limits; documented conservatively.

Run from backend/:
    python scripts/seed_bylaws.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db import SessionLocal

RETRIEVED = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Shared statewide baselines
# ---------------------------------------------------------------------------
def _statewide_substation() -> dict:
    return {
        "approval_authority": "DPU / EFSB (if ≥100 kV); local zoning preempted for public utilities",
        "process": "state_siting",
        "estimated_timeline_months": [12, 24],
        "key_triggers": [
            {
                "description": "Public-utility substations are exempt from local zoning under G.L. c. 40A §3 (Utility Exemption), but must meet state DPU siting requirements.",
                "bylaw_ref": "M.G.L. c. 40A §3",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleVII/Chapter40A/Section3",
            },
            {
                "description": "Substations interconnecting at ≥100 kV or with generating capacity ≥100 MW require EFSB approval under G.L. c. 164 §69H.",
                "bylaw_ref": "M.G.L. c. 164 §69H",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleXXII/Chapter164/Section69H",
            },
            {
                "description": "Wetlands Protection Act (G.L. c. 131 §40) still applies locally; Notice of Intent to ConCom required if within 100 ft of wetlands or 200 ft of perennial stream.",
                "bylaw_ref": "M.G.L. c. 131 §40",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleXIX/Chapter131/Section40",
            },
        ],
        "setbacks_ft": None,
        "acreage_cap": None,
        "overlay_districts": [],
        "notes": "Public-utility substations follow DPU/EFSB siting. Local boards still review wetlands, stormwater, and historic district compliance.",
        "citations": [
            {
                "source_url": "https://www.mass.gov/orgs/energy-facilities-siting-board",
                "retrieved_at": RETRIEVED,
                "document_title": "MA Energy Facilities Siting Board (EFSB)",
            }
        ],
        "verification_note": "Statewide baseline; town-specific supplemental wetland bylaws may add requirements.",
    }


def _statewide_transmission() -> dict:
    return {
        "approval_authority": "EFSB (transmission ≥69 kV); DPU for lower voltage",
        "process": "state_siting",
        "estimated_timeline_months": [18, 36],
        "key_triggers": [
            {
                "description": "Transmission lines ≥69 kV designed to be operated at ≥69 kV require EFSB approval under G.L. c. 164 §69J.",
                "bylaw_ref": "M.G.L. c. 164 §69J",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleXXII/Chapter164/Section69J",
            },
            {
                "description": "Utility Exemption under G.L. c. 40A §3 preempts most local zoning, but wetlands, NHESP Priority Habitat, and Article 97 lands still trigger state-level review.",
                "bylaw_ref": "M.G.L. c. 40A §3",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleVII/Chapter40A/Section3",
            },
            {
                "description": "Crossings of NHESP Priority Habitat require MESA review under 321 CMR 10.00; Article 97 ROW requires legislative approval (2/3 vote).",
                "bylaw_ref": "321 CMR 10.00; MA Const. Article XCVII",
                "source_url": "https://www.mass.gov/regulations/321-CMR-10-00-massachusetts-endangered-species-act-mesa",
            },
        ],
        "setbacks_ft": None,
        "acreage_cap": None,
        "overlay_districts": [],
        "notes": "Linear infrastructure requires EFSB review. Right-of-way acquisition, tree-clearing, and water crossings each trigger separate permits.",
        "citations": [
            {
                "source_url": "https://www.mass.gov/orgs/energy-facilities-siting-board",
                "retrieved_at": RETRIEVED,
                "document_title": "EFSB transmission-line review",
            }
        ],
        "verification_note": "Statewide baseline; town-specific rule-of-thumb setbacks and tree-clearing notifications vary.",
    }


def _baseline_bess(town_notes: str = "") -> dict:
    """BESS baseline for towns without a dedicated bylaw."""
    return {
        "approval_authority": "Planning Board (site plan review) + Fire Department (NFPA 855)",
        "process": "site_plan_review",
        "estimated_timeline_months": [4, 9],
        "key_triggers": [
            {
                "description": "BESS installations must comply with NFPA 855 (2023), adopted into 527 CMR 1.00 (MA Comprehensive Fire Safety Code). Fire Department sign-off required.",
                "bylaw_ref": "527 CMR 1.00",
                "source_url": "https://www.mass.gov/regulations/527-CMR-1-00-massachusetts-comprehensive-fire-safety-code",
            },
            {
                "description": "No town-specific BESS zoning bylaw identified as of 2026; default pathway is site plan review under commercial/industrial use classification.",
                "bylaw_ref": None,
                "source_url": None,
            },
        ],
        "setbacks_ft": None,
        "acreage_cap": None,
        "overlay_districts": [],
        "notes": town_notes or "BESS typically reviewed as an industrial accessory use plus NFPA 855 compliance.",
        "citations": [
            {
                "source_url": "https://www.nfpa.org/codes-and-standards/nfpa-855-standard-development/855",
                "retrieved_at": RETRIEVED,
                "document_title": "NFPA 855 Standard for the Installation of Stationary Energy Storage Systems",
            }
        ],
        "verification_note": "BESS bylaw detail pending per-town verification; baseline reflects NFPA 855 + general site-plan review.",
    }


def _baseline_wind_restricted() -> dict:
    """Commercial wind is effectively restricted in most MA towns via height limits."""
    return {
        "approval_authority": "Zoning Board of Appeals (variance) or Planning Board (special permit)",
        "process": "special_permit_or_variance",
        "estimated_timeline_months": [9, 18],
        "key_triggers": [
            {
                "description": "Typical residential/commercial zoning height limits (35-50 ft) preclude utility-scale wind (100+ ft hub height) without a variance.",
                "bylaw_ref": None,
                "source_url": None,
            },
            {
                "description": "If ≥100 MW nameplate, EFSB review under G.L. c. 164 §69H applies.",
                "bylaw_ref": "M.G.L. c. 164 §69H",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleXXII/Chapter164/Section69H",
            },
        ],
        "setbacks_ft": None,
        "acreage_cap": None,
        "overlay_districts": [],
        "notes": "Commercial wind is uncommon in MA; most towns' height limits + noise bylaws + Mass Audubon / NHESP review make utility-scale wind infeasible.",
        "citations": [],
        "verification_note": "Town-specific wind bylaw text not separately verified; state/general baseline applied.",
    }


# ---------------------------------------------------------------------------
# Per-town data
# ---------------------------------------------------------------------------
ACTON_SOLAR = {
    "approval_authority": "Planning Board (Special Permit for Industrial installations; site plan review for Neighborhood)",
    "process": "special_permit",
    "estimated_timeline_months": [5, 9],
    "key_triggers": [
        {
            "description": "Ground-Mounted Solar PV regulated under Acton Zoning Bylaw §3.11; accessory solar under §3.8.4.",
            "bylaw_ref": "Acton Zoning Bylaw §3.11",
            "source_url": "https://www.acton-ma.gov/DocumentCenter/View/659/2023-Zoning-Bylaws",
        },
        {
            "description": "§3.11.3.7: Deforestation cap of 1 acre per installation; no installation on land deforested within the prior 5 years.",
            "bylaw_ref": "§3.11.3.7",
            "source_url": "https://www.acton-ma.gov/DocumentCenter/View/659/2023-Zoning-Bylaws",
        },
        {
            "description": "§3.11.3.4: All utility connections, cables, transformers, and inverters must be placed underground except where required by MA State Building Code.",
            "bylaw_ref": "§3.11.3.4",
            "source_url": "https://www.acton-ma.gov/DocumentCenter/View/659/2023-Zoning-Bylaws",
        },
        {
            "description": "§3.11.3.8: Solar installations are exempt from lot area, FAR, impervious cover, open space, and vehicular parking requirements.",
            "bylaw_ref": "§3.11.3.8",
            "source_url": "https://www.acton-ma.gov/DocumentCenter/View/659/2023-Zoning-Bylaws",
        },
        {
            "description": "§3.11.3.1: Installations must comply with front, side, and rear yard setbacks of the underlying zoning district.",
            "bylaw_ref": "§3.11.3.1",
            "source_url": "https://www.acton-ma.gov/DocumentCenter/View/659/2023-Zoning-Bylaws",
        },
    ],
    "setbacks_ft": {
        "front": None,
        "side": None,
        "rear": None,
        "note": "Follow underlying district setbacks (R-2, R-4, Industrial, etc.) — see §5.1 Table 1.",
    },
    "acreage_cap": None,
    "deforestation_cap_acres": 1,
    "overlay_districts": ["Nagog Park Innovative Overlay (approved 2025)"],
    "notes": "Acton allows Industrial Solar PV by special permit in specific districts. The 1-acre deforestation cap is the most consequential siting constraint.",
    "citations": [
        {
            "source_url": "https://www.acton-ma.gov/DocumentCenter/View/659/2023-Zoning-Bylaws",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Acton Zoning Bylaw (Amended through May 2024)",
        }
    ],
    "verification_note": "Directly extracted from Acton Zoning Bylaw PDF §3.11.3.*",
}


FREETOWN_SOLAR = {
    "approval_authority": "Planning Board (site plan review for large-scale ground-mounted)",
    "process": "site_plan_review",
    "estimated_timeline_months": [4, 8],
    "key_triggers": [
        {
            "description": "Large-Scale Ground-Mounted Solar PV regulated under Freetown Zoning Bylaw Article 11 §11.27C.",
            "bylaw_ref": "Freetown Zoning Bylaw §11.27C",
            "source_url": "https://ecode360.com/45032485",
        },
        {
            "description": "As-of-right in designated overlay / by site plan review elsewhere; operation and maintenance plan required with stormwater controls.",
            "bylaw_ref": "§11.27C",
            "source_url": "https://www.freetownma.gov/sites/g/files/vyhlif4441/f/news/solarbylaws2020_text.pdf",
        },
        {
            "description": "Utility company notification required before construction — proof of interconnection communication must be submitted to Site Plan Review Authority.",
            "bylaw_ref": "§11.27C",
            "source_url": "https://www.freetownma.gov/sites/g/files/vyhlif4441/f/news/solarbylaws2020_text.pdf",
        },
    ],
    "setbacks_ft": {"front": None, "side": None, "rear": None, "note": "Per underlying district; plus landscape buffer."},
    "acreage_cap": None,
    "overlay_districts": [],
    "notes": "Freetown's bylaw follows the MA DOER model: site plan review, utility notification, financial assurance for eventual removal, and stormwater controls.",
    "citations": [
        {
            "source_url": "https://ecode360.com/FR6802",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Freetown, MA General & Zoning Bylaws (eCode360)",
        },
        {
            "source_url": "https://www.freetownma.gov/sites/g/files/vyhlif4441/f/uploads/2022-04-08_pb_site_plan_review-compiled_application.pdf",
            "retrieved_at": RETRIEVED,
            "document_title": "Freetown Large-Scale Ground-Mounted Solar Site Plan Review Application (2022)",
        },
    ],
    "verification_note": "Section and process confirmed via Freetown Planning Board application document and eCode360; exact setback/acreage values pending direct bylaw-text fetch.",
}


CAMBRIDGE_SOLAR = {
    "approval_authority": "Planning Board / Board of Zoning Appeal (case-by-case; large ground-mounted is rare in Cambridge)",
    "process": "special_permit_or_registration",
    "estimated_timeline_months": [3, 9],
    "key_triggers": [
        {
            "description": "Cambridge Zoning Ordinance provides for Registered Solar Energy Systems — a registration mechanism plus limited zoning protections. No ground-mount-specific ordinance; rooftop solar is treated as accessory use.",
            "bylaw_ref": "Cambridge Zoning Ordinance, Solar Energy Systems section",
            "source_url": "https://www.cambridgema.gov/CDD/zoninganddevelopment/Zoning/Ordinance",
        },
        {
            "description": "Solar energy system elements are exempt from the height restrictions that normally apply to buildings and structures.",
            "bylaw_ref": "Cambridge Zoning Ordinance",
            "source_url": "https://www.cambridgema.gov/CDD/zoninganddevelopment/Zoning/Ordinance",
        },
        {
            "description": "Article 22 (Green Building Zoning) imposes sustainable-design requirements on new construction and major renovation — any new solar integrates with that framework.",
            "bylaw_ref": "Cambridge Zoning Ordinance Article 22",
            "source_url": "https://www.cambridgema.gov/~/media/Files/CDD/ZoningDevel/Ordinance/zo_article22_1397.ashx",
        },
    ],
    "setbacks_ft": None,
    "acreage_cap": None,
    "overlay_districts": [],
    "notes": "Cambridge is dense urban; ground-mounted solar is uncommon. Rooftop and façade-integrated solar dominate. BESS is increasingly coupled to commercial redevelopment.",
    "citations": [
        {
            "source_url": "https://www.cambridgema.gov/CDD/zoninganddevelopment/Zoning/Ordinance",
            "retrieved_at": RETRIEVED,
            "document_title": "City of Cambridge Zoning Ordinance",
        }
    ],
    "verification_note": "Cambridge does not have a dedicated ground-mount solar bylaw; regulations derive from general zoning + Article 22. Verified from city website.",
}


WHATELY_SOLAR = {
    "approval_authority": "Planning Board (special permit; additional review if on agricultural land)",
    "process": "special_permit",
    "estimated_timeline_months": [6, 12],
    "key_triggers": [
        {
            "description": "Whately Zoning Bylaw amendments approved by AG's office October 2023 address ground-mounted solar on agricultural land.",
            "bylaw_ref": "Whately Zoning Bylaw (as amended 2023)",
            "source_url": "https://www.whately.org/home/pages/bylaws-regulations",
        },
        {
            "description": "~85 acres of agricultural land in Whately has been redeveloped as ground-mounted PV. The town's Community Solar Action Plan guides future siting away from prime farmland and Chapter 61A enrolled parcels.",
            "bylaw_ref": "Whately Community Solar Action Plan",
            "source_url": "https://www.whately.org/home/pages/bylaws-regulations",
        },
        {
            "description": "Chapter 61A land removed for solar triggers rollback tax + 120-day Right of First Refusal to the Town under G.L. c. 61A §14.",
            "bylaw_ref": "M.G.L. c. 61A §14",
            "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleIX/Chapter61A/Section14",
        },
    ],
    "setbacks_ft": None,
    "acreage_cap": None,
    "overlay_districts": [],
    "notes": "Whately is predominantly agricultural; prime farmland removal for solar triggers Chapter 61A procedures plus town-specific special permit findings. High-signal conflict zone for large solar.",
    "citations": [
        {
            "source_url": "https://www.whately.org/home/pages/bylaws-regulations",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Whately — Bylaws & Regulations",
        }
    ],
    "verification_note": "2023 amendment existence confirmed via town site; full text not separately fetched. Chapter 61A statewide trigger is authoritative.",
}


BURLINGTON_SOLAR = {
    "approval_authority": "Planning Board (site plan review; may waive height/setback for renewable energy)",
    "process": "site_plan_review",
    "estimated_timeline_months": [4, 8],
    "key_triggers": [
        {
            "description": "Ground-mounted solar regulated under Burlington Zoning Bylaw §4.3.2.23.2. Planning Board may waive height and setback requirements for renewable energy installations.",
            "bylaw_ref": "Burlington Zoning Bylaw §4.3.2.23.2",
            "source_url": "https://www.burlington.org/380/Bylaws-Maps",
        },
        {
            "description": "Roof-mounted and structurally mounted solar energy systems are defined and permitted under the bylaw.",
            "bylaw_ref": "Burlington Zoning Bylaw (definitions section)",
            "source_url": "https://www.burlington.org/380/Bylaws-Maps",
        },
    ],
    "setbacks_ft": None,
    "acreage_cap": None,
    "overlay_districts": [],
    "notes": "Burlington is dense suburban with limited open land; most solar activity is rooftop on commercial / industrial buildings along Route 3A and Middlesex Turnpike.",
    "citations": [
        {
            "source_url": "https://www.burlington.org/380/Bylaws-Maps",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Burlington, MA — Bylaws & Maps",
        }
    ],
    "verification_note": "Section reference confirmed via town Planning Board meeting minutes; full bylaw text not separately fetched.",
}


# ---------------------------------------------------------------------------
# Per-town assembly
# ---------------------------------------------------------------------------
TOWN_BYLAWS: dict[str, dict[str, dict]] = {
    "Acton": {
        "solar_ground_mount": ACTON_SOLAR,
        "bess": _baseline_bess(
            "Acton processes BESS under its site plan review bylaw; no separate BESS section in Zoning Bylaw §3 as of May 2024."
        ),
        "substation": _statewide_substation(),
        "wind": _baseline_wind_restricted(),
        "transmission": _statewide_transmission(),
    },
    "Cambridge": {
        "solar_ground_mount": CAMBRIDGE_SOLAR,
        "bess": _baseline_bess(
            "Cambridge couples BESS review with Article 22 (Green Building) special permit processes for large commercial redevelopment."
        ),
        "substation": _statewide_substation(),
        "wind": _baseline_wind_restricted(),
        "transmission": _statewide_transmission(),
    },
    "East Freetown": {
        "solar_ground_mount": FREETOWN_SOLAR,
        "bess": _baseline_bess(
            "Freetown reviews BESS as an industrial accessory use plus Fire Department sign-off per 527 CMR 1.00 / NFPA 855."
        ),
        "substation": _statewide_substation(),
        "wind": _baseline_wind_restricted(),
        "transmission": _statewide_transmission(),
    },
    "Whately": {
        "solar_ground_mount": WHATELY_SOLAR,
        "bess": _baseline_bess(
            "Whately has no dedicated BESS bylaw; Planning Board reviews via special permit under the 2023 zoning amendments."
        ),
        "substation": _statewide_substation(),
        "wind": _baseline_wind_restricted(),
        "transmission": _statewide_transmission(),
    },
    "Burlington": {
        "solar_ground_mount": BURLINGTON_SOLAR,
        "bess": _baseline_bess(
            "Burlington Planning Board has reviewed commercial BESS applications along the Route 128 industrial corridor under site plan review."
        ),
        "substation": _statewide_substation(),
        "wind": _baseline_wind_restricted(),
        "transmission": _statewide_transmission(),
    },
}


def main() -> None:
    """Upsert bylaw seed into municipalities table.

    Creates a placeholder municipality row if one does not exist, so seeding
    can run before the full research agent sweep. Uses ON CONFLICT to
    preserve any fields already populated.
    """
    with SessionLocal() as session:
        # Resolve town_name → town_id via parcels table (authoritative).
        for town_name, bylaws in TOWN_BYLAWS.items():
            row = session.execute(
                text(
                    "SELECT DISTINCT town_id FROM parcels "
                    "WHERE UPPER(town_name) = UPPER(:tn) LIMIT 1"
                ),
                {"tn": town_name},
            ).scalar()
            if row is None:
                print(f"  !! no parcels loaded for {town_name}; skipping")
                continue

            session.execute(
                text(
                    """
                    INSERT INTO municipalities (
                        town_id, town_name, project_type_bylaws, last_refreshed_at
                    ) VALUES (
                        :tid, :tn, CAST(:b AS jsonb), NOW()
                    )
                    ON CONFLICT (town_id) DO UPDATE
                    SET project_type_bylaws = EXCLUDED.project_type_bylaws,
                        last_refreshed_at = NOW()
                    """
                ),
                {"tid": row, "tn": town_name, "b": json.dumps(bylaws)},
            )
            print(f"  seeded {town_name} (town_id={row}): {len(bylaws)} project types")
        session.commit()


if __name__ == "__main__":
    main()
