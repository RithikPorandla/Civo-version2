"""NL query interpreter — Claude tool-calling for intent classification.

Every user query passes through here before hitting PostGIS. Claude extracts
structured filters; the raw query is never passed to SQL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# MA sub-region → municipality lists
# ---------------------------------------------------------------------------
SUB_REGIONS: dict[str, list[str]] = {
    "ema-north-metro-west": [
        "Acton", "Bedford", "Burlington", "Concord", "Lexington", "Lincoln",
        "Littleton", "Maynard", "Stow", "Sudbury", "Wayland", "Westford",
    ],
    "ema-south-metro-west": [
        "Ashland", "Framingham", "Holliston", "Hopkinton", "Marlborough",
        "Milford", "Millis", "Natick", "Northborough", "Sherborn",
        "Southborough", "Upton", "Westborough",
    ],
    "ema-north-shore": [
        "Beverly", "Danvers", "Essex", "Gloucester", "Hamilton", "Ipswich",
        "Manchester", "Marblehead", "Middleton", "Nahant", "Peabody",
        "Rockport", "Salem", "Swampscott", "Topsfield", "Wenham",
    ],
    "ema-south-shore": [
        "Abington", "Braintree", "Cohasset", "Duxbury", "Hanover", "Hanson",
        "Hingham", "Hull", "Kingston", "Marshfield", "Norwell", "Pembroke",
        "Plymouth", "Rockland", "Scituate", "Weymouth", "Whitman",
    ],
    "ema-pioneer-valley": [
        "Agawam", "Amherst", "Chicopee", "Easthampton", "Granby", "Hadley",
        "Hampden", "Holyoke", "Longmeadow", "Ludlow", "Northampton",
        "Palmer", "South Hadley", "Southampton", "Southwick", "Springfield",
        "West Springfield", "Westfield",
    ],
    "ema-cape-cod": [
        "Barnstable", "Bourne", "Brewster", "Chatham", "Dennis", "Eastham",
        "Falmouth", "Harwich", "Mashpee", "Orleans", "Provincetown",
        "Sandwich", "Truro", "Wellfleet", "Yarmouth",
    ],
    "ema-merrimack-valley": [
        "Amesbury", "Andover", "Haverhill", "Lawrence", "Lowell", "Methuen",
        "Newburyport", "North Andover",
    ],
    "ema-south": [
        "Abington", "Braintree", "Cohasset", "Duxbury", "Hanover", "Hanson",
        "Hingham", "Hull", "Kingston", "Marshfield", "Norwell", "Pembroke",
        "Plymouth", "Rockland", "Scituate", "Weymouth", "Whitman",
        "Attleboro", "Brockton", "Canton", "Easton", "Foxborough", "Franklin",
        "Mansfield", "Milford", "Norwood", "Plainville", "Randolph",
        "Stoughton", "Walpole", "Wrentham",
    ],
    "ema-north": [
        "Beverly", "Danvers", "Essex", "Gloucester", "Hamilton", "Ipswich",
        "Manchester", "Marblehead", "Middleton", "Nahant", "Peabody",
        "Rockport", "Salem", "Swampscott", "Topsfield", "Wenham",
        "Acton", "Bedford", "Burlington", "Concord", "Lexington", "Lincoln",
        "Littleton", "Maynard", "Stow", "Sudbury", "Wayland", "Westford",
        "Amesbury", "Andover", "Haverhill", "Lawrence", "Lowell", "Methuen",
        "Newburyport", "North Andover",
    ],
    "wma": [
        "Adams", "Agawam", "Amherst", "Blandford", "Brimfield", "Chicopee",
        "East Longmeadow", "Easthampton", "Granby", "Hadley", "Hampden",
        "Holyoke", "Longmeadow", "Ludlow", "Northampton", "Palmer",
        "South Hadley", "Southampton", "Southwick", "Springfield",
        "West Springfield", "Westfield",
    ],
}

INTENT_TYPES = [
    "site_discovery",
    "town_comparison",
    "precedent_search",
    "regulatory_lookup",
    "doer_status",
    "score_address",
]

CONSTRAINT_LAYERS = [
    "biomap_core", "biomap_cnl", "nhesp_priority", "nhesp_estimated",
    "flood_zone", "wetlands", "article97", "prime_farmland",
]

INTERPRET_TOOL = {
    "name": "interpret_site_query",
    "description": (
        "Parse a natural language site discovery query into structured filters "
        "for PostGIS spatial search of Massachusetts parcels."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "intent_type": {
                "type": "string",
                "enum": INTENT_TYPES,
                "description": "Primary intent of the query",
            },
            "municipalities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "MA municipality names (town names) to filter to. Use exact MA town names.",
            },
            "sub_region": {
                "type": "string",
                "enum": list(SUB_REGIONS.keys()),
                "description": "Named planning sub-region. Use instead of listing every individual town.",
            },
            "min_acres": {
                "type": "number",
                "description": "Minimum parcel size in acres",
            },
            "max_acres": {
                "type": "number",
                "description": "Maximum parcel size in acres",
            },
            "project_type": {
                "type": "string",
                "enum": [
                    "solar_ground_mount", "solar_rooftop", "solar_canopy",
                    "bess_standalone", "bess_colocated", "substation",
                ],
                "description": "Clean energy project type",
            },
            "project_size_mw": {
                "type": "number",
                "description": "Target project nameplate capacity in MW",
            },
            "exclude_layers": {
                "type": "array",
                "items": {"type": "string", "enum": CONSTRAINT_LAYERS},
                "description": "Constraint layers the parcel must NOT intersect",
            },
            "include_layers": {
                "type": "array",
                "items": {"type": "string", "enum": CONSTRAINT_LAYERS},
                "description": "Constraint layers the parcel MUST intersect",
            },
            "min_score": {
                "type": "number",
                "description": "Minimum suitability score (0-100)",
            },
            "anchor_esmp_name": {
                "type": "string",
                "description": "Name or partial name of an ESMP substation project to anchor search",
            },
            "max_distance_to_esmp_miles": {
                "type": "number",
                "description": "Max distance in miles to nearest ESMP project",
            },
            "doer_bess_status": {
                "type": "string",
                "enum": ["adopted", "in_progress", "not_started", "unknown"],
                "description": "Filter municipalities by DOER BESS bylaw adoption status",
            },
            "doer_solar_status": {
                "type": "string",
                "enum": ["adopted", "in_progress", "not_started", "unknown"],
                "description": "Filter municipalities by DOER solar bylaw adoption status",
            },
            "sort_by": {
                "type": "string",
                "enum": ["score_desc", "area_desc", "distance_asc", "approval_rate_desc", "composite_friendliness"],
                "description": "Result sort order",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence in interpretation (0-1)",
            },
        },
        "required": ["intent_type"],
    },
}

SYSTEM_PROMPT = """You are Civo's query interpreter for Massachusetts permitting professionals.
Parse natural language site discovery queries into structured filters.

MA geography:
- "EMA-North Metro West" = towns: Acton, Bedford, Burlington, Concord, Lexington, Lincoln, Littleton, Maynard, Stow, Sudbury, Wayland, Westford
- "EMA-South Metro West" = towns around Framingham, Natick, Marlborough, Milford
- "Cape Cod" = Barnstable, Bourne, Brewster, Chatham, Dennis, Eastham, Falmouth, etc.
- "Pioneer Valley" / "WMA" = Springfield, Holyoke, Northampton, Amherst area
- "Merrimack Valley" = Lowell, Lawrence, Haverhill, Andover, Newburyport

Project type mapping:
- "BESS" or "battery storage" → bess_standalone
- "co-located" battery → bess_colocated
- "solar" or "ground-mount solar" → solar_ground_mount
- "solar canopy" → solar_canopy
- "substation" → substation

Constraint layers:
- "BioMap" or "BioMap Core" → biomap_core
- "NHESP Priority" or "rare species habitat" → nhesp_priority
- "flood zone" or "FEMA" → flood_zone
- "wetlands" → wetlands
- "Article 97" or "protected open space" → article97
- "prime farmland" or "farmland" → prime_farmland

Size hints for project types (use as default min if only MW is given):
- 5MW BESS → min_acres ~2, max_acres ~15
- 5MW solar → min_acres ~5, max_acres ~40

Always call the interpret_site_query tool. Never respond with plain text."""


@dataclass
class InterpretedQuery:
    intent_type: str = "site_discovery"
    municipalities: list[str] = field(default_factory=list)
    sub_region: str | None = None
    min_acres: float | None = None
    max_acres: float | None = None
    project_type: str | None = None
    project_size_mw: float | None = None
    exclude_layers: list[str] = field(default_factory=list)
    include_layers: list[str] = field(default_factory=list)
    min_score: float | None = None
    anchor_esmp_name: str | None = None
    max_distance_to_esmp_miles: float | None = None
    doer_bess_status: str | None = None
    doer_solar_status: str | None = None
    sort_by: str = "score_desc"
    raw_query: str = ""
    confidence: float = 1.0

    def resolved_municipalities(self) -> list[str]:
        """Return flat municipality list, expanding sub_region if needed."""
        if self.municipalities:
            return self.municipalities
        if self.sub_region:
            return SUB_REGIONS.get(self.sub_region, [])
        return []


def interpret_query(query: str) -> InterpretedQuery:
    """Classify NL query and extract structured filters via Claude tool-calling.

    Falls back to a broad empty filter if ANTHROPIC_API_KEY is unset or the
    call fails — so the discovery endpoint still returns results (just unfiltered).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return InterpretedQuery(raw_query=query, confidence=0.0)

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[INTERPRET_TOOL],
            tool_choice={"type": "tool", "name": "interpret_site_query"},
            messages=[{"role": "user", "content": query}],
        )
        tool_use = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if not tool_use:
            return InterpretedQuery(raw_query=query, confidence=0.0)

        inp = tool_use.input
        return InterpretedQuery(
            intent_type=inp.get("intent_type", "site_discovery"),
            municipalities=inp.get("municipalities") or [],
            sub_region=inp.get("sub_region"),
            min_acres=inp.get("min_acres"),
            max_acres=inp.get("max_acres"),
            project_type=inp.get("project_type"),
            project_size_mw=inp.get("project_size_mw"),
            exclude_layers=inp.get("exclude_layers") or [],
            include_layers=inp.get("include_layers") or [],
            min_score=inp.get("min_score"),
            anchor_esmp_name=inp.get("anchor_esmp_name"),
            max_distance_to_esmp_miles=inp.get("max_distance_to_esmp_miles"),
            doer_bess_status=inp.get("doer_bess_status"),
            doer_solar_status=inp.get("doer_solar_status"),
            sort_by=inp.get("sort_by", "score_desc"),
            raw_query=query,
            confidence=inp.get("confidence", 0.9),
        )
    except Exception:
        return InterpretedQuery(raw_query=query, confidence=0.0)
