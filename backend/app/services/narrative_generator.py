"""Claude narrative synthesis for discovery results.

Takes a structured list of parcels + the interpreted query and generates
a 2-4 sentence analyst briefing. Every claim traces to the result data;
Claude never introduces facts beyond what's in the results dict.
"""

from __future__ import annotations

import os
from typing import Any

from app.services.query_interpreter import InterpretedQuery

SYNTHESIS_SYSTEM = """You are Civo's analysis engine. You write briefings for Massachusetts permitting professionals.

Rules (non-negotiable):
- Write exactly 2-4 sentences.
- Every factual claim must be directly supported by the structured data given to you.
- Do not speculate, predict permitting outcomes, or add information beyond the data.
- Mention the most notable finding first.
- If results are empty, explain which filters were most restrictive.
- Voice: senior analyst briefing a colleague — direct, specific, zero filler.
- Do NOT start sentences with "I" or "Civo".
"""


def generate_narrative(
    query: InterpretedQuery,
    results: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Return (narrative_text, citations). Returns (None, []) on failure/no key."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None, []

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        total = len(results)
        suitable = sum(1 for r in results if r.get("bucket") == "SUITABLE")
        conditional = sum(1 for r in results if r.get("bucket") == "CONDITIONALLY SUITABLE")
        constrained = sum(1 for r in results if r.get("bucket") == "CONSTRAINED")
        unscored = total - suitable - conditional - constrained

        top5 = results[:5]
        top_addresses = [
            f"{r.get('site_addr') or 'unnamed parcel'} ({r.get('town_name', '')})"
            for r in top5
        ]

        filters_summary = []
        if query.municipalities:
            filters_summary.append(f"municipalities: {', '.join(query.municipalities[:5])}")
        if query.sub_region:
            filters_summary.append(f"sub-region: {query.sub_region}")
        if query.min_acres:
            filters_summary.append(f"min size: {query.min_acres} acres")
        if query.max_acres:
            filters_summary.append(f"max size: {query.max_acres} acres")
        if query.exclude_layers:
            filters_summary.append(f"excluded: {', '.join(query.exclude_layers)}")
        if query.project_type:
            filters_summary.append(f"project type: {query.project_type}")

        data_summary = f"""Query: "{query.raw_query}"
Applied filters: {'; '.join(filters_summary) if filters_summary else 'none (broad search)'}
Total results: {total}
Bucket breakdown: {suitable} SUITABLE, {conditional} CONDITIONALLY SUITABLE, {constrained} CONSTRAINED, {unscored} unscored
Top results: {', '.join(top_addresses) if top_addresses else 'none'}
Data sources: MassGIS L3 Parcels, BioMap Core, NHESP Priority Habitat, FEMA NFHL, MassDEP Wetlands, Article 97, Eversource ESMP DPU 24-10"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system=SYNTHESIS_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Write a briefing based on these discovery results:\n\n{data_summary}",
                }
            ],
        )

        narrative = response.content[0].text.strip() if response.content else None

        citations: list[dict[str, Any]] = [
            {"claim": f"{total} parcels returned", "source": "MassGIS L3 Parcels"},
        ]
        if query.exclude_layers:
            for layer in query.exclude_layers:
                layer_source = {
                    "biomap_core": "MassGIS BioMap Core Habitat",
                    "nhesp_priority": "NHESP Priority Habitat of Rare Species",
                    "flood_zone": "FEMA NFHL Flood Hazard Areas",
                    "wetlands": "MassDEP Wetlands (310 CMR 10.04)",
                    "article97": "Article 97 Protected Open Space",
                    "prime_farmland": "USDA NRCS Prime Farmland",
                }.get(layer, layer)
                citations.append(
                    {"claim": f"{layer} exclusion filter", "source": layer_source}
                )
        if total > 0:
            citations.append(
                {"claim": "Suitability scores", "source": "Civo scoring engine v ma-eea-2026-v1"}
            )

        return narrative, citations

    except Exception:
        return None, []
