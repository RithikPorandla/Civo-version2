"""Sentiment analysis of public records for clean energy permitting.

Sources (in priority order):
  1. precedents.full_text   — ConCom/planning board hearing transcripts already in DB
  2. Town website scraping  — ConCom meeting minutes from municipalities.town_url
  3. MA DPU docket search   — public comment pages for BESS/solar dockets

Claude API extracts per-document sentiment (-1 to 1) toward each project type,
plus key concerns and support arguments. Aggregated per (town, project_type)
and stored in town_sentiment.

Usage:
    python -m scripts.sentiment_analysis [--town Acton] [--source precedents|web|all]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

sys.path.insert(0, ".")
from app.db import SessionLocal

try:
    import anthropic
    _client = anthropic.Anthropic()
except Exception:
    _client = None  # type: ignore

# ----- Prompt ------------------------------------------------------------------

_SENTIMENT_PROMPT = """\
You are a permitting intelligence analyst for Massachusetts clean energy projects.

Analyze the following public record excerpt from a Massachusetts town's ConCom (Conservation Commission) \
or Planning Board meeting, or a DPU docket comment. Extract community sentiment toward \
BESS (battery energy storage) and solar projects.

Document:
{text}

Return ONLY valid JSON with this exact structure:
{{
  "bess_sentiment": <float -1.0 to 1.0>,
  "solar_sentiment": <float -1.0 to 1.0>,
  "key_concerns": ["<concern 1>", "<concern 2>"],
  "key_support": ["<support argument 1>"],
  "summary": "<one sentence>"
}}

Scoring guide:
  1.0  = strong community support, commissioners favorable, no opposition voiced
  0.5  = mild support or neutral
  0.0  = mixed, split board, significant conditions required
 -0.5  = notable opposition, contested conditions, board skepticism
 -1.0  = denial, active opposition, moratorium discussion

If the document doesn't mention BESS or solar, return 0.0 for that type.
"""


def _call_claude(doc_text: str) -> dict | None:
    if not _client:
        return None
    try:
        msg = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": _SENTIMENT_PROMPT.format(text=doc_text[:6000])}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"    Claude error: {e}")
        return None


# ----- Source 1: precedents.full_text -----------------------------------------

def _analyze_precedents(town_name: str | None) -> dict[str, list[dict]]:
    """Return {town_name: [result_dict]} from precedents.full_text."""
    with SessionLocal() as session:
        q = """
            SELECT p.project_type, p.decision, p.full_text, m.town_name
            FROM precedents p
            JOIN municipalities m ON m.town_id = p.town_id
            WHERE p.full_text IS NOT NULL AND LENGTH(p.full_text) > 100
        """
        params: dict = {}
        if town_name:
            q += " AND m.town_name = :town"
            params["town"] = town_name
        rows = session.execute(text(q), params).mappings().all()

    by_town: dict[str, list[dict]] = {}
    for row in rows:
        town = row["town_name"]
        result = _call_claude(row["full_text"])
        if result:
            result["source"] = "precedent"
            result["project_type"] = row["project_type"]
            result["decision"] = row["decision"]
            by_town.setdefault(town, []).append(result)
        time.sleep(0.3)  # rate limiting

    return by_town


# ----- Source 2: Town website scraping ----------------------------------------

_SEARCH_QUERIES = [
    "{town} ConCom minutes battery storage site",
    "{town} planning board solar hearing minutes",
    "{town} conservation commission BESS decision",
]

_DPU_SEARCH = "site:mass.gov/dpu battery storage solar {town} comments"


def _scrape_town_minutes(town_name: str, town_url: str | None) -> list[str]:
    """Try to fetch relevant text from town ConCom minutes pages."""
    texts: list[str] = []
    if not town_url:
        return texts

    # Check if town site has an agenda/minutes section
    candidate_paths = [
        "/AgendaCenter",
        "/175/Conservation-Commission",
        "/minutes",
        "/conservation",
    ]
    base = town_url.rstrip("/")

    for path in candidate_paths:
        try:
            resp = httpx.get(f"{base}{path}", timeout=8, follow_redirects=True)
            if resp.status_code == 200 and len(resp.text) > 500:
                # Look for mentions of solar/BESS/battery
                lower = resp.text.lower()
                if any(kw in lower for kw in ["solar", "battery", "bess", "energy storage"]):
                    texts.append(resp.text[:4000])
                    break
        except Exception:
            continue

    return texts


# ----- Aggregation + upsert ---------------------------------------------------

def _aggregate(results: list[dict]) -> dict:
    if not results:
        return {
            "sentiment_score": 0.0,
            "support_score": 0.0,
            "opposition_score": 0.0,
            "document_count": 0,
            "key_concerns": [],
            "key_support": [],
            "sources": [],
        }

    bess_scores = [r.get("bess_sentiment", 0.0) for r in results if "bess_sentiment" in r]
    solar_scores = [r.get("solar_sentiment", 0.0) for r in results if "solar_sentiment" in r]
    all_scores = bess_scores + solar_scores

    avg = sum(all_scores) / len(all_scores) if all_scores else 0.0
    support = sum(s for s in all_scores if s > 0) / max(len([s for s in all_scores if s > 0]), 1)
    opposition = abs(sum(s for s in all_scores if s < 0) / max(len([s for s in all_scores if s < 0]), 1))

    concerns = []
    support_args = []
    for r in results:
        concerns.extend(r.get("key_concerns", []))
        support_args.extend(r.get("key_support", []))

    return {
        "sentiment_score": round(avg, 3),
        "support_score": round(support, 3),
        "opposition_score": round(opposition, 3),
        "document_count": len(results),
        "key_concerns": list(dict.fromkeys(concerns))[:10],
        "key_support": list(dict.fromkeys(support_args))[:10],
        "sources": [r.get("source", "unknown") for r in results],
    }


_UPSERT = text("""
    INSERT INTO town_sentiment
        (town_name, project_type, sentiment_score, support_score, opposition_score,
         document_count, key_concerns, key_support, sources, computed_at)
    VALUES
        (:town, :pt, :sentiment, :support, :opposition,
         :doc_count,
         CAST(:concerns AS jsonb),
         CAST(:support_args AS jsonb),
         CAST(:sources AS jsonb),
         :now)
    ON CONFLICT (town_name, project_type) DO UPDATE SET
        sentiment_score  = EXCLUDED.sentiment_score,
        support_score    = EXCLUDED.support_score,
        opposition_score = EXCLUDED.opposition_score,
        document_count   = EXCLUDED.document_count,
        key_concerns     = EXCLUDED.key_concerns,
        key_support      = EXCLUDED.key_support,
        sources          = EXCLUDED.sources,
        computed_at      = EXCLUDED.computed_at
""")


def run(town_name: str | None = None, source: str = "all") -> None:
    now = datetime.now(timezone.utc)

    # Step 1: analyze from precedent full_text
    print("Analyzing precedent full_text ...")
    precedent_results: dict[str, list[dict]] = {}
    if source in ("precedents", "all"):
        precedent_results = _analyze_precedents(town_name)
        for town, results in precedent_results.items():
            print(f"  {town}: {len(results)} precedent docs analyzed")

    # Step 2: scrape town websites
    web_results: dict[str, list[dict]] = {}
    if source in ("web", "all"):
        with SessionLocal() as session:
            q = "SELECT town_name, town_url FROM municipalities"
            params: dict = {}
            if town_name:
                q += " WHERE town_name = :town"
                params["town"] = town_name
            towns = session.execute(text(q), params).mappings().all()

        for row in towns:
            town = row["town_name"]
            texts = _scrape_town_minutes(town, row.get("town_url"))
            for txt in texts:
                result = _call_claude(txt)
                if result:
                    result["source"] = "town_website"
                    web_results.setdefault(town, []).append(result)
                time.sleep(0.3)

    # Merge all results
    all_towns: set[str] = set(precedent_results) | set(web_results)

    with SessionLocal() as session:
        for town in all_towns:
            combined = precedent_results.get(town, []) + web_results.get(town, [])

            # Split into BESS and solar result subsets
            bess_results = [r for r in combined if r.get("bess_sentiment") is not None]
            solar_results = [r for r in combined if r.get("solar_sentiment") is not None]

            for project_type, subset in [("bess_standalone", bess_results), ("solar_ground_mount", solar_results)]:
                agg = _aggregate(subset)
                session.execute(_UPSERT, {
                    "town": town,
                    "pt": project_type,
                    "sentiment": agg["sentiment_score"],
                    "support": agg["support_score"],
                    "opposition": agg["opposition_score"],
                    "doc_count": agg["document_count"],
                    "concerns": json.dumps(agg["key_concerns"]),
                    "support_args": json.dumps(agg["key_support"]),
                    "sources": json.dumps(agg["sources"]),
                    "now": now,
                })
                print(f"  {town} / {project_type}: sentiment={agg['sentiment_score']:.2f} ({agg['document_count']} docs)")

        session.commit()

    print("Sentiment analysis complete.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--town", default=None)
    parser.add_argument("--source", choices=["precedents", "web", "all"], default="all")
    args = parser.parse_args()
    run(town_name=args.town, source=args.source)


if __name__ == "__main__":
    main()
