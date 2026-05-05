"""Parcel use-code classification for MA assessor property codes.

Reads the ``use_code`` field on MassGIS L3 parcels and returns a
ParcelClassification describing what the parcel actually is — hospital,
municipal park, state-owned land, private warehouse, etc.

MA assessors use a standardized code system (4-digit codes are just
3-digit codes with a trailing zero; both forms appear in the dataset).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Development complexity flag — controls how prominently the UI warns the user.
DevelopmentFlag = Literal[
    "private",        # Standard private land — no ownership red flags
    "institutional",  # Private but hospital / university / church / nonprofit
    "government",     # Municipal, county, state, or federal ownership
    "protected",      # Parks, conservation land — legally restricted
    "infrastructure", # Airport, utility corridor, ROW
]


class ParcelClassification(BaseModel):
    use_code: str
    use_label: str
    use_category: str
    ownership_type: str
    development_flag: DevelopmentFlag
    note: str


# ---------------------------------------------------------------------------
# MA Assessor Use Code → Classification
#
# Both 3-digit (101) and 4-digit (1010) forms appear in the MassGIS dataset.
# The map normalises to 3-digit by stripping a trailing '0' when lookup fails.
# ---------------------------------------------------------------------------
_USE_CODE_MAP: dict[str, ParcelClassification] = {
    # ── Residential ──────────────────────────────────────────────────────────
    "101": ParcelClassification(use_code="101", use_label="Single-Family Residential", use_category="Residential", ownership_type="Private", development_flag="private", note="Standard private residential parcel."),
    "102": ParcelClassification(use_code="102", use_label="Condominium Unit", use_category="Residential", ownership_type="Private", development_flag="private", note="Condo unit — parcel may be too small; confirm lot size."),
    "104": ParcelClassification(use_code="104", use_label="Two-Family Residential", use_category="Residential", ownership_type="Private", development_flag="private", note=""),
    "105": ParcelClassification(use_code="105", use_label="Three-Family Residential", use_category="Residential", ownership_type="Private", development_flag="private", note=""),
    "106": ParcelClassification(use_code="106", use_label="Accessory Land / Mixed Residential", use_category="Residential", ownership_type="Private", development_flag="private", note=""),
    "109": ParcelClassification(use_code="109", use_label="Multiple-Family Residential (4+)", use_category="Residential", ownership_type="Private", development_flag="private", note=""),
    "111": ParcelClassification(use_code="111", use_label="Four-Family Residential", use_category="Residential", ownership_type="Private", development_flag="private", note=""),
    "112": ParcelClassification(use_code="112", use_label="Five or More Family Residential", use_category="Residential", ownership_type="Private", development_flag="private", note=""),

    # ── Agricultural / Undeveloped ────────────────────────────────────────────
    "013": ParcelClassification(use_code="013", use_label="Agricultural Land", use_category="Agricultural", ownership_type="Private", development_flag="private", note="Prime farmland scoring applies — check agricultural criterion."),
    "017": ParcelClassification(use_code="017", use_label="Agricultural Residential", use_category="Agricultural", ownership_type="Private", development_flag="private", note=""),
    "018": ParcelClassification(use_code="018", use_label="Horticultural", use_category="Agricultural", ownership_type="Private", development_flag="private", note=""),
    "031": ParcelClassification(use_code="031", use_label="Potentially Developable Land", use_category="Undeveloped", ownership_type="Private", development_flag="private", note="Vacant land — confirm zoning before proceeding."),

    # ── Commercial ───────────────────────────────────────────────────────────
    "130": ParcelClassification(use_code="130", use_label="Commercial / Office", use_category="Commercial", ownership_type="Private", development_flag="private", note=""),
    "131": ParcelClassification(use_code="131", use_label="Retail / Store", use_category="Commercial", ownership_type="Private", development_flag="private", note=""),
    "132": ParcelClassification(use_code="132", use_label="Mixed Commercial", use_category="Commercial", ownership_type="Private", development_flag="private", note=""),
    "316": ParcelClassification(use_code="316", use_label="Hospital / Medical Center", use_category="Institutional", ownership_type="Institutional (Private)", development_flag="institutional", note="Hospital or medical campus. Development rights require negotiation with the owning health system. Ground lease or roof-mount arrangements are possible but complex."),
    "325": ParcelClassification(use_code="325", use_label="Parking Facility", use_category="Commercial", ownership_type="Private", development_flag="private", note="Parking lots and garages are good candidates for solar canopy. Confirm ownership — may be privately or municipally owned."),
    "340": ParcelClassification(use_code="340", use_label="Hotel / Motel", use_category="Commercial", ownership_type="Private", development_flag="private", note=""),
    "359": ParcelClassification(use_code="359", use_label="Stadium / Arena / Sports Facility", use_category="Recreational / Commercial", ownership_type="Mixed", development_flag="institutional", note="Stadiums are often publicly subsidised or municipally owned. Verify ownership before assuming private development rights."),

    # ── Industrial ───────────────────────────────────────────────────────────
    "400": ParcelClassification(use_code="400", use_label="Industrial / Manufacturing", use_category="Industrial", ownership_type="Private", development_flag="private", note="Industrial parcels are strong BESS candidates — large footprints, existing grid infrastructure, and brownfield bonus likely applies."),
    "401": ParcelClassification(use_code="401", use_label="Utility / Telephone Infrastructure", use_category="Infrastructure", ownership_type="Private / Utility", development_flag="infrastructure", note="May be owned by a regulated utility. Development rights depend on whether the parcel is a utility easement or fee-simple ownership."),

    # ── Government — Municipal ────────────────────────────────────────────────
    "903": ParcelClassification(use_code="903", use_label="Municipal / Town-Owned Land", use_category="Government", ownership_type="Municipal", development_flag="government", note="Owned by the host municipality. Development requires town approval — typically a town meeting vote or select board authorization. Municipal solar and BESS leases do happen but add 12–24 months to timeline."),
    "904": ParcelClassification(use_code="904", use_label="County-Owned Land", use_category="Government", ownership_type="County", development_flag="government", note="County ownership. Development requires county approval."),

    # ── Government — State ────────────────────────────────────────────────────
    "905": ParcelClassification(use_code="905", use_label="State-Owned Land (DCR / MassHighway / Other)", use_category="Government", ownership_type="State", development_flag="government", note="Commonwealth of Massachusetts owns this parcel. Generally managed by DCR, MassDOT, or another state agency. State-land solar/BESS leases require DCAMM approval — significant added process and timeline."),
    "906": ParcelClassification(use_code="906", use_label="State-Owned Land (Other Agency)", use_category="Government", ownership_type="State", development_flag="government", note="Same as 905 — state-owned, requires DCAMM or agency approval for any ground lease."),

    # ── Government — Federal ──────────────────────────────────────────────────
    "907": ParcelClassification(use_code="907", use_label="Federal Government Land", use_category="Government", ownership_type="Federal", development_flag="government", note="Federal ownership (National Park, military, GSA, postal, etc.). Development is extremely restricted — federal procurement rules and NEPA review required."),

    # ── Institutional / Nonprofit ─────────────────────────────────────────────
    "910": ParcelClassification(use_code="910", use_label="Church / Religious Institution", use_category="Institutional", ownership_type="Nonprofit (Religious)", development_flag="institutional", note="Religious institution. Tax-exempt nonprofit ownership — development rights require negotiation with the religious body. Ground lease solar projects on church land are common."),
    "911": ParcelClassification(use_code="911", use_label="Educational Institution (University / School)", use_category="Institutional", ownership_type="Nonprofit / Public", development_flag="institutional", note="University, college, or K-12 school campus. Ownership may be private nonprofit, public, or charter. Campus solar and BESS are active markets but require institution sign-off."),

    # ── Parks / Recreation / Conservation ─────────────────────────────────────
    "742": ParcelClassification(use_code="742", use_label="Municipal Park / Playground", use_category="Recreation", ownership_type="Municipal", development_flag="protected", note="Public park or playground. Town-owned open space — generally protected under Article 97 of the MA Constitution. Siting clean energy here is likely legally restricted and politically very difficult."),
    "743": ParcelClassification(use_code="743", use_label="Recreation Area (Private or Club)", use_category="Recreation", ownership_type="Private / Club", development_flag="institutional", note="Private recreation land (golf course, sports club, etc.). Development rights depend on ownership — golf courses have been successfully converted to solar in MA."),
    "744": ParcelClassification(use_code="744", use_label="Conservation / Agricultural Reserve", use_category="Conservation", ownership_type="Mixed", development_flag="protected", note="Conservation or agricultural restriction likely in place. Verify deed restrictions — may prohibit energy development entirely."),

    # ── Infrastructure / Exempt ───────────────────────────────────────────────
    "930": ParcelClassification(use_code="930", use_label="Tax-Exempt Land (various)", use_category="Exempt", ownership_type="Mixed", development_flag="institutional", note="Tax-exempt parcel — ownership may be nonprofit, religious, educational, or government. Verify owner before assessing development rights."),
    "932": ParcelClassification(use_code="932", use_label="Tax-Exempt — Charitable / Nonprofit", use_category="Exempt", ownership_type="Nonprofit", development_flag="institutional", note="Charitable or nonprofit-owned exempt land."),
    "950": ParcelClassification(use_code="950", use_label="Utility / Public Service Land", use_category="Infrastructure", ownership_type="Utility", development_flag="infrastructure", note="Utility-owned land. May be substation, transmission ROW, or service yard. ESMP and HCA data likely most relevant here."),
    "965": ParcelClassification(use_code="965", use_label="Airport / Airfield", use_category="Infrastructure", ownership_type="Mixed (Public / Private)", development_flag="infrastructure", note="Airport land. FAA height and safety restrictions apply — solar near runways has specific siting constraints under FAA Advisory Circular 150/5190-8."),
    "995": ParcelClassification(use_code="995", use_label="Right-of-Way / Road", use_category="Infrastructure", ownership_type="Public", development_flag="infrastructure", note="Road ROW or transportation corridor. Not a developable parcel."),
}

# Normalise a raw use_code to the 3-digit canonical form.
def _normalise(code: str) -> str:
    code = code.strip().lstrip("0") or "0"
    # 4-digit codes (e.g. "1010") are 3-digit + trailing zero
    if len(code) == 4 and code.endswith("0"):
        return code[:-1]
    return code


def classify(use_code: str | None) -> ParcelClassification:
    """Return a ParcelClassification for a MassGIS L3 assessor use_code.

    Falls back to a generic 'Private' classification when the code is
    unknown — unknown does not mean problematic.
    """
    if not use_code:
        return ParcelClassification(
            use_code="",
            use_label="Use Code Not Available",
            use_category="Unknown",
            ownership_type="Unknown",
            development_flag="private",
            note="Parcel use code is missing from the assessor data. Verify ownership independently.",
        )

    key = _normalise(use_code)
    if key in _USE_CODE_MAP:
        return _USE_CODE_MAP[key]

    # Broad-category fallback from the leading digit(s)
    prefix = key[:2] if len(key) >= 2 else key
    if prefix in ("10", "11", "12"):
        return ParcelClassification(use_code=use_code, use_label=f"Residential (code {use_code})", use_category="Residential", ownership_type="Private", development_flag="private", note="")
    if prefix in ("13", "14", "15", "16", "17", "18", "19", "32", "33", "34", "35"):
        return ParcelClassification(use_code=use_code, use_label=f"Commercial (code {use_code})", use_category="Commercial", ownership_type="Private", development_flag="private", note="")
    if prefix in ("40", "41", "42", "43", "44", "45"):
        return ParcelClassification(use_code=use_code, use_label=f"Industrial (code {use_code})", use_category="Industrial", ownership_type="Private", development_flag="private", note="")
    if prefix in ("90", "91", "92", "93", "94", "95", "96", "97", "98", "99"):
        return ParcelClassification(use_code=use_code, use_label=f"Exempt / Government (code {use_code})", use_category="Government / Exempt", ownership_type="Unknown", development_flag="government", note="Code in the 900-series suggests government or exempt ownership. Verify before proceeding.")

    return ParcelClassification(
        use_code=use_code,
        use_label=f"Unknown Use (code {use_code})",
        use_category="Unknown",
        ownership_type="Unknown",
        development_flag="private",
        note="Use code not recognised — verify ownership independently.",
    )
