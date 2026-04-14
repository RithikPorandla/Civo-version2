# Civo Research Agent — Design Spec

## Purpose

Build a background agent that continuously enriches Civo's knowledge base with
structured, cited, up-to-date intelligence about every Massachusetts
municipality's permitting posture. This is Civo's primary moat: data depth that
national competitors (Kite Compliance) cannot replicate without hiring a
Massachusetts-specific team.

## What the agent produces

For each of the 351 MA municipalities, a row in the `municipalities` table with:

- Town name, county, population, FIPS code
- Official town website URL (verified)
- Planning Board: members, meeting schedule, contact email, page URL
- Conservation Commission: members, meeting schedule, contact email, page URL
- Zoning Board of Appeals: members, meeting schedule, contact email, page URL
- Building Department: contact, page URL
- Zoning bylaws: document URL, last-updated date
- Wetlands bylaw (if stricter than state): document URL
- Solar / battery storage bylaws: document URL, summary
- Active moratoriums: type, dates, source URL
- Recent ConCom decisions: count in last 12 months, most recent date
- Political risk indicators: JSON blob with recent town meeting articles,
  opposition groups, press coverage, confidence scores
- Last refreshed timestamp per field
- Source URL for every claim (non-negotiable)

For each municipality, also populate the `precedents` table with:

- Docket / case number (or synthetic ID if town-level)
- Project type (solar, battery storage, substation, transmission, commercial,
  residential, mixed-use, data center, other)
- Project address (geocoded to L3 parcel when possible)
- Applicant name
- Decision (approved, approved_with_conditions, denied, withdrawn, pending)
- Key conditions imposed (as array of strings)
- Filing date, decision date
- Meeting body (ConCom, Planning Board, ZBA, Special Town Meeting)
- Source document URL
- Full text chunk (for pgvector semantic search)

## Architecture

The agent runs as a long-lived Python process that processes one municipality
at a time. It uses Claude (Sonnet 4.6 by default, Opus 4.6 for hard reasoning)
via tool use, with the agent's own code orchestrating the sequence.

```
                    ┌──────────────────────┐
                    │   Research Agent     │
                    │   (Python + Claude)  │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼─────────────────┐
              │                │                 │
              ▼                ▼                 ▼
       ┌──────────┐    ┌──────────────┐    ┌──────────┐
       │  Claude  │    │  Web fetch   │    │ Postgres │
       │   API    │    │  + Places    │    │  brain   │
       └──────────┘    └──────────────┘    └──────────┘
```

The agent does NOT use a full browser / Playwright. It uses `httpx` for fetches
and Claude vision for any PDF extraction. This keeps it lightweight enough to
run on a 16GB M1.

## Processing sequence per municipality

### Step 1: Identify the official town website

Claude prompt (Sonnet 4.6): "Given the municipality name '{town}, Massachusetts',
find the official .gov or .org town website URL. Return only the URL, no
commentary. If you are uncertain, return null."

Verify the URL by fetching it and checking for:
- Town seal or name in `<title>`
- Population or state reference in first 2KB of HTML
- At least one of "planning", "conservation", "zoning" in page links

If verification fails, fall back to a Google Places search and retry.

### Step 2: Crawl key department pages

Fetch the town homepage and extract all links. Use a classifier prompt to
categorize links into department buckets:

- planning_board
- conservation_commission
- zoning_board
- building_department
- bylaws_page
- meeting_archive

Claude prompt (Sonnet 4.6): "Here is a list of links from the Acton, MA town
website. Return a JSON object mapping each relevant department to the best
matching URL. Categories: planning_board, conservation_commission, zoning_board,
building_department, bylaws_page, meeting_archive. If no good match, use null.
Respond only with JSON matching the schema below."

Fetch each categorized URL and extract structured data using a second Claude
call per page. Each extraction uses a tight JSON schema — never free-form text.

### Step 3: Ingest recent ConCom agendas

The ConCom page usually has a list of recent meeting agendas as PDF links. The
agent downloads the last 12 months of agendas (or 20 most recent, whichever is
smaller). For each agenda PDF:

1. Download via `httpx`, store hash and raw bytes in object storage
2. Convert to base64 and send to Claude vision with a strict extraction schema
3. Extract: meeting date, list of agenda items, for each item: project address,
   applicant, project type, action requested, decision (if noted)
4. Write each item to the `precedents` table with source URL and confidence

Claude prompt (Sonnet 4.6, vision): "This is a Massachusetts Conservation
Commission meeting agenda. Extract every agenda item that involves a specific
project (not procedural items). For each project, return the address, applicant
name, project type, action requested, and decision if stated. Respond only with
JSON matching the schema. If a field is not clearly stated, return null — do
not guess."

### Step 4: Political risk signals

Search for recent news and town meeting articles:

- Google Custom Search API (or SerpAPI) for site-specific queries like
  "battery storage moratorium site:{town-website}"
- Fetch returned pages and have Claude classify each as signal / noise
- For signals, extract: topic, date, stance (pro / anti / neutral), source URL

Write findings to the municipality row's `political_signals` JSONB field with
per-signal confidence scores.

### Step 5: Persist and set refresh schedule

Write everything to Postgres in a single transaction. Set the row's
`next_refresh_at` based on activity level:

- High activity (10+ decisions in last 90 days): refresh weekly
- Medium activity (3-9 decisions in last 90 days): refresh monthly
- Low activity (0-2 decisions in last 90 days): refresh quarterly

## Tool use pattern

The agent uses Claude's tool use API with these tools defined:

```python
TOOLS = [
    {
        "name": "fetch_url",
        "description": "Fetch a URL and return the response body (HTML or text, truncated to 50KB)",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "fetch_pdf",
        "description": "Download a PDF and return it as base64 for vision analysis",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "search_web",
        "description": "Run a web search and return top 10 results as JSON",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "write_municipality_field",
        "description": "Write a single field to the municipalities table with source citation",
        "input_schema": {
            "type": "object",
            "properties": {
                "town": {"type": "string"},
                "field": {"type": "string"},
                "value": {},
                "source_url": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["town", "field", "value", "source_url", "confidence"],
        },
    },
    {
        "name": "write_precedent",
        "description": "Insert a new row into the precedents table with source citation",
        "input_schema": {
            "type": "object",
            "properties": {
                "town": {"type": "string"},
                "project_address": {"type": "string"},
                "project_type": {"type": "string"},
                "applicant": {"type": "string"},
                "decision": {"type": "string"},
                "conditions": {"type": "array", "items": {"type": "string"}},
                "filing_date": {"type": "string"},
                "decision_date": {"type": "string"},
                "meeting_body": {"type": "string"},
                "source_url": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["town", "project_type", "source_url", "confidence"],
        },
    },
]
```

The agent loop: call Claude with the system prompt and the municipality name,
handle any tool calls by executing them and feeding results back, repeat until
Claude emits a `stop_reason: end_turn` indicating the research is complete.

## Accuracy guardrails

1. **Every field has a source URL.** If Claude writes to the database without a
   source, reject the write.
2. **Confidence scores below 0.7 are flagged.** A human review queue surfaces
   low-confidence extractions for manual verification.
3. **URL verification before write.** Any URL the agent plans to save is first
   fetched to verify it resolves (200 or 301). Dead links are not written.
4. **No fabricated people or contacts.** If the agent cannot find a real name
   and email for a Planning Board member, it writes null rather than making one
   up. This is enforced by prompt wording and verified by unit tests.
5. **Provenance on conflicts.** If the agent finds conflicting information
   across sources (two different ConCom meeting schedules, for example), it
   writes both and flags the conflict rather than picking one.

## Cost estimate

Running the full research agent against all 351 MA municipalities:

- ~10 Claude calls per town at ~$0.015 each (Sonnet 4.6 blended in/out)
- ~5 vision calls per town for PDF extraction at ~$0.03 each
- ~20 ConCom agenda PDFs per town average, vision extraction at ~$0.02 each
- Web search calls at ~$0.005 each, ~10 per town

Total per-town cost: ~$1.00-1.50
Total for 351 towns: ~$350-525 one-time initial build
Ongoing refresh cost: ~$50-100/month at quarterly average refresh cadence

Affordable on a solo-founder budget. Do NOT optimize this prematurely —
accuracy is worth more than savings.

## Day-by-day build plan

**Day 1:** SQL schema for `municipalities` and `precedents` tables. Write the
tool functions (`fetch_url`, `fetch_pdf`, `write_municipality_field`,
`write_precedent`) as plain Python. No Claude integration yet. Unit test that
writes and reads a fake Acton row.

**Day 2:** Wire up Claude tool use. Run the agent against Acton only. Verify
it finds the town website, identifies the ConCom page, and writes at least
one correct municipality field with a real source URL.

**Day 3:** Add PDF vision extraction. Run against Acton's last 12 months of
ConCom agendas. Verify precedents are extracted with reasonable accuracy.
Manually spot-check 10 extractions.

**Day 4:** Expand to 10 target municipalities (Acton, Burlington, Falmouth,
Natick, Worthington, East Freetown, Whately, Dennis, Somerville, Cambridge —
the towns with Eversource ESMP projects from the validation benchmark).
Verify each completes successfully.

**Day 5:** Wire retrieval into the scoring engine. When a user scores an
address, the scoring report should include the 3-5 nearest precedents by
project type and location, pulled via pgvector semantic search.

**Day 6 (optional):** Launch the overnight batch job to process all 351
municipalities. Sleep. Wake up to a statewide database.

## Open questions

- Should we use Claude's built-in web search tool instead of a custom
  `search_web` tool? (Probably yes for v1 — simpler and higher quality)
- How do we handle towns whose websites are behind Cloudflare bot protection?
  (Defer until we hit one)
- Should precedents include full text chunks for vector search, or just
  structured fields? (Both — structured for exact queries, chunks for
  semantic search)
- Do we need manual review on every new precedent before it's visible to
  users, or only on low-confidence ones? (Only low-confidence; trust high-
  confidence with visible confidence indicators in the UI)

---

*This document is the source of truth for the research agent design. Update
it as the implementation evolves and edge cases are discovered.*
