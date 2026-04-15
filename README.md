# Civo — Massachusetts Permitting Intelligence

Civo scores energy-infrastructure sites against the Massachusetts EEA Site
Suitability methodology (225 CMR 29.00). Every number on every report traces
to a real cited source row. Nothing is fabricated.

**Target user:** Energy developers, utilities, and permitting consultants who
need to triage site suitability before committing to a full Environmental
Impact Report (EIR) or EFSB filing.

---

## What it does

1. Accepts a Massachusetts address.
2. Resolves it to a MassGIS parcel via the Google Places API → PostGIS
   ST_Contains → nearest-parcel fallback (2 km cap) → ESMP-anchored fallback.
3. Scores the parcel across seven criteria derived from 225 CMR 29.00:

| # | Criterion | Weight |
|---|-----------|--------|
| 1 | Development Potential / Grid Alignment | 20% |
| 2 | Climate Resilience (FEMA flood zones) | 15% |
| 3 | Carbon Storage (forested cover proxy) | 15% |
| 4 | Biodiversity (BioMap / NHESP overlap) | 20% |
| 5 | Social & Environmental Burdens (MassEnviroScreen) | 15% |
| 6 | Social & Environmental Benefits (brownfield cover) | 5% |
| 7 | Agricultural Production (prime farmland soils) | 10% |

4. Returns a `SuitabilityReport` JSON with per-criterion scores, findings,
   and source citations. Saves to `score_history` for retrieval by ID.
5. Frontend renders a printable report at `/report/<id>`.

---

## Quick start

### Prerequisites

- Docker Desktop (≥ 4.28, with 12 GB RAM + 4 GB swap allocated)
- Python 3.11+
- Node 20+
- A Google Places API key (for geocoding)
- An Anthropic API key (for the research agent — optional for scoring)

### 1. Start the database

```bash
cd v2
docker compose up -d
```

Postgres 16 + PostGIS 3.4 + pgvector 0.8.2 will be available on
`localhost:5432`.

### 2. Run migrations

```bash
cd backend
python -m alembic upgrade head
```

### 3. Ingest spatial data (first run only)

```bash
# MA parcels — 10 target towns, ~206k parcels (~8 min)
python ingest/parcels.py

# ESMP project pipeline
python ingest/esmp.py

# Habitat layers (BioMap, NHESP, wetlands)
python ingest/habitat.py

# FEMA flood zones
python ingest/flood_zones.py

# MassGIS land use (filtered to scoring cover codes)
python ingest/land_use.py

# Prime / statewide-importance farmland soils
python ingest/prime_farmland.py

# MassEnviroScreen cumulative burden index
python ingest/massenviroscreen.py

# Article 97 protected lands
python ingest/article97.py
```

### 4. Configure environment variables

```bash
cp .env.example .env   # edit GOOGLE_PLACES_API_KEY and ANTHROPIC_API_KEY
```

### 5. Start the backend

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`GET /health` should return `{"status":"ok", ...}`.

### 6. Start the frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Enter a Massachusetts address and click **Score →**.

---

## Project structure

```
v2/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes (score.py, portfolio.py)
│   │   ├── scoring/      # Engine, resolver, Pydantic models
│   │   └── main.py       # App factory, router mounts
│   ├── agent/            # Research agent (Claude Sonnet + tool use)
│   ├── alembic/          # DB migrations
│   ├── config/scoring/   # Versioned scoring config YAML
│   ├── ingest/           # MassGIS ingestion scripts
│   ├── scripts/          # One-off utility scripts
│   └── tests/            # pytest suite (51 tests)
├── config/
│   └── scoring/
│       └── ma-eea-2026-v1.yaml   # Anchors, weights, caps
├── docs/
│   ├── benchmark.yaml            # 10-parcel validation ground truth
│   └── references/               # Design reference artifacts
├── examples/                     # Pre-scored JSON for all 10 benchmark parcels
└── frontend/
    └── src/
        ├── routes/               # Landing, Report, Portfolio pages
        ├── components/           # MapView (MapLibre)
        └── lib/api.ts            # Typed fetch wrappers
```

---

## Running tests

```bash
cd backend

# Fast suite — no DB required for most tests
pytest tests/ --ignore=tests/test_benchmark.py

# Full benchmark — requires populated DB (takes ~3 min)
pytest tests/test_benchmark.py -v -s
```

Current benchmark results (Pearson r = **0.834**, all within ±20 points):

| Parcel | Expected | Computed | Δ |
|--------|----------|----------|---|
| acton-nagog-park-50 | 65 | 64.1 | −0.9 |
| boston-east-eagle-sub | 72 | 67.2 | −4.8 |
| cambridge-kendall-8025 | 78 | 92.5 | +14.5 |
| burlington-winn-st | 52 | 71.2 | +19.2 |
| natick-saxonville-sub | 48 | 62.5 | +14.5 |
| falmouth-tap-substation | 42 | 55.0 | +13.0 |
| east-freetown-cip | 35 | 35.4 | +0.4 |
| worthington-new-sub | 38 | 39.5 | +1.5 |
| whately-deerfield-cip | 40 | 47.0 | +7.0 |
| boston-seaport-brownfield | 82 | 70.2 | −11.8 |

---

## Adding a new municipality

1. **Add the town to the target list** in `ingest/parcels.py` (the
   `TARGET_TOWNS` dict — MassGIS town ID and FIPS code).
2. **Re-run the ingestion scripts** that are filtered by town:
   `parcels.py`, `habitat.py` (if scoped), `land_use.py`.
   Statewide layers (flood zones, farmland, BioMap) cover all of MA and do
   not need to be re-run.
3. **Seed municipality metadata** (ConCom contact, bylaws URL, etc.) via the
   research agent:
   ```bash
   python agent/research.py --town "Town Name, MA"
   ```
4. **Add benchmark parcels** to `docs/benchmark.yaml` and run
   `pytest tests/test_benchmark.py` to verify the new town scores correctly.

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/score` | Score a single address |
| POST | `/score/batch` | Score up to 50 addresses concurrently |
| GET | `/report/{id}` | Retrieve a persisted report |
| GET | `/parcel/{loc_id}/geojson` | Parcel polygon in WGS84 |
| GET | `/parcel/{loc_id}/overlays` | All overlay features within a buffer |
| GET | `/parcel/{loc_id}/precedents` | Recent ConCom/Planning decisions |
| POST | `/portfolio` | Score N addresses; persist ranked results |
| GET | `/portfolio/{id}` | Retrieve a portfolio |
| DELETE | `/portfolio/{id}` | Delete a portfolio |
| GET | `/health` | Liveness + DB connectivity check |

Full OpenAPI schema at `http://localhost:8000/docs`.

---

## What is NOT implemented yet

| Gap | Priority | Notes |
|-----|----------|-------|
| Research agent for 9 remaining towns | High | Acton only; ~$22 at current token usage |
| Token-efficient research agent | Medium | Documented in Phase 5 commit: history pruning, prompt caching |
| DCR Top-20% carbon forest layer | Medium | Currently proxied by forested cover fraction |
| Real-time ESMP coordinate updates | Medium | Hand-curated overrides in `scripts/refine_esmp_locations.py` |
| Authentication / multi-tenant | Low | All endpoints are anonymous (MVP) |
| PDF export | Low | Report page can be printed from browser |
| Precedent retrieval in scoring engine | Low | Available via `/parcel/{id}/precedents` but not in score |
| Vectorized precedent search (pgvector) | Low | Schema ready; filtering is town-based only |
| EFSB docket integration | Low | Would enable real-outcome validation |

---

## Methodology notes

Scores are computed under **225 CMR 29.00** (MA Clean Energy and Climate Plan
for 2025 and 2030, EEA Site Suitability Regulations). The config YAML at
`config/scoring/ma-eea-2026-v1.yaml` version-controls all anchors, weights,
and ineligibility thresholds. Every report carries its `config_version` field
so historical scores remain reproducible.

Ineligibility triggers (score capped at 55/100):
- BioMap Core Habitat overlap ≥ 5% of parcel area
- NHESP Priority Habitat overlap ≥ 5% of parcel area

---

## License

Private / proprietary. All rights reserved. Not for redistribution.
