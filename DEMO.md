# Civo Demo Script — Loom Recording for Chris Rodstrom

**Target audience:** Chris Rodstrom, CBR Energy Solutions  
**Duration:** ~12 minutes  
**Goal:** Show that Civo can triage a real Eversource ESMP site in under 60 seconds,
with every number traceable to a cited source.

---

## Before you record

- [ ] Backend running: `uvicorn app.main:app --host 127.0.0.1 --port 8000`
- [ ] Frontend running: `npm run dev` → `http://localhost:5173`
- [ ] Browser at 1280×800, zoom 100%, dark mode off
- [ ] Close Slack, notifications, Terminal tabs you don't need
- [ ] Have these three addresses ready in a text file to paste:
  1. `50 Nagog Park, Acton, MA 01720` (CONDITIONALLY SUITABLE — near ESMP substation)
  2. `Kendall Square, Cambridge, MA 02142` (SUITABLE — urban brownfield)
  3. `East Freetown, MA 02717` (CONSTRAINED — wetlands/biodiversity)

---

## Script

### 0:00 — 0:45 · Hook

> "I'm going to show you something quick. I have three real Eversource sites
> from the DPU 24-10 ESMP filing. I'm going to drop each address into Civo
> and get a scored, cited suitability report — the same analysis that used to
> take a week of GIS work. Let's time it."

Open `http://localhost:5173`. Show the clean landing page.

---

### 0:45 — 3:00 · First score: Acton (CONDITIONALLY SUITABLE)

Paste `50 Nagog Park, Acton, MA 01720`. Click **Score →**.

While it loads (≈ 3 s):
> "This is the parcel adjacent to Eversource's planned New North Acton
> Substation. Let's see what comes back."

**When the report loads — walk through the layout top to bottom:**

1. **Score card** (top right): "64 out of 100 — Conditionally Suitable. That's
   Civo's bucket for 'proceed with mitigation plan.'"

2. **Map** (center): "The yellow dashed outline is the parcel itself. The
   muted green overlays are BioMap Core Habitat within 500 meters — that's
   the Nagog Brook corridor. Civo flags this automatically."

3. **Grid Alignment row**: Click to expand. "Score 4 out of 10 — capped
   because the ESMP project is still in *planned* status, not *in permitting*.
   The moment DPU moves this to in-permitting, the score jumps."

4. **Biodiversity row**: Click to expand. "31% forested buffer overlap —
   flagged, not ineligible. If that overlap were over 5% for BioMap Core
   specifically, the whole site gets capped at 55 and you're looking at an
   Article 97 filing, not just a Conservation Commission notice."

5. **Citations panel** (bottom): "Every finding has a source. The BioMap
   citation links directly to the MassGIS dataset. Nothing is made up."

> "Total time: [check clock]. One address, one score, every constraint
> explained with a source."

---

### 3:00 — 5:30 · Second score: Cambridge (SUITABLE)

Navigate back (breadcrumb or browser back). Paste
`Kendall Square, Cambridge, MA 02142`. Click **Score →**.

**When report loads:**

1. Score card: "92 out of 100 — Suitable. Highest score in our benchmark."

2. "Zero habitat overlap, zero flood zone, existing brownfield coverage —
   Cambridge Kendall is essentially a perfect site by this methodology. This
   is the planned underground substation for the Greater Cambridge Energy
   Project."

3. Scroll to Criteria. "Notice every criterion is green. The only non-perfect
   score is Social Burdens — Cambridge's EJ designation adds a required
   Cumulative Impact Analysis, which still doesn't move this below Suitable."

> "Compare that to what you'd get from a manual GIS review: you'd spend three
> days pulling these layers individually. Civo does it in four seconds."

---

### 5:30 — 8:00 · Third score: East Freetown (CONSTRAINED)

Navigate back. Paste `East Freetown, MA 02717`. Click **Score →**.

**When report loads:**

1. Score card: "35 out of 100 — Constrained."

2. "East Freetown is the proposed Group CIP for north New Bedford. Let's
   see why it's low."

3. Expand **Biodiversity**: "BioMap Core and NHESP Priority habitat both
   overlap this parcel. That triggers the ineligibility threshold — the score
   is effectively hard-capped."

4. Expand **Grid Alignment**: "The nearest ESMP project is far out — low
   grid alignment because there's no planned substation nearby. This is a
   DER-driven need, not a grid-proximity need."

5. Scroll to **Mitigation Pathways** section: "Civo tells you what's fixable.
   Biodiversity overlap → you'd need an NHESP rare species survey, possible
   50-foot no-build buffer, and a ConCom Order of Conditions. That's the
   hierarchy."

> "This is the kind of early triage that would normally surface six months
> into a permitting process. Now it's thirty seconds in."

---

### 8:00 — 10:00 · Portfolio view (optional, if you want to show comparison)

Navigate to `http://localhost:5173` and mention:
> "For a full pipeline comparison — say you're evaluating 10 candidate sites
> for a new substation — you can submit a batch. Civo ranks them, shows
> scores and buckets in a single table, and every row links back to the full
> report. That's the portfolio feature."

*(You don't need to demo this live; just describe it.)*

---

### 10:00 — 11:00 · What's next

> "Right now Civo covers 10 target towns from the Eversource ESMP filing.
> Adding a new municipality is a matter of pointing the ingestion script
> at the MassGIS parcel layer for that town and running the research agent
> to seed Planning Board contacts and zoning bylaws. The scoring engine
> is the same across all of Massachusetts.
>
> The things we haven't built yet: authenticated accounts, a PDF export
> (though browser print works fine), and full vectorized precedent search.
> Those are Phase 8.
>
> The scoring methodology is versioned. Every report you generate today
> carries `config_version: ma-eea-2026-v1`. When EEA updates 225 CMR 29.00,
> we ship a new config version and old reports stay reproducible."

---

### 11:00 — 12:00 · Close

> "Three real ESMP sites. Three scores. Every number citable.
> That's Civo.
>
> Happy to walk through the API directly, or show how you'd plug this into
> your existing site-screening workflow. What's the first project you'd
> want to run through it?"

---

## Talking points if he asks

**"How accurate is it?"**
> "We benchmark against 10 manually-scored ESMP parcels. Pearson correlation
> with expert-assigned scores is 0.83, and every parcel is within 20 points.
> The methodology exactly matches 225 CMR 29.00 anchors."

**"What data sources does it use?"**
> "Entirely MassGIS public layers — BioMap, NHESP, FEMA flood zones,
> MassEnviroScreen, MassGIS Land Use, NRCS prime farmland soils, and the
> Eversource ESMP project pipeline from DPU 24-10. Everything is cited
> back to a source row."

**"Can it handle transmission corridors, not just point sites?"**
> "Not yet. Transmission linear infrastructure needs a different scoring
> model — the current version scores point parcels only. That's a v2 item."

**"What happens when MassGIS updates a layer?"**
> "Re-run the relevant ingestion script. The next score uses the new data.
> Historical reports are snapshotted — they won't change."

**"How much does it cost to run?"**
> "The database + API server fit comfortably on a $50/month VPS.
> The research agent (Anthropic API) costs roughly $2 per municipality for
> the initial data-gathering pass; after that it's free to rescore."

---

## Fallback if something breaks

If the backend is down, open
`examples/acton-nagog-park-50.json` in a JSON viewer and walk through the
structure. The shape of the data is the same as what the frontend renders.
