# Civo — Massachusetts Permitting Intelligence

Civo scores energy-infrastructure sites against the Massachusetts EEA Site
Suitability methodology (**225 CMR 29.00**) and surfaces the municipal
permitting landscape around them. Every number on every report traces back to
a cited source row. Nothing is fabricated.

**Target user:** Energy developers, utilities, and MA permitting consultants
who need to triage candidate sites **before** committing to a full
Environmental Impact Report (EIR) or EFSB filing.

---

## What it does

```
┌──────────────────┐   ┌───────────────────┐   ┌──────────────────────┐
│  Typed address   │ → │  Parcel resolver  │ → │  Scoring engine      │
│                  │   │  (transparent)    │   │  7 criteria / 100    │
└──────────────────┘   └───────────────────┘   └──────────┬───────────┘
                                                          │
                       ┌──────────────────────────────────┴──────┐
                       ▼                                         ▼
           ┌───────────────────────┐             ┌───────────────────────┐
           │  Report page          │             │  Municipality page    │
           │  • per-criterion math │             │  • bylaws by project  │
           │  • findings           │             │  • DOER alignment     │
           │  • precedents         │             │  • permit contacts    │
           │  • mitigation $       │             │  • moratoriums        │
           │  • moratorium flag    │             │                       │
           └───────────────────────┘             └───────────────────────┘
```

1. User enters a Massachusetts address and a project type.
2. The **resolver** geocodes via Google Places, reprojects to EPSG:26986,
   then attempts (in order): `ST_Contains` on a parcel polygon → a
   narrow 500 m ESMP anchor (only for substation/transmission projects) →
   a 500 m nearest-parcel fallback. Returns full provenance so the UI can
   show *exactly* what was scored vs. what the user typed.
3. The **scoring engine** rates the parcel across seven weighted criteria
   derived from 225 CMR 29.00:

| # | Criterion | Weight |
|---|-----------|--------|
| 1 | Development Potential / Grid Alignment | 20% |
| 2 | Climate Resilience (FEMA flood zones) | 15% |
| 3 | Carbon Storage (forested cover proxy) | 15% |
| 4 | Biodiversity (BioMap / NHESP overlap) | 20% |
| 5 | Social & Environmental Burdens (MassEnviroScreen) | 15% |
| 6 | Social & Environmental Benefits (brownfield cover) | 5% |
| 7 | Agricultural Production (prime farmland soils) | 10% |

4. Output is a `SuitabilityReport` JSON with per-criterion scores,
   findings, and cited sources. Every report is persisted to
   `score_history` and retrievable by ID.
5. The frontend renders a printable report at `/report/<id>`, plus a
   municipality detail view, a portfolio batch-scoring view, and a
   DOER Model Bylaw alignment strip for each town.

---

## Supported project types

Eight categories, each with its own bylaw set and scoring knobs:

```
solar_ground_mount · solar_rooftop  · solar_canopy
bess_standalone    · bess_colocated
substation         · transmission
wind               · ev_charging
```

---

## Quick start

### Prerequisites

- Docker Desktop (≥ 4.28, with 12 GB RAM + 4 GB swap allocated)
- Python 3.11+
- Node 20+
- A **Google Places API key** (geocoding)
- An **Anthropic API key** (research agent — optional for scoring)

### 1. Start Postgres + PostGIS + pgvector

```bash
cd v2
docker compose up -d
```

The image is built from `db/` and bundles Postgres 16 + PostGIS 3.4 +
pgvector 0.8.2. Available on `localhost:5432` as `civo/civo/civo`.

### 2. Install backend + run migrations

```bash
cd backend
pip install -e '.[dev]'          # or: uv pip install -e '.[dev]'
alembic upgrade head             # applies 0001 → 0007
```

### 3. Ingest spatial data (first run only)

Each script is idempotent; re-running only updates changed rows. Full run
is ~15 min on an M1 laptop.

```bash
python -m ingest.l3_parcels          # MA parcels — ~206k rows for 10 target towns
python -m ingest.esmp_projects       # ESMP transmission / substation pipeline
python -m ingest.biomap              # BioMap Core + Critical habitat
python -m ingest.nhesp               # NHESP Priority + Estimated habitat
python -m ingest.wetlands            # MassDEP wetlands
python -m ingest.fema_flood          # FEMA NFHL flood zones
python -m ingest.land_use            # MassGIS 2016 land use (scoring cover codes)
python -m ingest.prime_farmland      # USDA SSURGO prime / statewide-importance
python -m ingest.massenviroscreen    # MA EJ cumulative burden index
```

### 4. Configure environment

```bash
cp .env.example .env    # fill in GOOGLE_PLACES_API_KEY + ANTHROPIC_API_KEY
```

### 5. Start the backend

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`GET /health` returns `{"status":"ok", ...}` when the DB is reachable and
both PostGIS + pgvector extensions are present.

### 6. Start the frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Pick a project type, enter a MA address,
click **Score →**.

---

## Frontend routes

| Path | Purpose |
|------|---------|
| `/` | Overview — portfolio + recent-activity dashboard |
| `/lookup` | Single-address scoring entry point |
| `/suitability` | Full-map site suitability explorer |
| `/municipalities` | Searchable list of seeded towns |
| `/municipalities/:townId` | Town detail — bylaws by project type, DOER alignment, contacts |
| `/report/:reportId` | Scored report with map, criteria, precedents, mitigation costs |
| `/portfolio/:portfolioId` | Ranked multi-site comparison |

---

## API reference

### Scoring
| Method | Path | Description |
|--------|------|-------------|
| POST | `/score` | Score a single address; persists to `score_history` |
| POST | `/score/batch` | Score ≤ 50 addresses concurrently |
| GET | `/report/{id}` | Retrieve a persisted report (enriched with live link-health) |

### Parcel-level reads
| Method | Path | Description |
|--------|------|-------------|
| GET | `/parcel/{loc_id}/geojson` | Parcel polygon in WGS84 |
| GET | `/parcel/{loc_id}/overlays` | Habitat / flood / land-use overlays within a buffer |
| GET | `/parcel/{loc_id}/precedents` | Recent ConCom / Planning decisions in the town |
| GET | `/parcel/{loc_id}/mitigation-costs` | Line-item mitigation $ estimate (benchmarks + precedents + HCA) |
| GET | `/parcel/{loc_id}/moratoriums` | Active moratoriums in the parcel's town, keyed by project type |

### Municipality + bylaws
| Method | Path | Description |
|--------|------|-------------|
| GET | `/municipalities` | All seeded towns |
| GET | `/municipality/{town_id}` | Full town record (contacts, bylaws, moratoriums) |
| GET | `/municipality/{town_id}/bylaws/{project_type}` | Per-project-type bylaw block |

### DOER Model Bylaw alignment
| Method | Path | Description |
|--------|------|-------------|
| GET | `/towns/{town_id}/doer-status` | Adoption status + per-section deviation vs. DOER model |
| POST | `/exemption-check` | Determine whether a project meets MGL c.40A §3 exemption criteria |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| POST | `/portfolio` | Score N addresses and persist a ranked portfolio |
| GET | `/portfolio/{id}` | Retrieve a portfolio |
| DELETE | `/portfolio/{id}` | Delete a portfolio |

### Ops
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | DB + PostGIS + pgvector + row-count liveness |

Full OpenAPI schema at <http://localhost:8000/docs>.

---

## Project structure

```
v2/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers
│   │   │   ├── score.py          # /score, /report, /parcel/*
│   │   │   ├── portfolio.py      # /portfolio
│   │   │   ├── municipality.py   # /municipalities, /bylaws
│   │   │   └── doer.py           # DOER alignment + exemption check
│   │   ├── scoring/          # Engine, resolver, pydantic models, config loader
│   │   ├── services/         # mitigation_costs, doer_comparison,
│   │   │                     # exemption_checker, link_health
│   │   ├── db.py             # SQLAlchemy engine + session
│   │   └── main.py           # App factory, router mounts, /health
│   ├── agent/                # Research agent (Claude + tool use) for town metadata
│   ├── alembic/              # Schema migrations (0001 → 0007)
│   ├── ingest/               # MassGIS / FEMA / SSURGO ingestion scripts
│   ├── scripts/              # Ad-hoc utilities (ESMP coord refinement, etc.)
│   ├── tests/                # pytest suite (scoring, API, ingestion, benchmark)
│   └── pyproject.toml
├── config/
│   └── scoring/
│       └── ma-eea-2026-v1.yaml   # Versioned anchors, weights, ineligibility
├── data/                         # Cached geocodes + raw MassGIS pulls (gitignored)
├── db/                           # Dockerfile for PostGIS + pgvector image
├── docs/                         # benchmark.yaml + architecture references
├── examples/                     # Pre-scored JSON for all 10 benchmark parcels
├── frontend/
│   ├── src/
│   │   ├── routes/               # Overview, AddressLookup, Municipalities,
│   │   │                         # SiteSuitability, Report, Portfolio
│   │   ├── components/           # Sidebar, TopBar, MapView, CriterionRow,
│   │   │                         # DoerAlignmentStrip, ExemptionChip,
│   │   │                         # PermittingPanel, StatusPill, Icon
│   │   └── lib/api.ts            # Typed fetch wrappers
│   └── scripts/walkthrough.mjs   # Puppeteer demo-capture script
├── docker-compose.yml
├── DEMO.md
└── README.md (you are here)
```

---

## Running tests

```bash
cd backend

# Fast suite — no DB required
pytest tests/ --ignore=tests/test_benchmark.py

# Full benchmark — requires fully-populated DB (~3 min)
pytest tests/test_benchmark.py -v -s
```

Current benchmark results (Pearson r = **0.834**, all within ±20 points of
the expert-annotated target score):

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

## Capturing a walkthrough (for demos)

```bash
# With backend on :8000 and frontend on :5173
cd frontend
node scripts/walkthrough.mjs
```

Screenshots land in `frontend/scripts/walkthrough/` (gitignored). Eleven
steps: overview → lookup → report → criterion expand → mitigation panel →
municipality index → DOER drawer → site suitability.

---

## Adding a new municipality

1. **Register the town** in `ingest/l3_parcels.py` (`TARGET_TOWNS` — name
   plus MassGIS muni ID).
2. **Re-run town-scoped ingestion:** `l3_parcels.py`, `land_use.py`, and
   `biomap.py`/`nhesp.py` if they are scoped. Statewide layers (FEMA,
   SSURGO, MassEnviroScreen) do not need re-running.
3. **Seed municipality metadata** via the research agent:
   ```bash
   python -m agent.research --town "Town Name, MA"
   ```
   This writes `municipalities.{contacts, bylaws, project_type_bylaws,
   moratoriums, doer_adoption}` and any precedent rows it can find.
4. **Add benchmark parcels** to `docs/benchmark.yaml` and run
   `pytest tests/test_benchmark.py` to confirm the new town stays within
   tolerance.

---

## Methodology notes

Scores are computed under **225 CMR 29.00** (MA Clean Energy and Climate
Plan for 2025 and 2030, EEA Site Suitability Regulations). The config YAML
at `config/scoring/ma-eea-2026-v1.yaml` version-controls every anchor,
weight, and ineligibility threshold. Every persisted report carries its
`config_version` so historical scores remain reproducible when the config
is revised.

**Ineligibility triggers** cap the final score at 55/100:
- BioMap Core Habitat overlap ≥ 5% of parcel area
- NHESP Priority Habitat overlap ≥ 5% of parcel area

**Resolver transparency.** If the typed address doesn't sit inside a
parcel polygon, the `SuitabilityReport.resolution` block records how we
snapped (`esmp_anchored` vs `nearest`), the original query, the resolved
parcel's site address + town, and the straight-line distance from the
geocoded point. The frontend surfaces this as a banner above the report —
consultants see exactly what was scored vs. what they asked for, or the
call fails loudly if no parcel is within 500 m.

**Mitigation cost estimates.** The `/parcel/{id}/mitigation-costs`
endpoint blends industry benchmarks (vegetative screening, earthwork,
wetland replication, decommissioning surety, stormwater treatment, HCA
payments) with observed conditions on prior precedents in the same town.
Output is a line-item range the developer can drop into an ROI model.

**Link-health enrichment.** Every citation on every report is checked at
render time via the `link_health` service; dead originals fall back to an
archived version with a visible "archived" badge.

---

## What is NOT implemented yet

| Gap | Priority | Notes |
|-----|----------|-------|
| Research agent for remaining ESMP towns | High | ~$22/town at current token usage |
| Token-efficient research agent | Medium | History pruning + prompt caching |
| DCR Top-20% carbon forest layer | Medium | Currently proxied by forested cover fraction |
| PDF export (server-side) | Low | Report page uses `window.print()` — works but not branded |
| Authentication / multi-tenant | Low | All endpoints anonymous (MVP) |
| Precedent retrieval inside scoring | Low | Available via `/precedents` but not folded into the score |
| Vectorized precedent search (pgvector) | Low | Schema ready; filtering is town-based for now |
| EFSB docket integration | Low | Would enable real-outcome validation |

See `civo_docs/ROADMAP.md` for the full week-by-week plan.

---

## License

Private / proprietary. All rights reserved. Not for redistribution.
