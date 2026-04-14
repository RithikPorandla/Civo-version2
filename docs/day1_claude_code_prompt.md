# Day 1 — First Prompt for Claude Code

Copy-paste this as your first message to Claude Code after opening the civo repo.

---

## The prompt

Read `CLAUDE.md`, `docs/PRD.md`, `docs/RESEARCH_AGENT.md`, and `docs/benchmark.yaml` carefully before making any changes. These four files are the source of truth for this project.

Today is **day 1** of a one-week MVP build for **Civo**, a Massachusetts permitting intelligence platform. I need you to set up the backend foundation. The goal is a working scoring engine against the 10 parcels in `docs/benchmark.yaml` by end of day — beautiful frontend can wait until day 5.

### Scope for this session

Build the minimum working backend:

1. **Project structure**
   - FastAPI project under `backend/` with `app/`, `tests/`, and `ingest/` subdirectories
   - `pyproject.toml` with dependencies: `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `geoalchemy2`, `psycopg2-binary`, `httpx`, `pyyaml`, `pytest`, `anthropic`, `shapely`, `rasterio` — nothing else yet
   - `.env.example` with placeholders for `DATABASE_URL`, `ANTHROPIC_API_KEY`, `GOOGLE_PLACES_API_KEY`
   - `.gitignore` covering `.env`, `__pycache__`, `.pytest_cache`, `*.pyc`, `data/`

2. **Docker Compose**
   - Postgres 16 with PostGIS 3.4 and pgvector extensions enabled
   - Single service, exposed on port 5432
   - Persistent volume for the db
   - Health check that verifies both extensions are installed
   - `docker-compose up -d` should just work from a clean clone

3. **Database schema**
   - Alembic set up for migrations
   - Initial migration creates these tables:
     - `parcels` — L3 parcel polygons with MassGIS attributes, geometry in EPSG:26986 (MA State Plane)
     - `habitat_biomap_core` — BioMap Core Habitat polygons
     - `habitat_nhesp_priority` — NHESP Priority Habitat polygons
     - `flood_zones` — FEMA NFHL polygons
     - `wetlands` — MassGIS wetlands polygons
     - `esmp_projects` — the 29 Eversource ESMP projects with location, name, sub-region, ISD, MW
     - `score_history` — every computed score with parcel id, config version, timestamp, full report JSON
   - GiST indexes on all geometry columns
   - Unit test that spins up the db, runs migrations, and verifies all tables exist

4. **Ingestion script for Acton only**
   - `ingest/l3_parcels.py --town Acton` pulls Acton L3 parcels from the MassGIS ArcGIS REST feature service and loads them into the `parcels` table
   - Uses the MassGIS Data Hub REST endpoint (find the correct URL during the task — do not hardcode a placeholder)
   - Handles pagination (the API returns 2000 features per page max)
   - Idempotent — running twice does not duplicate rows
   - Includes a unit test using a small fixture of 5 parcels

5. **Scoring engine — stub first, real later**
   - `app/scoring/engine.py` — pure Python function `score_site(parcel_id: str, config_version: str = "ma-eea-2026-v1") -> SuitabilityReport`
   - For day 1, implement only the **Development Potential / Grid Alignment** criterion — distance from the parcel centroid to the nearest ESMP project, with full scoring math from CLAUDE.md
   - The other 6 criteria should return placeholder scores of 5/10 with a TODO comment — we will fill them in day 2
   - The report JSON structure must match the shape in the PRD exactly
   - Pydantic models for `SuitabilityReport`, `CriterionScore`, `SourceCitation`

6. **Benchmark test**
   - `tests/test_benchmark.py` loads `docs/benchmark.yaml`, runs the scoring engine against every parcel that has an L3 polygon loaded, and prints a diff table of computed vs expected scores
   - Does NOT yet enforce the Pearson correlation threshold — we need more criteria working first
   - Instead, prints a warning for any parcel more than 15 points off from expected

7. **Health check endpoint**
   - `GET /health` returns JSON with: database reachable, PostGIS available, pgvector available, number of parcels loaded, number of ESMP projects loaded, scoring config version
   - `GET /score?address=...` — stub that geocodes via Google Places and returns a placeholder JSON with "not implemented" — we wire it up day 2

### How to work

- Commit after every working piece. Not at end of day.
- Run tests as you go. Don't just eyeball output.
- If you need to add a dependency not on my list, ask first.
- If something in CLAUDE.md or the PRD is unclear, ask — do not guess.
- Write docstrings and type hints on every public function.
- Use `ruff` for linting and `mypy` for type checking. Add them to `pyproject.toml` as dev dependencies.

### What success looks like at end of day

When I come back to review, I should be able to:

```bash
git clone <repo>
cd civo
docker-compose up -d
cp .env.example .env   # I fill in my keys
cd backend
uv sync               # or pip install -e .
alembic upgrade head
python ingest/l3_parcels.py --town Acton
pytest
uvicorn app.main:app --reload
curl http://localhost:8000/health
```

And see a passing health check showing Acton parcels loaded, the 29 ESMP projects preloaded (hardcode them in a seed migration from the ESMP data we extracted earlier — I'll paste the list if you need it), and the benchmark test showing a diff table of expected vs computed scores for the grid alignment criterion only.

### What NOT to do today

- Do not build the frontend. Not a line of React. Day 5.
- Do not implement the other 6 scoring criteria. Day 2.
- Do not build the research agent. Day 3.
- Do not set up CI/CD. Day 7.
- Do not deploy anywhere. Local only.
- Do not add Redis, Celery, or any queue. Use asyncio tasks if needed.
- Do not create user accounts or authentication.

Start by reading the four context files, then confirm you understand the scope, then build. Commit early and often. Let's go.
