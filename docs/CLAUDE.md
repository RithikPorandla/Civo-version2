# Civo — Claude Code Project Instructions

You are helping build **Civo**, a Massachusetts permitting intelligence platform for energy developers, utilities, and consultants. Read `docs/PRD.md` and `docs/RESEARCH_AGENT.md` for full context before making significant changes.

## Project essentials

- **Owner:** Rithik
- **Stage:** MVP, week 1 of build
- **Target user:** Permitting consultants (e.g., Chris Rodstrom at CBR Energy Solutions), energy developers, utilities, municipal planners — Massachusetts-focused
- **Positioning:** MA-specific depth layer. Where national tools (Kite Compliance) are broad, Civo is deep on Massachusetts data: every EFSB docket, ConCom decision, NHESP determination, MassDEP wetlands finding, Eversource ESMP project
- **Scoring methodology:** MA EEA Site Suitability for Clean Energy Infrastructure (2024 Climate Act, G.L. c.21A §30, codified in 225 CMR 29.00) — 7 criteria, weighted

## Tech stack (committed — do not change without asking)

- **Backend:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL 16 + PostGIS 3.4 + pgvector, running in Docker Compose for local dev
- **Frontend:** React + Vite + TypeScript, MapLibre GL for maps, deck.gl for spatial overlays
- **LLM:** Anthropic API (Claude Sonnet 4.6 for bulk work, Opus 4.6 for hard reasoning). Model strings: `claude-sonnet-4-6` and `claude-opus-4-6`
- **Geocoding:** Google Places API (Rithik already has a key)
- **Embeddings:** pgvector with Claude or OpenAI embeddings — decide in week 2
- **Deploy target:** Fly.io or Railway, decide in week 2

## Accuracy guardrails (non-negotiable)

1. **Never let AI be the sole source of truth for a regulatory determination.** Vision extracts what it sees. PostGIS tells you what's actually there. If they disagree, flag the conflict and trust the GIS. Surface both to the user.
2. **Every claim cites a source.** Every number, every risk flag, every precedent reference must link to a specific dataset row or document URL. If you cannot cite it, do not claim it.
3. **Every score runs against the validation benchmark.** `docs/benchmark.yaml` contains real MA parcels with expected outcomes. Every scoring engine change re-runs the full benchmark. If Pearson correlation against expected scores drops below 0.7, fail the build.
4. **Use real parcel polygons, not lat/lon points.** All spatial scoring runs against MassGIS L3 Parcel polygons, with area-weighted overlap calculations. A point-in-polygon shortcut is never acceptable.
5. **Version the scoring config.** Weights and criteria thresholds live in a versioned YAML file. When the state updates 225 CMR 29.00, bump the config version and re-score historical reports.

## Build principles

- **Ship the scoring engine first, UI last.** A working pure-Python scoring function that produces correct JSON for 10 real addresses is worth more than a beautiful frontend returning wrong numbers.
- **Commit after every working feature.** Not at end of day. If a feature works, commit it.
- **Run tests, don't eyeball output.** Write pytest cases for the scoring engine and the ingestion functions. CI runs the benchmark on every commit.
- **No premature optimization.** No Celery, no Kubernetes, no microservices in week 1. A single FastAPI app, a single Postgres, asyncio for background tasks. Add complexity only when there is real load.
- **Small, testable prompts when calling Claude.** For any LLM-powered feature, write the prompt to return strict JSON matching a pydantic schema. Reject malformed output. Never parse free-form text.

## The 7 scoring criteria (exact names and weights from MA EEA methodology)

1. **Development Potential / Grid Alignment** — weight 20%. Distance from existing or planned substation. Cross-reference Eversource ESMP project locations.
2. **Climate Resilience** — weight 15%. FEMA flood zone + sea level rise exposure. Use ResilientMass Climate Resilience Design Standards methodology.
3. **Carbon Storage** — weight 15%. Current biomass/soil carbon stocks. Top 20% carbon forests are high-concern.
4. **Biodiversity** — weight 20%. BioMap Core Habitat, Critical Natural Landscape, NHESP Priority Habitat, NHESP Estimated Habitat. UMass CAPS IEI optional.
5. **Social & Environmental Burdens** — weight 10%. MassEnviroScreen cumulative burden score. EJ community designation.
6. **Social & Environmental Benefits** — weight 10%. Brownfield bonus, built-environment bonus, job creation, transit proximity.
7. **Agricultural Production** — weight 10%. USDA NRCS prime farmland soils, Chapter 61A status.

Total score is 0-100, weighted sum. Buckets: SUITABLE (70+), CONDITIONALLY SUITABLE (50-69), CONSTRAINED (<50).

## Ineligible areas (automatic no-go, from 225 CMR 29.00)

- BioMap Core Habitat
- NHESP Priority Habitat
- Article 97 protected open space
- Top 20% of forests for carbon storage statewide
- Wetland resource areas (310 CMR 10.04)
- State Register properties (950 CMR 71.03)

Infrastructure projects can apply for a waiver in these zones, generation/storage cannot.

## Data sources (all MA-specific, all free/public)

- **MassGIS Data Hub:** L3 Parcels, BioMap, NHESP, FEMA NFHL, wetlands, Article 97, prime farmland, MassEnviroScreen
- **Eversource ESMP (DPU 24-10, Jan 2024):** 29 planned distribution projects already extracted in earlier work
- **EFSB dockets:** search via mass.gov/efsb
- **Town websites:** 351 MA municipalities, ConCom and Planning Board pages
- **MassDEP Waste Site Portal:** contamination and wetlands determinations

## What NOT to build in week 1

- User authentication (anonymous MVP, email-gated PDF export)
- Stripe billing
- Multi-state support (MA only)
- Full 351-municipality research agent coverage (start with 10 target towns)
- Historic aerial photo analysis
- Vision-based site plan upload (week 2)
- ConCom meeting ingestion at scale (manual curation for week 1)

## When in doubt

- Ask before adding a new dependency
- Ask before creating a new microservice or splitting the backend
- Ask before changing the scoring weights
- Ask before skipping a benchmark run
- Proceed without asking on: writing tests, adding types, improving error messages, writing docstrings, small refactors that don't change behavior
