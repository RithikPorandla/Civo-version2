"""Ask Claude to find the current canonical URL for each 404ing citation.

Runs check_citation_links → for every URL that's broken and has no
Wayback snapshot, asks Claude Sonnet 4.6 (with the server-side
web_search tool) to find the live replacement. Writes a reviewable
suggestions JSON; never patches source files on its own.

Human approval is mandatory — regulatory citations must be correct,
not just "200 OK". The script prints candidate URLs; the operator
verifies each one lands on the right page before patching.

Usage
-----
    .venv/bin/python -m scripts.suggest_url_repairs
    .venv/bin/python -m scripts.suggest_url_repairs --json out/repairs.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from anthropic import Anthropic, RateLimitError
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from scripts.check_citation_links import (  # noqa: E402
    collect_from_score_history,
    collect_from_source,
    dedupe,
    USER_AGENT,
    HTTP_TIMEOUT,
)

MODEL = "claude-sonnet-4-6"

URL_RE = re.compile(r"https?://[^\s\"'\)]+")


def _http_probe(client: httpx.Client, url: str) -> int:
    """Return HTTP status after following redirects, 0 on network error."""
    try:
        r = client.head(url, follow_redirects=True, timeout=HTTP_TIMEOUT)
        if r.status_code in (405, 403):
            r = client.get(url, follow_redirects=True, timeout=HTTP_TIMEOUT)
        return r.status_code
    except httpx.HTTPError:
        return 0


# ---------------------------------------------------------------------------
# Hard-coded slug rewrites that don't need Claude
# ---------------------------------------------------------------------------
def _rule_based_replacement(url: str) -> str | None:
    """Fast path: known mass.gov → gis.data.mass.gov remapping.

    MassGIS deprecated every /info-details/massgis-data-X page in 2025.
    The Data Hub at gis.data.mass.gov/search is the official replacement
    and always returns 200, even when a specific dataset slug churns.
    """
    m = re.match(
        r"^https://www\.mass\.gov/info-details/massgis-data-(.+)$",
        url.rstrip("/"),
    )
    if m:
        term = m.group(1).replace("-", " ")
        return f"https://gis.data.mass.gov/search?q={term.replace(' ', '%20')}"
    return None


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------
PROMPT = """
You are repairing a broken regulatory / government citation URL on the
Civo Massachusetts permitting platform. The URL below returns HTTP 404.

Broken URL: {url}

Your job: find the CURRENT canonical URL for the same document or page.
Use web_search to look it up on official sources (mass.gov,
malegislature.gov, gis.data.mass.gov, arcgis.com, etc.). Prefer direct
document URLs over search pages. Prefer the authoritative publisher.

Return JSON ONLY, no markdown, matching exactly:
{{
  "replacement_url": "<the new URL, or null if not findable>",
  "confidence": 0.0-1.0,
  "rationale": "<one sentence: what you found and why this replaces the broken URL>"
}}

Rules:
- Do not guess. If you cannot find a live authoritative page, set replacement_url to null.
- The replacement must be the same underlying document/page as the broken one.
- If the broken URL points to a regulation (e.g., 225 CMR 29), the replacement should be that regulation's current published location.
- If it's a data page (e.g., MassGIS wetlands), the replacement should be the MassGIS Data Hub item for that dataset, or the mass.gov info-details page if it still exists.
"""


def _claude_suggest(client: Anthropic, url: str) -> dict:
    """Call Claude with web_search until it returns a JSON result block."""
    delay = 10.0
    for attempt in range(6):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}],
                messages=[{"role": "user", "content": PROMPT.format(url=url)}],
            )
            break
        except RateLimitError:
            time.sleep(delay)
            delay = min(delay * 1.5, 60.0)
    else:
        return {"replacement_url": None, "confidence": 0.0, "rationale": "rate-limited"}

    # Extract the final text block (Claude may have emitted search + then text).
    text_blocks = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    raw = (text_blocks[-1] if text_blocks else "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "replacement_url": None,
            "confidence": 0.0,
            "rationale": f"non-JSON response: {raw[:300]}",
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, help="Write suggestions JSON here.")
    ap.add_argument(
        "--skip-claude",
        action="store_true",
        help="Only apply rule-based suggestions; no API calls.",
    )
    args = ap.parse_args()

    if not args.skip_claude and not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set; rerun with --skip-claude for rule-only.")
        sys.exit(1)

    refs = collect_from_source()
    try:
        refs.extend(collect_from_score_history())
    except Exception as e:
        print(f"[warn] skipping score_history: {e}")
    buckets = dedupe(refs)
    print(f"[suggest] {len(buckets)} distinct gov URLs")

    suggestions: list[dict] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as http_client:
        anthropic_client = (
            Anthropic() if not args.skip_claude and os.getenv("ANTHROPIC_API_KEY") else None
        )
        for url in sorted(buckets.keys()):
            status = _http_probe(http_client, url)
            if 200 <= status < 400:
                continue

            # Try the deterministic rule first.
            rule_repl = _rule_based_replacement(url)
            if rule_repl:
                # Verify the rule produces a live URL.
                if 200 <= _http_probe(http_client, rule_repl) < 400:
                    suggestions.append(
                        {
                            "old": url,
                            "new": rule_repl,
                            "confidence": 0.95,
                            "rationale": "Rule: MassGIS info-details page → Data Hub search.",
                            "sources": buckets[url],
                        }
                    )
                    print(f"  RULE  {url}\n        → {rule_repl}")
                    continue

            if anthropic_client is None:
                suggestions.append(
                    {
                        "old": url,
                        "new": None,
                        "confidence": 0.0,
                        "rationale": "no rule applies; Claude disabled",
                        "sources": buckets[url],
                    }
                )
                continue

            print(f"  asking Claude for: {url}")
            guess = _claude_suggest(anthropic_client, url)
            new = guess.get("replacement_url")

            # Verify Claude's suggestion is live.
            if new:
                verify = _http_probe(http_client, new)
                if not (200 <= verify < 400):
                    guess["confidence"] = 0.3
                    guess["rationale"] = f"Claude suggested {new} (status {verify})"

            suggestions.append(
                {
                    "old": url,
                    "new": new,
                    "confidence": guess.get("confidence", 0.0),
                    "rationale": guess.get("rationale", ""),
                    "sources": buckets[url],
                }
            )
            status_tag = "CLAUDE" if new else "NONE  "
            print(f"  {status_tag} {url}\n         → {new or '(no suggestion)'}")

    high_conf = [s for s in suggestions if s["new"] and s["confidence"] >= 0.7]
    low_conf = [s for s in suggestions if s["new"] and s["confidence"] < 0.7]
    unsuggested = [s for s in suggestions if not s["new"]]

    print(
        f"\n{len(suggestions)} broken · "
        f"{len(high_conf)} high-confidence · "
        f"{len(low_conf)} low-confidence · "
        f"{len(unsuggested)} no suggestion"
    )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(suggestions, indent=2))
        print(f"\nsuggestions → {args.json}")


if __name__ == "__main__":
    main()
