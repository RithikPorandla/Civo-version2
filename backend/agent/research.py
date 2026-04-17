"""Civo Research Agent — populates `municipalities` and `precedents`.

Per docs/RESEARCH_AGENT.md: a Claude Sonnet 4.6 agent with tool use.
Tools:
  - fetch_url        (custom, HTTP GET + HTML-to-text truncation)
  - fetch_pdf        (custom, returns base64 for Claude vision)
  - web_search       (Anthropic server-side tool; Claude executes it)
  - write_municipality_field
  - write_precedent

Every DB write demands a source_url and a confidence score. Claude is
instructed never to fabricate names/emails; null is preferred to a guess.

CLI:
  python -m agent.research --town Acton [--max-turns 40] [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import time

import httpx
from anthropic import Anthropic, RateLimitError
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import SessionLocal  # noqa: E402
from ingest._common import resolve_town_id  # noqa: E402

load_dotenv()

MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TURNS = 40
FETCH_BODY_CAP = 6_000  # chars of plain-text body returned to Claude
FETCH_LINK_CAP = 60  # top N hyperlinks surfaced per page
FETCH_PDF_BYTE_CAP = 8 * 1024 * 1024  # 8 MB hard limit on PDFs


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def _html_to_text(html: str) -> str:
    """Strip tags + collapse whitespace — good enough to feed Claude."""
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def tool_fetch_url(url: str) -> dict:
    try:
        r = httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "CivoResearchAgent/0.1 (+civo.energy)"},
        )
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "url": url}
    final = str(r.url)
    ctype = r.headers.get("content-type", "")
    if "pdf" in ctype.lower():
        return {
            "ok": False,
            "error": "URL is a PDF — call fetch_pdf instead.",
            "url": final,
        }
    body = r.text
    # Extract hyperlinks (href + visible text) BEFORE stripping HTML so Claude
    # can classify them without us losing the URLs.
    links = [
        {"href": m.group(1), "text": _html_to_text(m.group(2))[:200]}
        for m in re.finditer(
            r'<a[^>]+href="([^"#][^"]*)"[^>]*>([\s\S]*?)</a>',
            body,
            flags=re.IGNORECASE,
        )
    ][:FETCH_LINK_CAP]
    return {
        "ok": r.is_success,
        "status": r.status_code,
        "url": final,
        "content_type": ctype,
        "title": (re.search(r"<title>(.*?)</title>", body, re.I | re.S) or [None, ""])[1].strip(),
        "links": links,
        "text": _html_to_text(body)[:FETCH_BODY_CAP],
    }


def tool_fetch_pdf(url: str) -> dict:
    try:
        r = httpx.get(
            url,
            timeout=60,
            follow_redirects=True,
            headers={"User-Agent": "CivoResearchAgent/0.1 (+civo.energy)"},
        )
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "url": url}
    if not r.is_success:
        return {"ok": False, "status": r.status_code, "url": str(r.url)}
    if len(r.content) > FETCH_PDF_BYTE_CAP:
        return {
            "ok": False,
            "error": f"PDF too large ({len(r.content)} bytes); cap {FETCH_PDF_BYTE_CAP}",
            "url": str(r.url),
        }
    b64 = base64.standard_b64encode(r.content).decode("ascii")
    return {
        "ok": True,
        "url": str(r.url),
        "size": len(r.content),
        "base64": b64,
    }


# ---------- DB writes ------------------------------------------------------
def _ensure_municipality_row(session, town_name: str) -> int:
    town_id = resolve_town_id(town_name)
    session.execute(
        text(
            """
            INSERT INTO municipalities (town_id, town_name)
            VALUES (:tid, :name)
            ON CONFLICT (town_id) DO NOTHING
            """
        ),
        {"tid": town_id, "name": town_name},
    )
    return town_id


# Columns on `municipalities` that the agent can address directly.
_SCALAR_COLS = {"town_url", "county", "population", "fips_code"}
_JSONB_COLS = {
    "planning_board",
    "conservation_commission",
    "zoning_board",
    "building_department",
    "bylaws",
    "moratoriums",
    "political_signals",
}


def _merge_dotted(target: dict | None, dotted: str, value: Any) -> dict:
    """Set ``target[a][b][c] = value`` from a dotted path ``"a.b.c"``."""
    out = dict(target or {})
    keys = dotted.split(".")
    cursor = out
    for k in keys[:-1]:
        if not isinstance(cursor.get(k), dict):
            cursor[k] = {}
        cursor = cursor[k]
    cursor[keys[-1]] = value
    return out


def tool_write_municipality_field(
    session,
    town: str,
    field: str,
    value: Any,
    source_url: str,
    confidence: float,
) -> dict:
    if not source_url:
        return {"ok": False, "error": "source_url is required"}
    if confidence is None or not (0.0 <= float(confidence) <= 1.0):
        return {"ok": False, "error": "confidence must be in [0, 1]"}
    town_id = _ensure_municipality_row(session, town)

    # field = "planning_board.chair.name" -> column "planning_board", path "chair.name"
    head, *tail = field.split(".", 1)
    subpath = tail[0] if tail else None

    if head in _SCALAR_COLS and not tail:
        session.execute(
            text(f"UPDATE municipalities SET {head} = :v WHERE town_id = :tid"),
            {"v": value, "tid": town_id},
        )
    elif head in _JSONB_COLS:
        row = session.execute(
            text(f"SELECT {head} FROM municipalities WHERE town_id = :tid"),
            {"tid": town_id},
        ).scalar()
        dotted = subpath or "_value"
        merged = _merge_dotted(row, dotted, value)
        session.execute(
            text(f"UPDATE municipalities SET {head} = CAST(:v AS jsonb) WHERE town_id = :tid"),
            {"v": json.dumps(merged), "tid": town_id},
        )
    else:
        return {
            "ok": False,
            "error": (
                f"unknown field {field!r}. Scalar fields: "
                f"{sorted(_SCALAR_COLS)}. JSONB roots: {sorted(_JSONB_COLS)}."
            ),
        }

    # Record citation + confidence in political_signals._citations[field] for audit.
    cit_row = session.execute(
        text("SELECT political_signals FROM municipalities WHERE town_id = :tid"),
        {"tid": town_id},
    ).scalar()
    cits = dict(cit_row or {})
    cits_inner = dict(cits.get("_citations") or {})
    cits_inner[field] = {
        "source_url": source_url,
        "confidence": float(confidence),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    cits["_citations"] = cits_inner
    session.execute(
        text(
            "UPDATE municipalities SET political_signals = CAST(:v AS jsonb) WHERE town_id = :tid"
        ),
        {"v": json.dumps(cits), "tid": town_id},
    )
    session.commit()
    return {"ok": True, "town_id": town_id, "field": field}


def tool_write_precedent(session, town: str, **kw) -> dict:
    required = {"project_type", "source_url", "confidence"}
    missing = [k for k in required if not kw.get(k)]
    if missing:
        return {"ok": False, "error": f"missing required fields: {missing}"}
    if not (0.0 <= float(kw["confidence"]) <= 1.0):
        return {"ok": False, "error": "confidence must be in [0, 1]"}
    town_id = _ensure_municipality_row(session, town)

    def _date_or_none(s: str | None):
        if not s:
            return None
        # Accept YYYY-MM-DD or ISO.
        try:
            return datetime.fromisoformat(s).date()
        except ValueError:
            return None

    row = session.execute(
        text(
            """
            INSERT INTO precedents (
                town_id, docket, project_type, project_address, applicant,
                decision, conditions, filing_date, decision_date,
                meeting_body, source_url, full_text, confidence
            ) VALUES (
                :town_id, :docket, :project_type, :project_address, :applicant,
                :decision, :conditions, :filing_date, :decision_date,
                :meeting_body, :source_url, :full_text, :confidence
            )
            RETURNING id
            """
        ),
        {
            "town_id": town_id,
            "docket": kw.get("docket"),
            "project_type": kw["project_type"],
            "project_address": kw.get("project_address"),
            "applicant": kw.get("applicant"),
            "decision": kw.get("decision"),
            "conditions": kw.get("conditions") or None,
            "filing_date": _date_or_none(kw.get("filing_date")),
            "decision_date": _date_or_none(kw.get("decision_date")),
            "meeting_body": kw.get("meeting_body"),
            "source_url": kw["source_url"],
            "full_text": kw.get("full_text"),
            "confidence": float(kw["confidence"]),
        },
    )
    pid = row.scalar_one()
    session.commit()
    return {"ok": True, "precedent_id": pid, "town_id": town_id}


# ---------------------------------------------------------------------------
# Tools schema (what Claude sees)
# ---------------------------------------------------------------------------
TOOLS: list[dict] = [
    {
        "name": "fetch_url",
        "description": (
            "Fetch a URL and return its HTTP status, final URL after redirects, "
            "page <title>, up to 150 hyperlinks (href + visible text), and up to "
            "50KB of plain-text body. Use this for HTML pages. For PDFs, call "
            "fetch_pdf instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "fetch_pdf",
        "description": (
            "Download a PDF and return it base64-encoded for vision analysis in a "
            "follow-up turn. Use this for meeting agendas, decision letters, and "
            "bylaw documents. Capped at 8MB."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 5,
    },
    {
        "name": "write_municipality_field",
        "description": (
            "Write a verified field to the municipalities table. `field` may be a "
            "scalar column ('town_url', 'county', 'population', 'fips_code') or a "
            "dotted JSONB path like 'planning_board.chair.name', "
            "'conservation_commission.meeting_schedule', 'bylaws.solar.url', "
            "'moratoriums.battery_storage.end_date'. source_url is mandatory — a "
            "write without a resolvable source is rejected. confidence in [0,1]."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "town": {"type": "string"},
                "field": {"type": "string"},
                "value": {},
                "source_url": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["town", "field", "value", "source_url", "confidence"],
        },
    },
    {
        "name": "write_precedent",
        "description": (
            "Insert a precedent row (one ConCom / Planning Board / ZBA / EFSB "
            "action on a specific project). Never fabricate names or addresses — "
            "use null when the agenda PDF is ambiguous."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "town": {"type": "string"},
                "docket": {"type": "string"},
                "project_address": {"type": "string"},
                "project_type": {
                    "type": "string",
                    "enum": [
                        "solar",
                        "battery_storage",
                        "substation",
                        "transmission",
                        "commercial",
                        "residential",
                        "mixed_use",
                        "data_center",
                        "industrial",
                        "other",
                    ],
                },
                "applicant": {"type": "string"},
                "decision": {
                    "type": "string",
                    "enum": [
                        "approved",
                        "approved_with_conditions",
                        "denied",
                        "withdrawn",
                        "pending",
                        "continued",
                    ],
                },
                "conditions": {"type": "array", "items": {"type": "string"}},
                "filing_date": {"type": "string", "description": "YYYY-MM-DD"},
                "decision_date": {"type": "string", "description": "YYYY-MM-DD"},
                "meeting_body": {
                    "type": "string",
                    "enum": [
                        "ConCom",
                        "PlanningBoard",
                        "ZBA",
                        "SpecialTownMeeting",
                        "TownMeeting",
                        "EFSB",
                        "SelectBoard",
                        "BuildingDept",
                    ],
                },
                "source_url": {"type": "string"},
                "full_text": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["town", "project_type", "source_url", "confidence"],
        },
    },
]


SYSTEM_PROMPT = textwrap.dedent(
    """
    You are the Civo Research Agent. Your job is to populate a single
    Massachusetts municipality's row in the `municipalities` table and
    a handful of `precedents` rows by reading the town's official website
    and recent Conservation Commission meeting agendas.

    ## Process (follow in order)

    1. **Find the official town website.** Use web_search with a query
       like '"{town}, Massachusetts" official town website'. The result
       should be a .gov, .org, or municipal .com domain. Verify with
       fetch_url that the page clearly identifies the town. Write
       `town_url`.
    2. **Identify department pages.** From the town homepage's link
       list, pick the URLs most likely to be the Planning Board,
       Conservation Commission, Zoning Board of Appeals, and Building
       Department. Fetch each. Write dotted-path fields under the
       relevant JSONB column (e.g., 'planning_board.url',
       'planning_board.meeting_schedule', 'conservation_commission.url',
       'conservation_commission.contact_email'). If you cannot find a
       name/email with high confidence, WRITE NULL — do not invent.
    3. **Bylaws.** Find solar / battery storage / wetlands / zoning
       bylaw document URLs. Write 'bylaws.solar.url', 'bylaws.solar.last_updated',
       etc.
    4. **Moratoriums.** If the town has an active moratorium (battery
       storage, solar, data center, etc.), write 'moratoriums.<type>.*'
       with start_date, end_date, and source_url.
    5. **ConCom precedents.** Browse the ConCom meeting-archive page.
       NOTE (step 7a — TODO, deferred to next sprint): check DOER model
       bylaw adoption status for solar and BESS. Search queries to run
       once this step is implemented:
         - '"{town}" DOER model bylaw'
         - '"{town}" solar zoning bylaw adoption'
         - '"{town}" 225 CMR 29'
         - site:{town_url} "BESS" OR "battery storage"
         - '"{town}" annual town meeting warrant solar article'
       Expected outputs: one row in municipal_doer_adoption per
       (town, project_type ∈ {solar, bess}) with source_url,
       adoption_status ∈ {adopted, in_progress, not_started, unknown},
       confidence per the scoring guide in the sprint spec. Use a new
       write_doer_adoption tool (not yet implemented — build alongside).
       Pick the 5-10 most recent agenda PDFs (last 12 months). For each,
       call fetch_pdf and examine the contents. For every agenda item
       that references a specific project (not a procedural item),
       call write_precedent with a project_type from the allowed list,
       source_url = the agenda URL, confidence reflecting how clearly
       the PDF identifies the project.

    ## Hard rules

    - **Every DB write MUST include a resolving source_url.** Do not
      write fields sourced from your own prior knowledge.
    - **Confidence < 0.7 is OK** — just be honest. The review queue
      handles low-confidence rows.
    - **Never invent people, emails, addresses, or docket numbers.**
      Use null when the source is ambiguous.
    - **Prefer breadth over depth for this pass.** One good precedent
      per meeting is fine.
    - **One fetch_pdf per turn.** The runtime attaches at most one PDF
      document per user message. If you request multiple, the second
      and later will error — call again on the next turn.
    - **Stop when done.** When you have populated `town_url`, at least
      3 department fields, and between 3 and 10 precedents, emit a
      short summary and stop — don't keep browsing.
    """
).strip()


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------
class ResearchAgent:
    def __init__(self, town: str, max_turns: int = DEFAULT_MAX_TURNS, dry_run: bool = False):
        self.town = town
        self.max_turns = max_turns
        self.dry_run = dry_run
        self.client = Anthropic()
        self.session = SessionLocal()
        self.turn = 0
        self.usage = {"input_tokens": 0, "output_tokens": 0, "server_tool_use": 0}

    # ------- tool dispatch
    def _run_tool(self, name: str, inp: dict) -> Any:
        if self.dry_run and name.startswith("write_"):
            return {"ok": True, "dry_run": True, "tool": name, "input": inp}
        if name == "fetch_url":
            return tool_fetch_url(inp["url"])
        if name == "fetch_pdf":
            return tool_fetch_pdf(inp["url"])
        if name == "write_municipality_field":
            return tool_write_municipality_field(self.session, **inp)
        if name == "write_precedent":
            return tool_write_precedent(self.session, **inp)
        return {"ok": False, "error": f"unknown tool {name!r}"}

    # ------- main loop
    def run(self) -> dict:
        user_msg = (
            f"Research the municipality of {self.town}, Massachusetts. "
            f"Follow the process in the system prompt. Start by finding the "
            f"official town website."
        )
        messages: list[dict] = [{"role": "user", "content": user_msg}]

        while self.turn < self.max_turns:
            self.turn += 1
            # 429 backoff: honor the retry-after header if present, else
            # wait exponentially up to 60s per attempt.
            delay = 10.0
            for attempt in range(6):
                try:
                    resp = self.client.messages.create(
                        model=MODEL,
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        tools=TOOLS,
                        messages=messages,
                    )
                    break
                except RateLimitError as e:
                    retry_after = None
                    try:
                        retry_after = float(e.response.headers.get("retry-after") or 0)
                    except Exception:
                        pass
                    wait = retry_after if retry_after and retry_after > 0 else delay
                    wait = min(wait, 60.0)
                    print(f"[turn {self.turn}] 429 rate-limited; sleeping {wait:.0f}s")
                    time.sleep(wait)
                    delay = min(delay * 1.5, 60.0)
            else:
                raise RuntimeError("rate-limited 6 times, giving up")
            u = getattr(resp, "usage", None)
            if u:
                self.usage["input_tokens"] += getattr(u, "input_tokens", 0) or 0
                self.usage["output_tokens"] += getattr(u, "output_tokens", 0) or 0
                stu = getattr(u, "server_tool_use", None)
                if stu:
                    self.usage["server_tool_use"] += getattr(stu, "web_search_requests", 0) or 0

            # Echo the assistant turn.
            content_out = [block.model_dump() for block in resp.content]
            messages.append({"role": "assistant", "content": content_out})

            tool_blocks = [b for b in resp.content if b.type == "tool_use"]
            if not tool_blocks:
                # end_turn / other stop reason — we're done.
                print(f"\n[turn {self.turn}] stop_reason={resp.stop_reason}")
                break

            tool_results: list[dict] = []
            attached_documents: list[dict] = []
            for tb in tool_blocks:
                print(f"[turn {self.turn}] -> {tb.name}({json.dumps(tb.input)[:180]})")
                result = self._run_tool(tb.name, tb.input)
                # fetch_pdf: return a compact ack via tool_result AND attach the
                # PDF as a document content block so Claude can vision it.
                # Cap at 1 PDF per turn to keep context manageable.
                if tb.name == "fetch_pdf" and result.get("ok") and not attached_documents:
                    ack = {
                        "ok": True,
                        "url": result["url"],
                        "size": result["size"],
                        "note": "PDF attached as a document content block in this same user message.",
                    }
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": json.dumps(ack),
                        }
                    )
                    attached_documents.append(
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": result["base64"],
                            },
                        }
                    )
                elif tb.name == "fetch_pdf" and result.get("ok") and attached_documents:
                    # Queue a reminder to fetch again in the next turn.
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": json.dumps(
                                {
                                    "ok": False,
                                    "error": ("one PDF per turn; call fetch_pdf again next turn"),
                                    "url": result["url"],
                                }
                            ),
                        }
                    )
                else:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": json.dumps(result)[:120_000],
                        }
                    )
            messages.append({"role": "user", "content": tool_results + attached_documents})

        self.session.close()
        return {"turns": self.turn, "usage": self.usage}


def main() -> None:
    ap = argparse.ArgumentParser(description="Civo Research Agent")
    ap.add_argument("--town", required=True)
    ap.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    ap.add_argument("--dry-run", action="store_true", help="Don't commit DB writes")
    args = ap.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set")

    agent = ResearchAgent(args.town, max_turns=args.max_turns, dry_run=args.dry_run)
    stats = agent.run()
    print("\n" + json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
