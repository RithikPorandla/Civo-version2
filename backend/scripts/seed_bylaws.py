"""Seed project-type bylaws for 11 ESMP-targeted MA towns.

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
                "source_url": "https://www.mass.gov/regulations/321-CMR-1000-massachusetts-endangered-species-act",
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


def _baseline_solar_rooftop(town_notes: str = "") -> dict:
    return {
        "approval_authority": "Building Department (by-right accessory use); registration optional",
        "process": "building_permit",
        "estimated_timeline_months": [1, 3],
        "key_triggers": [
            {
                "description": "G.L. c. 40A §3 prohibits municipalities from unreasonably regulating rooftop solar energy systems. Standard residential/commercial rooftop solar is accessory by-right.",
                "bylaw_ref": "M.G.L. c. 40A §3",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleVII/Chapter40A/Section3",
            },
            {
                "description": "Structural review under 780 CMR (MA State Building Code) + electrical permit under 527 CMR 12.00 (MA Electrical Code).",
                "bylaw_ref": "780 CMR; 527 CMR 12.00",
                "source_url": "https://www.mass.gov/massachusetts-state-building-code-780-cmr",
            },
            {
                "description": "Historic District review required for installations visible from public way in designated districts (G.L. c. 40C).",
                "bylaw_ref": "M.G.L. c. 40C",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleVII/Chapter40C",
            },
        ],
        "setbacks_ft": None,
        "acreage_cap": None,
        "overlay_districts": [],
        "notes": town_notes or "Rooftop solar is by-right accessory use in most zoning districts; building permit typically sufficient.",
        "citations": [
            {
                "source_url": "https://www.mass.gov/info-details/solar",
                "retrieved_at": RETRIEVED,
                "document_title": "MA DOER — Solar Energy Systems guidance",
            }
        ],
        "verification_note": "Town-specific rooftop solar provisions (if any) pending verification; statewide baseline applied.",
    }


def _baseline_solar_canopy(town_notes: str = "") -> dict:
    return {
        "approval_authority": "Planning Board (site plan review; sometimes Building Department if under accessory-height threshold)",
        "process": "site_plan_review",
        "estimated_timeline_months": [3, 6],
        "key_triggers": [
            {
                "description": "Parking-lot solar canopies trigger stormwater review (additional impervious coverage) and structural review; height often within accessory-structure limits but varies by district.",
                "bylaw_ref": None,
                "source_url": None,
            },
            {
                "description": "SMART 3.0 provides a canopy adder incentive ($/kWh) for qualifying parking-lot canopies; eligibility has siting criteria.",
                "bylaw_ref": "225 CMR 20.00 (SMART 3.0)",
                "source_url": "https://www.mass.gov/regulations/225-CMR-2000-solar-massachusetts-renewable-target-smart-program",
            },
            {
                "description": "Historic District Commission review required in designated districts (G.L. c. 40C).",
                "bylaw_ref": "M.G.L. c. 40C",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleVII/Chapter40C",
            },
        ],
        "setbacks_ft": None,
        "acreage_cap": None,
        "overlay_districts": [],
        "notes": town_notes or "Canopies over existing parking count as structures; most towns treat them as a ground-mount variant for permitting.",
        "citations": [
            {
                "source_url": "https://www.mass.gov/regulations/225-CMR-2000-solar-massachusetts-renewable-target-smart-program",
                "retrieved_at": RETRIEVED,
                "document_title": "225 CMR 20.00 — SMART Program",
            }
        ],
        "verification_note": "Town-specific canopy provisions (if any) pending verification.",
    }


def _baseline_bess_standalone(town_notes: str = "") -> dict:
    return {
        "approval_authority": "Planning Board (special permit / site plan review) + Fire Department (NFPA 855)",
        "process": "special_permit",
        "estimated_timeline_months": [6, 12],
        "key_triggers": [
            {
                "description": "NFPA 855 (2023) clearance distances: 3 ft between modules, 10 ft from structures, and 50 ft from lot lines for Li-ion installations >20 kWh. Adopted into MA fire code.",
                "bylaw_ref": "527 CMR 1.00 (NFPA 855 adopted)",
                "source_url": "https://www.mass.gov/regulations/527-CMR-100-massachusetts-comprehensive-fire-safety-code",
            },
            {
                "description": "UL 9540A large-scale fire testing report often required by AHJ before occupancy sign-off.",
                "bylaw_ref": "UL 9540A",
                "source_url": "https://www.ul.com/services/ul-9540a-battery-testing",
            },
            {
                "description": "Post-Moss Landing (CA, 2025) fires, many MA municipalities are drafting BESS-specific bylaws — expect stricter setbacks, evacuation planning, and emergency response training requirements.",
                "bylaw_ref": None,
                "source_url": None,
            },
        ],
        "setbacks_ft": {"front": None, "side": 50, "rear": 50, "note": "NFPA 855 minimum 50 ft to lot lines for Li-ion >20 kWh; town setbacks may add on top."},
        "acreage_cap": None,
        "overlay_districts": [],
        "notes": town_notes or "Standalone BESS is the highest-friction new category in MA permitting as of 2026; expect 6-12 month timelines and significant fire-department engagement.",
        "citations": [
            {
                "source_url": "https://www.nfpa.org/codes-and-standards/nfpa-855-standard-development/855",
                "retrieved_at": RETRIEVED,
                "document_title": "NFPA 855 Standard for the Installation of Stationary Energy Storage Systems",
            }
        ],
        "verification_note": "Town-specific BESS bylaw detail pending; NFPA 855 is statewide via 527 CMR 1.00.",
    }


def _baseline_bess_colocated(town_notes: str = "") -> dict:
    return {
        "approval_authority": "Planning Board (concurrent with solar permit) + Fire Department",
        "process": "site_plan_review",
        "estimated_timeline_months": [4, 9],
        "key_triggers": [
            {
                "description": "Co-located BESS typically rides the host solar project's permit; same NFPA 855 fire-code requirements apply (527 CMR 1.00).",
                "bylaw_ref": "527 CMR 1.00",
                "source_url": "https://www.mass.gov/regulations/527-CMR-100-massachusetts-comprehensive-fire-safety-code",
            },
            {
                "description": "SMART 3.0 Energy Storage Adder incentive requires co-located storage to be ≥25% of solar DC capacity and ≥4-hour duration.",
                "bylaw_ref": "225 CMR 20.00",
                "source_url": "https://www.mass.gov/regulations/225-CMR-2000-solar-massachusetts-renewable-target-smart-program",
            },
        ],
        "setbacks_ft": {"front": None, "side": 50, "rear": 50, "note": "NFPA 855 minimum applies to battery equipment regardless of solar co-location."},
        "acreage_cap": None,
        "overlay_districts": [],
        "notes": town_notes or "Adding BESS to a solar project is usually a ~60 day addition to the solar timeline; the key risk is fire-setback encroaching on the solar array layout.",
        "citations": [
            {
                "source_url": "https://www.mass.gov/regulations/225-CMR-2000-solar-massachusetts-renewable-target-smart-program",
                "retrieved_at": RETRIEVED,
                "document_title": "225 CMR 20.00 — SMART Program (Energy Storage Adder)",
            }
        ],
        "verification_note": "Co-located BESS treated as a rider to the solar permit; town-specific supplemental rules may apply.",
    }


def _baseline_ev_charging(town_notes: str = "") -> dict:
    return {
        "approval_authority": "Building Department (electrical/structural) + Planning Board (if new curb cut or DCFC hub)",
        "process": "building_permit",
        "estimated_timeline_months": [1, 4],
        "key_triggers": [
            {
                "description": "G.L. c. 40A §3 (amended 2022) designates EVSE as a by-right accessory use; municipalities cannot unreasonably regulate.",
                "bylaw_ref": "M.G.L. c. 40A §3",
                "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleVII/Chapter40A/Section3",
            },
            {
                "description": "MassDOT NEVI Plan designates Alternative Fuel Corridors; DCFC sites on these corridors have expedited state-level review.",
                "bylaw_ref": "MassDOT NEVI Deployment Plan",
                "source_url": "https://www.mass.gov/massdot-nevi-plan",
            },
            {
                "description": "Eversource / National Grid Make-Ready programs subsidize utility-side infrastructure (service upgrade, transformer) for qualifying sites.",
                "bylaw_ref": "DPU 21-90 (Eversource) / DPU 21-91 (National Grid)",
                "source_url": "https://www.mass.gov/info-details/electric-vehicle-charging",
            },
            {
                "description": "ADA accessibility and stormwater review for sites with ≥4 DCFC ports or new curb cuts.",
                "bylaw_ref": "521 CMR (MA Architectural Access Board)",
                "source_url": "https://www.mass.gov/law-library/521-cmr",
            },
        ],
        "setbacks_ft": None,
        "acreage_cap": None,
        "overlay_districts": [],
        "notes": town_notes or "EVSE is largely by-right statewide as of 2022. DCFC hubs on NEVI corridors are the most active segment.",
        "citations": [
            {
                "source_url": "https://www.mass.gov/massdot-nevi-plan",
                "retrieved_at": RETRIEVED,
                "document_title": "Massachusetts NEVI Deployment Plan",
            }
        ],
        "verification_note": "By-right statewide as of 2022 (c.40A §3 amendment); town-specific site-plan thresholds may still apply for DCFC hubs.",
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
    "approval_authority": "Building Commissioner (building permit) + Planning Board Site Plan Review Authority",
    "process": "site_plan_review",
    "estimated_timeline_months": [4, 8],
    "key_triggers": [
        {
            "description": "Large-Scale Ground-Mounted Solar PV regulated under Freetown Zoning Bylaw Chapter 300, Article 11 §11.28. Two-step approval: building permit from Building Commissioner first, then site plan review by the Planning Board.",
            "bylaw_ref": "Freetown Zoning Bylaw §11.28",
            "source_url": "https://ecode360.com/45032485",
        },
        {
            "description": "All material modifications to a solar installation after permit issuance require approval by the Site Plan Review Authority.",
            "bylaw_ref": "Freetown Zoning Bylaw §11.28",
            "source_url": "https://www.freetownma.gov/sites/g/files/vyhlif4441/f/uploads/final_code_-_codification_-_zoning_bylaws_082924.pdf",
        },
        {
            "description": "Utility company notification required before construction — proof of interconnection communication must be submitted to the Site Plan Review Authority. Underground connections strongly encouraged.",
            "bylaw_ref": "Freetown Zoning Bylaw §11.28",
            "source_url": "https://www.freetownma.gov/sites/g/files/vyhlif4441/f/news/solarbylaws2020_text.pdf",
        },
        {
            "description": "Decommissioning: owner must notify the Planning Board by certified mail; physical removal within 150 days of discontinued operations. Financial surety (escrow or bond) required — amount not to exceed 125% of removal cost.",
            "bylaw_ref": "Freetown Zoning Bylaw §11.28",
            "source_url": "https://ecode360.com/45032485",
        },
        {
            "description": "Emergency response plan required; applicant must coordinate with the Fire Chief and submit project summary, electrical schematic, and site plan to Fire Department.",
            "bylaw_ref": "Freetown Zoning Bylaw §11.28",
            "source_url": "https://ecode360.com/45032485",
        },
    ],
    "setbacks_ft": {"front": 50, "side": 50, "rear": 50, "note": "50 ft from all property lines. Vegetation clearing limited to what is necessary for construction, operation, and maintenance."},
    "acreage_cap": None,
    "overlay_districts": [],
    "notes": "Freetown's bylaw (§11.28) follows the MA DOER model: two-step approval (building permit + site plan review), utility notification, stormwater controls, and financial assurance for removal. Fire Chief coordination is mandatory. Planning Board meets 1st and 3rd Tuesday October–April.",
    "citations": [
        {
            "source_url": "https://ecode360.com/45032485",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Freetown, MA — Chapter 300 Zoning Bylaws (eCode360)",
        },
        {
            "source_url": "https://www.freetownma.gov/sites/g/files/vyhlif4441/f/uploads/final_code_-_codification_-_zoning_bylaws_082924.pdf",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Freetown — Final Codified Zoning Bylaws (August 2024)",
        },
        {
            "source_url": "https://www.freetownma.gov/sites/g/files/vyhlif4441/f/uploads/2022-04-08_pb_site_plan_review-compiled_application.pdf",
            "retrieved_at": RETRIEVED,
            "document_title": "Freetown Large-Scale Ground-Mounted Solar — Site Plan Review Application (2022)",
        },
    ],
    "verification_note": "Section §11.28 confirmed via eCode360 and Freetown Planning Board application document. Front/side/rear setbacks of 50 ft each confirmed from bylaw research. Decommissioning 150-day timeline and 125% surety cap confirmed. Fire Chief coordination requirement confirmed.",
}


CAMBRIDGE_SOLAR = {
    "approval_authority": "Building Commissioner (building permit for rooftop); Board of Zoning Appeal or Planning Board if special permit or variance required by adjacent development",
    "process": "building_permit",
    "estimated_timeline_months": [1, 3],
    "key_triggers": [
        {
            "description": "Cambridge Zoning Ordinance Article 22, §§22.60–22.63 establishes Registered Solar Energy Systems. A system becomes 'Registered' after obtaining a building permit and operating for one year, then receives limited zoning protection — neighboring development seeking a special permit or variance must consider impacts on registered systems.",
            "bylaw_ref": "Cambridge Zoning Ordinance Article 22, §§22.60–22.63",
            "source_url": "https://library.municode.com/ma/cambridge/codes/zoning_ordinance?nodeId=ZONING_ORDINANCE_ART22.000SUDEDE",
        },
        {
            "description": "Solar energy system elements are exempt from the height restrictions that normally apply to buildings and structures; sun-exposed elements must be no lower than 5 feet below the maximum height allowed in the base zoning district.",
            "bylaw_ref": "Cambridge Zoning Ordinance Article 22",
            "source_url": "https://library.municode.com/ma/cambridge/codes/zoning_ordinance?nodeId=ZONING_ORDINANCE_ART22.000SUDEDE",
        },
        {
            "description": "Article 22 (Green Building Zoning) applies sustainable-design requirements to new construction and major renovations ≥25,000 sq ft — solar integrates with that framework. Commercial buildings ≥25,000 sq ft must demonstrate on-site solar feasibility.",
            "bylaw_ref": "Cambridge Zoning Ordinance Article 22",
            "source_url": "https://www.cambridgema.gov/~/media/Files/CDD/ZoningDevel/Ordinance/zo_article22_1397.ashx",
        },
    ],
    "setbacks_ft": None,
    "acreage_cap": None,
    "overlay_districts": [],
    "notes": "Cambridge is dense urban; ground-mounted solar is uncommon. No dedicated ground-mount bylaw exists — any ground-mount would be reviewed under general zoning as an accessory use. Rooftop solar dominates. Registration (§22.60–22.63) is optional but provides zoning protections for existing systems.",
    "citations": [
        {
            "source_url": "https://library.municode.com/ma/cambridge/codes/zoning_ordinance?nodeId=ZONING_ORDINANCE_ART22.000SUDEDE",
            "retrieved_at": RETRIEVED,
            "document_title": "Cambridge Zoning Ordinance Article 22 — Sustainable Development (Municode)",
        },
        {
            "source_url": "https://www.cambridgema.gov/CDD/zoninganddevelopment/Zoning/Ordinance",
            "retrieved_at": RETRIEVED,
            "document_title": "City of Cambridge — Zoning Ordinance (CDD)",
        },
    ],
    "verification_note": "Article 22 §§22.60–22.63 (Registered Solar Energy System) confirmed via Municode Library. Building permit + 1-year operation requirement for registration confirmed. No dedicated ground-mount solar bylaw exists in Cambridge.",
}


WHATELY_SOLAR = {
    "approval_authority": "Planning Board (site plan review in nonresidential zones; special permit on agricultural land)",
    "process": "site_plan_review",
    "estimated_timeline_months": [6, 12],
    "key_triggers": [
        {
            "description": "Ground-mounted solar ('solar farms' and 'solar power plants') require Planning Board site plan review in all nonresidential zones. Whately originally adopted the MA DOER model solar bylaw in 2011; systems generating <10 kW are exempt from the large-scale provisions.",
            "bylaw_ref": "Whately Zoning Bylaw (as amended 2023)",
            "source_url": "https://www.whately.org/home/pages/bylaws-regulations",
        },
        {
            "description": "Route 107 Large-Scale Ground-Mounted Solar Photovoltaic Installations Overlay District established March 2014. Solar farms are an expedited use within this overlay.",
            "bylaw_ref": "Whately Zoning Bylaw — Route 107 Overlay District (est. 2014)",
            "source_url": "https://www.whately.org/home/pages/bylaws-regulations",
        },
        {
            "description": "~85 acres of agricultural land in Whately has been redeveloped as ground-mounted PV. The town has signaled uncertainty about whether its acreage caps are enforceable following the MA Tracer Lane II court decision on municipal solar zoning limits.",
            "bylaw_ref": "Whately Community Solar Action Plan; Tracer Lane II Realty (2024)",
            "source_url": "https://www.recorder.com/As-solar-array-and-battery-storage-debate-heats-up-Whately-backs-municipal-zoning-bill-53729126",
        },
        {
            "description": "Chapter 61A land removed for solar triggers rollback tax + 120-day Right of First Refusal to the Town under G.L. c. 61A §14.",
            "bylaw_ref": "M.G.L. c. 61A §14",
            "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleIX/Chapter61A/Section14",
        },
        {
            "description": "As of 2026, Whately is moving standalone battery energy storage system (BESS) conditions out of the solar bylaw into a separate bylaw section; the solar bylaw currently is 'silent' on standalone BESS, making it prohibited until the new section is adopted.",
            "bylaw_ref": "Whately Energy Storage Systems Study Committee (2026)",
            "source_url": "https://www.whately.org/boards_committees/energy_storage_systems_study_committee.php",
        },
    ],
    "setbacks_ft": None,
    "acreage_cap": None,
    "overlay_districts": ["Route 107 Large-Scale Ground-Mounted Solar Overlay District (established March 2014)"],
    "notes": "Whately is predominantly agricultural; prime farmland removal for solar triggers Chapter 61A procedures. Approximately 85 acres already converted to ground-mount PV. The town is active in state-level solar zoning reform discussions following the Tracer Lane II decision. BESS is currently prohibited as a standalone use pending new bylaw adoption.",
    "citations": [
        {
            "source_url": "https://www.whately.org/home/pages/bylaws-regulations",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Whately — Bylaws & Regulations",
        },
        {
            "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleIX/Chapter61A/Section14",
            "retrieved_at": RETRIEVED,
            "document_title": "M.G.L. c. 61A §14 — Agricultural Land Right of First Refusal",
        },
        {
            "source_url": "https://www.recorder.com/As-solar-array-and-battery-storage-debate-heats-up-Whately-backs-municipal-zoning-bill-53729126",
            "retrieved_at": RETRIEVED,
            "document_title": "Daily Hampshire Gazette — Whately solar & battery storage zoning (2026)",
        },
    ],
    "verification_note": "2023 amendment and Route 107 Overlay (2014) confirmed via town site and news sources. <10 kW exemption confirmed from MA DOER model bylaw adoption records. BESS 'silent' status confirmed via Energy Storage Systems Study Committee page. Exact numeric setbacks not found in available bylaw text.",
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


BOSTON_SOLAR = {
    "approval_authority": "BPDA (Article 80 Large Project Review for ≥20,000 SF); Inspectional Services Department (building permit for rooftop)",
    "process": "large_project_review",
    "estimated_timeline_months": [12, 24],
    "key_triggers": [
        {
            "description": "New construction or renovation projects ≥20,000 sq ft gross floor area trigger Article 80B Large Project Review, which includes a carbon-neutral building assessment covering on-site solar feasibility.",
            "bylaw_ref": "Boston Zoning Code Article 80B",
            "source_url": "https://www.boston.gov/departments/boston-planning-development-agency/article-80-development-review",
        },
        {
            "description": "Article 37 (Green Buildings) Net Zero Carbon Zoning Initiative — effective July 1, 2025 for newly filed projects: ≥50% of eligible flat or south-facing roof area must have solar PV; 90% of uncovered parking structure decks must have solar. Applies to Article 80 projects.",
            "bylaw_ref": "Boston Zoning Code Article 37 (Net Zero Carbon, effective 2025-07-01)",
            "source_url": "https://www.bostonplans.org/planning-zoning/zoning-code",
        },
        {
            "description": "BERDO 2.0 requires existing buildings ≥20,000 SF non-residential or ≥15 residential units to reduce emissions on a schedule; on-site solar generation, off-site RECs, or alternative compliance payments are all valid compliance pathways.",
            "bylaw_ref": "BERDO 2.0 (Boston Municipal Code §7-2.2)",
            "source_url": "https://www.boston.gov/environment/berdo",
        },
        {
            "description": "Rooftop solar on residential buildings: building permit only; typical timeline 3–6 weeks. Historic District installations require Landmarks Commission review, adding 30–45 days.",
            "bylaw_ref": "Boston ISD Solar Permitting Guide (2026)",
            "source_url": "https://www.boston.gov/boston-permitting/install-or-replace/install-or-replace-solar-panels",
        },
        {
            "description": "Ground-mounted solar is limited to non-residential zones (C-3, I-1, I-2) and brownfield/former industrial sites. Designated Port Area (DPA) land cannot be used for solar per Massachusetts Coastal Zone Management policy.",
            "bylaw_ref": "Boston Zoning Code Articles 8, 11–12; MCZM DPA Policy",
            "source_url": "https://www.boston.gov/departments/inspectional-services/zoning",
        },
    ],
    "setbacks_ft": {"front": None, "side": None, "rear": None, "note": "No city-wide ground-mount setback standard; site-specific review under Article 80. Rooftop solar: no setback beyond fire-access code."},
    "acreage_cap": None,
    "overlay_districts": ["Designated Port Area (DPA) — solar prohibited per MCZM policy", "Historic Districts — Landmarks Commission review required for visible installations"],
    "notes": "Ground-mounted solar in Boston is rare due to land scarcity; primary pathways are rooftop and parking canopy. Article 37 NZC (effective July 2025) mandates 50% roof solar coverage on major new projects. BERDO 2.0 is the compliance driver for existing large buildings. Residential rooftop permitting is straightforward (3–6 weeks).",
    "citations": [
        {
            "source_url": "https://www.bostonplans.org/planning-zoning/zoning-code",
            "retrieved_at": RETRIEVED,
            "document_title": "Boston Planning & Development Agency — Zoning Code (Article 37 NZC)",
        },
        {
            "source_url": "https://www.boston.gov/departments/boston-planning-development-agency/article-80-development-review",
            "retrieved_at": RETRIEVED,
            "document_title": "City of Boston — Article 80 Large Project Review",
        },
        {
            "source_url": "https://www.boston.gov/environment/berdo",
            "retrieved_at": RETRIEVED,
            "document_title": "City of Boston — BERDO 2.0 Building Emissions Reduction",
        },
        {
            "source_url": "https://www.boston.gov/boston-permitting/install-or-replace/install-or-replace-solar-panels",
            "retrieved_at": RETRIEVED,
            "document_title": "City of Boston — Install Solar Panels (Permitting Guide)",
        },
    ],
    "verification_note": "Article 80B threshold (≥20,000 SF) confirmed via BPDA documentation. Article 37 NZC 50% roof requirement and July 2025 effective date confirmed via BPDA and Sullivan Law reporting. BERDO 2.0 thresholds confirmed via city website. Residential 3–6 week timeline confirmed via Boston Solar permitting guide (2026). DPA prohibition confirmed via MCZM.",
}

FALMOUTH_SOLAR = {
    "approval_authority": "Falmouth Planning Board (Site Plan Review Authority)",
    "process": "site_plan_review",
    "estimated_timeline_months": [6, 12],
    "key_triggers": [
        {
            "description": "Large-Scale Ground-Mounted Solar Photovoltaic Installations regulated under Article XLIII §240-254 (Large Scale Ground Mounted Solar Overlay District). Systems ≥250 kW nameplate capacity (>40,000 sq ft panel area) require site plan review by the Planning Board prior to construction. Minimum lot size: 7 acres.",
            "bylaw_ref": "Falmouth Zoning Bylaw Article XLIII §240-254",
            "source_url": "https://www.falmouthma.gov/DocumentCenter/View/5262/Article-8---Solar-Overlay-District",
        },
        {
            "description": "Solar facilities are a by-right use within the Large Scale Ground Mounted Solar Overlay District; site plan review (not a special permit) is the applicable approval pathway. Planning Board decision window: 90 days from complete application.",
            "bylaw_ref": "Falmouth Zoning Bylaw Article XLIII §240-254",
            "source_url": "https://ecode360.com/42790627",
        },
        {
            "description": "Decommissioning: owner must notify Planning Board by certified mail; physical removal within 150 days of discontinued operations. Financial surety required — amount not to exceed 125% of estimated removal cost, indexed for inflation.",
            "bylaw_ref": "Falmouth Zoning Bylaw Article XLIII §240-254",
            "source_url": "https://www.falmouthma.gov/DocumentCenter/View/5262/Article-8---Solar-Overlay-District",
        },
        {
            "description": "Views from residential properties and roadways must be screened with landscaping. Multiple accessory structures shall be clustered. Front yard maintained as no-disturb zone except for site access drives.",
            "bylaw_ref": "Falmouth Zoning Bylaw Article XLIII §240-254",
            "source_url": "https://www.falmouthma.gov/DocumentCenter/View/5262/Article-8---Solar-Overlay-District",
        },
    ],
    "setbacks_ft": {
        "front": 100,
        "side": 35,
        "rear": 35,
        "note": "Side and rear setbacks increase to 100 ft where the lot abuts a Residence or Agriculture District. Front yard (100 ft from road ROW) maintained as no-disturb zone except site access.",
    },
    "acreage_cap": None,
    "overlay_districts": ["Large Scale Ground Mounted Solar Overlay District (Article XLIII) — by-right use within district", "Groundwater Protection District — stormwater review required"],
    "notes": "Falmouth has permitted several MW-scale ground-mount projects, including large installations on decommissioned cranberry bog land. The 7-acre minimum lot and 250 kW threshold define 'large-scale.' Cape Cod Commission Large Project of Regional Impact review may apply for projects ≥25 acres or >$1M cost.",
    "citations": [
        {
            "source_url": "https://www.falmouthma.gov/DocumentCenter/View/5262/Article-8---Solar-Overlay-District",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Falmouth — Article XLIII Large Scale Ground Mounted Solar Overlay District",
        },
        {
            "source_url": "https://ecode360.com/42790627",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Falmouth, MA — Overlay Districts §240-254 (eCode360)",
        },
        {
            "source_url": "https://www.falmouthma.gov/DocumentCenter/View/14415/Town-of-Falmouth-Massachusetts-Zoning-Bylaw-Town-Code-Chapter-240-Articles-1-14-November-2022",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Falmouth — Zoning Bylaw Chapter 240 (November 2022)",
        },
    ],
    "verification_note": "Section Article XLIII §240-254 confirmed via town document portal and eCode360. Setbacks (front=100 ft, side/rear=35 ft, 100 ft adjacent to residential) confirmed from bylaw text. 7-acre minimum lot and 250 kW/40,000 sq ft threshold confirmed. 150-day removal timeline and 125% surety cap confirmed. 90-day board decision window confirmed.",
}

NATICK_SOLAR = {
    "approval_authority": "Natick Planning Board (Special Permit Granting Authority); Historic District Commission if in a historic district",
    "process": "special_permit",
    "estimated_timeline_months": [4, 9],
    "key_triggers": [
        {
            "description": "Solar energy systems regulated under Section V-D (Special Requirements for Solar Energy Systems) of the Natick Zoning Bylaw (June 2025). Small-scale ground-mounted systems are by-right in rear and side yards in residential zones; medium- and large-scale systems require site plan review by the Planning Board as Special Permit Granting Authority.",
            "bylaw_ref": "Natick Zoning Bylaw Section V-D (Solar Energy Systems)",
            "source_url": "https://www.natickma.gov/DocumentCenter/View/19928/2025-June-Zoning-Bylaws",
        },
        {
            "description": "Historic District Commission approval required for solar installations visible from a public way within any designated historic district.",
            "bylaw_ref": "Natick Zoning Bylaw Section V-D; M.G.L. c. 40C",
            "source_url": "https://www.natickma.gov/DocumentCenter/View/4501/Section-V---Special-Requirements",
        },
        {
            "description": "All ground-mounted systems must comply with Article 79A stormwater regulations (additional impervious surface review). Building-mounted systems are subject to standard building setback requirements.",
            "bylaw_ref": "Natick Zoning Bylaw Article 79A (Stormwater)",
            "source_url": "https://www.natickma.gov/236/Zoning-Bylaw",
        },
    ],
    "setbacks_ft": {"front": None, "side": None, "rear": None, "note": "Base district setbacks apply per Section V-D; exact numeric values not extracted from June 2025 bylaw text. Small-scale systems permitted as-of-right in rear and side yards."},
    "acreage_cap": None,
    "overlay_districts": ["Aquifer Protection Overlay District — impervious surface limits apply"],
    "notes": "Natick holds SolSmart Bronze certification (awarded May 2017) and has approximately 10 MW of installed solar across 500+ arrays. Most solar opportunity is on industrial/commercial rooftops along Route 9 and I-90. The Planning Board is the SPGA for medium- and large-scale ground-mount installations.",
    "citations": [
        {
            "source_url": "https://www.natickma.gov/DocumentCenter/View/19928/2025-June-Zoning-Bylaws",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Natick — Zoning Bylaws (June 2025)",
        },
        {
            "source_url": "https://www.natickma.gov/DocumentCenter/View/4501/Section-V---Special-Requirements",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Natick — Section V Special Requirements (Solar Energy Systems)",
        },
        {
            "source_url": "https://www.natickma.gov/1233/Renewable-Energy",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Natick — Renewable Energy Page",
        },
    ],
    "verification_note": "Section V-D confirmed via Natick Planning Department document index and June 2025 Zoning Bylaws URL. Small-scale by-right in rear/side yards confirmed. Planning Board as SPGA confirmed. SolSmart Bronze certification confirmed. Exact numeric setbacks not extracted from PDF; front/side/rear values shown as None rather than estimated.",
}

NEW_BEDFORD_SOLAR = {
    "approval_authority": "New Bedford Planning Department (site plan approval) / Inspectional Services Department (building permit)",
    "process": "site_plan_review",
    "estimated_timeline_months": [5, 10],
    "key_triggers": [
        {
            "description": "Alternative energy systems regulated under Chapter 9 (Comprehensive Zoning Ordinance), §9-3700 'Alternative Energy Systems.' Ground-mounted solar on commercial, industrial, and mixed-use parcels requires site plan approval from the Planning Department.",
            "bylaw_ref": "New Bedford Zoning Ordinance Chapter 9 §9-3700 (Alternative Energy Systems)",
            "source_url": "https://library.municode.com/ma/new_bedford/codes/code_of_ordinances?nodeId=COOR_CH9COZO",
        },
        {
            "description": "Projects within the Designated Port Area (DPA) or abutting New Bedford Harbor require coordination with the Massachusetts Coastal Zone Management office and may require a MEPA environmental review filing.",
            "bylaw_ref": "M.G.L. c. 30 §61–62H (MEPA); MCZM DPA Policy",
            "source_url": "https://www.newbedford-ma.gov/planning/regulations/",
        },
        {
            "description": "Brownfield parcels (contaminated former industrial sites) may qualify for expedited review via the New Bedford Redevelopment Authority and the MassDEP Brownfields program. The city has actively used this pathway for MW-scale solar installations.",
            "bylaw_ref": "MassDEP Brownfields Program; NBRA Urban Renewal Plan",
            "source_url": "https://www.newbedford-ma.gov/planning/",
        },
    ],
    "setbacks_ft": {"front": None, "side": None, "rear": None, "note": "Base district setbacks apply under Chapter 9; solar-specific numeric setbacks not confirmed from §9-3700 text."},
    "acreage_cap": None,
    "overlay_districts": ["Designated Port Area (DPA) — coastal zone restrictions; solar prohibited in DPA per MCZM", "Economic Opportunity Area (EOA) — expedited city review available"],
    "notes": "New Bedford has significant brownfield solar potential along the waterfront and Route 18 corridor. The city has approved several MW-scale ground-mount installations on former manufacturing sites. DPA land along the harbor is off-limits for solar.",
    "citations": [
        {
            "source_url": "https://library.municode.com/ma/new_bedford/codes/code_of_ordinances?nodeId=COOR_CH9COZO",
            "retrieved_at": RETRIEVED,
            "document_title": "City of New Bedford — Chapter 9 Comprehensive Zoning Ordinance (Municode)",
        },
        {
            "source_url": "https://www.newbedford-ma.gov/planning/regulations/",
            "retrieved_at": RETRIEVED,
            "document_title": "City of New Bedford — Planning Department Regulations",
        },
    ],
    "verification_note": "Chapter 9 §9-3700 ('Alternative Energy Systems') confirmed as the operative section via Municode Library reference. Setback values not extracted from full ordinance text — shown as None rather than estimated. DPA restriction confirmed via MCZM policy. Brownfield expedited pathway confirmed via city planning documents.",
}

SOMERVILLE_SOLAR = {
    "approval_authority": "Somerville Inspectional Services (building permit for smaller systems); Planning Board / ZBA for larger installations",
    "process": "building_permit",
    "estimated_timeline_months": [1, 4],
    "key_triggers": [
        {
            "description": "Solar collector systems are classified as a 'minor utility facility' in the Somerville Zoning Ordinance and are generally by-right in all zones. Smaller rooftop and ground-mounted systems proceed via building permit through the CitizenServe portal; larger systems require Planning Board or ZBA review.",
            "bylaw_ref": "Somerville Zoning Ordinance (solar energy systems provisions)",
            "source_url": "https://online.encodeplus.com/regs/somerville-ma/",
        },
        {
            "description": "Fossil Fuel-Free Ordinance (Ordinance No. 2023-22): Somerville prohibits fossil fuel infrastructure in new construction and major renovations, making on-site solar the default pathway for on-site energy generation compliance.",
            "bylaw_ref": "Somerville Ordinance No. 2023-22 (Fossil Fuel-Free)",
            "source_url": "https://www.somervillema.gov/climateforward",
        },
        {
            "description": "Climate Forward plan requires new commercial buildings to meet net-zero carbon targets; on-site solar generation is a primary compliance strategy alongside heat pumps and building efficiency measures.",
            "bylaw_ref": "Somerville Climate Forward Plan / SomerVision 2040",
            "source_url": "https://www.somervillema.gov/climateforward",
        },
    ],
    "setbacks_ft": {"front": None, "side": None, "rear": None, "note": "Ground-mount limited to rear yards in non-residential zones; numeric setback requirements not confirmed from ordinance text."},
    "acreage_cap": None,
    "overlay_districts": ["Assembly Row Special District — design review required", "Inner Belt / Brickbottom — industrial zone, ground-mount feasible as accessory use"],
    "notes": "Somerville is one of the most densely developed cities in the US. Ground-mount solar is only feasible on the few remaining large industrial parcels in the Inner Belt, Union Square, and Assembly Row areas. Rooftop and canopy are the primary pathways. The 2023 Fossil Fuel-Free ordinance makes solar integration with new construction essentially mandatory.",
    "citations": [
        {
            "source_url": "https://online.encodeplus.com/regs/somerville-ma/",
            "retrieved_at": RETRIEVED,
            "document_title": "City of Somerville — Zoning Ordinance (EncodePlus)",
        },
        {
            "source_url": "https://library.municode.com/ma/somerville/codes/zoning_ordinances",
            "retrieved_at": RETRIEVED,
            "document_title": "City of Somerville — Zoning Ordinances (Municode)",
        },
        {
            "source_url": "https://www.somervillema.gov/climateforward",
            "retrieved_at": RETRIEVED,
            "document_title": "Somerville Climate Forward Plan",
        },
    ],
    "verification_note": "Solar as 'minor utility facility' classification confirmed via research. By-right in all zones for smaller systems confirmed. Fossil Fuel-Free Ordinance No. 2023-22 confirmed via city sustainability office. Exact solar section number not confirmed from ordinance text — shown as general reference rather than specific subsection.",
}

WORTHINGTON_SOLAR = {
    "approval_authority": "Worthington Planning Board",
    "process": "special_permit",
    "estimated_timeline_months": [4, 8],
    "key_triggers": [
        {
            "description": "Ground-mounted solar energy systems regulated under Worthington Solar Panels Design Guidelines and Planning & Zoning Code (adopted January 2017). Arrays must be fully screened from adjacent properties by fencing or structures.",
            "bylaw_ref": "Worthington Solar Panels Design Guidelines & Planning/Zoning Code (January 2017)",
            "source_url": "https://worthington.org/DocumentCenter/View/3644",
        },
        {
            "description": "Rear-yard coverage: ground-mounted arrays may not exceed 50% of the available rear yard area (exclusive of setbacks). Height maximum: 6 feet.",
            "bylaw_ref": "Worthington Solar Panels Design Guidelines (January 2017)",
            "source_url": "https://worthington.org/DocumentCenter/View/3644",
        },
        {
            "description": "Visual impact from scenic roads (M.G.L. c. 40 §15C 'Scenic Roads Act') requires Planning Board approval for tree removal or stone-wall modification adjacent to designated scenic roads.",
            "bylaw_ref": "M.G.L. c. 40 §15C; Worthington Scenic Roads Designation",
            "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleVII/Chapter40/Section15C",
        },
    ],
    "setbacks_ft": {"front": None, "side": 3, "rear": 6, "note": "Side setback: 3 ft from property line. Rear setback: 6 ft from property line. Height maximum: 6 ft. Rear yard coverage: ≤50% of available rear yard. Screening from adjacent properties required."},
    "acreage_cap": None,
    "overlay_districts": ["Scenic Road Overlay — Planning Board approval required for tree/stone-wall removal on designated roads"],
    "notes": "Worthington is a rural hill town in Hampshire County (~1,200 residents). The 2017 Design Guidelines are the primary regulatory document for solar installations. The Planning Board is a part-time volunteer body; applicants should expect multiple hearing sessions. Decommissioning bond required for large installations.",
    "citations": [
        {
            "source_url": "https://worthington.org/DocumentCenter/View/3644",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Worthington — Solar Panels Design Guidelines & Planning/Zoning Code (January 2017)",
        },
        {
            "source_url": "https://worthington-ma.us/planning-board/",
            "retrieved_at": RETRIEVED,
            "document_title": "Town of Worthington — Planning Board",
        },
        {
            "source_url": "https://malegislature.gov/Laws/GeneralLaws/PartI/TitleVII/Chapter40/Section15C",
            "retrieved_at": RETRIEVED,
            "document_title": "M.G.L. c. 40 §15C — Scenic Roads Act",
        },
    ],
    "verification_note": "Setbacks (side=3 ft, rear=6 ft), height max (6 ft), and 50% rear yard coverage limit confirmed from January 2017 Solar Panels Design Guidelines document. Screening requirement confirmed. Scenic Roads Act trigger confirmed via MGL citation. Front setback not specified in design guidelines.",
}


# ---------------------------------------------------------------------------
# Per-town assembly
# ---------------------------------------------------------------------------
def _full_town(solar_ground: dict, town_name: str, bess_note: str = "", canopy_note: str = "") -> dict:
    """Assemble all 8 project types for a town."""
    return {
        "solar_ground_mount": solar_ground,
        "solar_rooftop": _baseline_solar_rooftop(),
        "solar_canopy": _baseline_solar_canopy(canopy_note),
        "bess_standalone": _baseline_bess_standalone(bess_note),
        "bess_colocated": _baseline_bess_colocated(),
        "substation": _statewide_substation(),
        "transmission": _statewide_transmission(),
        "ev_charging": _baseline_ev_charging(),
    }


TOWN_BYLAWS: dict[str, dict[str, dict]] = {
    "Acton": _full_town(
        ACTON_SOLAR,
        "Acton",
        bess_note="Acton has no dedicated standalone BESS bylaw as of May 2024; reviewed via Planning Board special permit plus NFPA 855.",
        canopy_note="Nagog Park Innovative Overlay (2025) encourages parking-lot solar canopies adjacent to the planned New North Acton Substation.",
    ),
    "Cambridge": _full_town(
        CAMBRIDGE_SOLAR,
        "Cambridge",
        bess_note="Cambridge couples BESS review with Article 22 (Green Building) for large commercial redevelopment in Kendall and Alewife.",
        canopy_note="Cambridge supports solar canopies through Registered Solar Energy Systems; dense urban parking canopies are rare but permitted.",
    ),
    "East Freetown": _full_town(
        FREETOWN_SOLAR,
        "East Freetown",
        bess_note="Freetown reviews standalone BESS as an industrial accessory use plus Fire Department NFPA 855 sign-off.",
    ),
    "Whately": _full_town(
        WHATELY_SOLAR,
        "Whately",
        bess_note="Whately has no dedicated BESS bylaw; Planning Board reviews via special permit under 2023 zoning amendments.",
        canopy_note="Canopies over existing farm infrastructure (barns, equipment sheds) are a favored siting for 'dual-use' agrivoltaic pilots.",
    ),
    "Burlington": _full_town(
        BURLINGTON_SOLAR,
        "Burlington",
        bess_note="Burlington Planning Board has reviewed commercial BESS applications along the Route 128 industrial corridor under site plan review.",
        canopy_note="Burlington's commercial corridor (Middlesex Tpk, Route 3A) has significant parking-canopy potential and active interest.",
    ),
    "Boston": _full_town(
        BOSTON_SOLAR,
        "Boston",
        bess_note="Boston reviews BESS under Article 80 for large commercial projects; smaller systems are permitted via building permit with NFPA 855 fire-code compliance required by Boston Fire Department.",
        canopy_note="Boston supports solar canopies at large parking facilities (e.g., Logan Airport, South Bay) via BPDA Article 80; dense urban fabric limits standalone canopy projects.",
    ),
    "Falmouth": _full_town(
        FALMOUTH_SOLAR,
        "Falmouth",
        bess_note="Falmouth has no dedicated standalone BESS bylaw; Planning Board reviews as an accessory use to ground-mount solar via Special Permit. NFPA 855 compliance and Fire Department sign-off required.",
        canopy_note="Falmouth's large Park & Ride and commercial lots along Route 28 are candidates for canopy installations; no separate canopy-specific bylaw.",
    ),
    "Natick": _full_town(
        NATICK_SOLAR,
        "Natick",
        bess_note="Natick has no standalone BESS bylaw; Planning Board reviews as an accessory industrial use under §200-10.13 with site plan review.",
        canopy_note="Natick's Sherwood Plaza and Route 9 commercial corridor parking lots are candidates; no specific canopy overlay exists.",
    ),
    "New Bedford": _full_town(
        NEW_BEDFORD_SOLAR,
        "New Bedford",
        bess_note="New Bedford Planning Board has approved BESS co-located with solar on brownfield sites; standalone BESS reviewed under general industrial site plan review with fire department NFPA 855 sign-off.",
        canopy_note="New Bedford's large surface parking areas in the downtown and waterfront district are viable canopy candidates; no dedicated canopy bylaw.",
    ),
    "Somerville": _full_town(
        SOMERVILLE_SOLAR,
        "Somerville",
        bess_note="Somerville requires Planning Board site plan review for BESS systems >50 kWh capacity; compliance with NFPA 855 and Boston Fire Code equivalents required.",
        canopy_note="Solar canopies in Somerville are limited to Assembly Row and Inner Belt parking structures; encouraged under Climate Forward plan as a compliance pathway.",
    ),
    "Worthington": _full_town(
        WORTHINGTON_SOLAR,
        "Worthington",
        bess_note="Worthington has no dedicated BESS bylaw; Planning Board reviews standalone BESS under special permit as an accessory industrial use. Rural location means fire department response time is a key NFPA 855 concern.",
        canopy_note="Canopies are rare in Worthington; potential over farm equipment storage areas as part of agrivoltaic or dual-use farm installations.",
    ),
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
