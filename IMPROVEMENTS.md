# UBID Platform — Improvements Roadmap

> **Read [HANDOFF.md](./HANDOFF.md) first** for the current state of the platform, metrics, file paths, and how to start the stack. This document is the prioritised list of *what to build next*.

---

## Snapshot of the platform when this roadmap was written

- **236 source records · 70 UBIDs · 1944 events joined** to UBIDs · 99 review-queue items
- **B3 F1 = 0.92 · pairwise F1 @ 0.95 = 0.95 · verdict accuracy = 0.82**
- 11 frontend pages, 5 admin sub-tabs, government-themed UI, retrain history + smart re-score wired
- Single host on Docker Compose with 9 services
- Codebase at `c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ubid_platform\`

Everything below is *additive* — nothing here breaks what already works.

---

## ⭐ Top-5 recommended order (≈ 4 hr total)

If you only do five things, do these:

1. **About / How-it-works page** (45 min) — biggest demo polish per minute spent
2. **Self-hosted Nominatim geocoding** (2 hr) — biggest model-quality lift
3. **5th adapter (BWSSB or Fire Safety)** (1 hr) — proves the pluggability claim
4. **Authentication (basic + roles)** (1.5 hr) — makes it feel like a real gov product
5. **One-click "Demo reset" button** (30 min) — for repeatable demos

---

## All improvements, grouped by purpose

### 🎯 Demo / hackathon polish (judge-facing)

#### 1. "About / How it works" page · ~45 min · ⭐ HIGHEST IMPACT
A new top-nav entry. Judges see the story before exploring.

**Build:**
- New page entry in `PAGES` list in `frontend/reviewer_console.py` (insert as second item after Dashboard)
- Visual SVG/HTML architecture diagram showing: 4 source CSVs → canonicalize → block → score (LightGBM) → cluster (union-find) → UBID → activity engine → verdict + reviewer console
- Pull live numbers from `/api/v1/query/stats` and `/api/v1/admin/calibration-report`
- Proposal-compliance checklist:
  - ✅ Wrong merge > missed merge (auto-link threshold 0.95)
  - ✅ Explainable decisions (SHAP per pair)
  - ✅ Reversible (Unmerge / Sorting Mat)
  - ✅ No hosted LLMs
  - ✅ Human-in-the-loop (Review Queue + Audit Merges)
  - ✅ No source-system changes (pull-based ingest)
- Glossary inline (UBID, B3, calibration, Brier, ECE, decay)
- 1-paragraph plain-English summary at the top

**Files:** `frontend/reviewer_console.py` only.

#### 2. One-click "Demo reset" button · ~30 min
For repeatable demos — wipe + re-ingest in one click.

**Build:** New button on Admin → Verdicts tab (or its own "Demo reset" sub-tab). Calls in sequence:
1. `POST /api/v1/events/admin/wipe-events`
2. Existing `scripts/wipe_data.py` logic exposed as a new admin endpoint
3. Re-ingest the 4 CSVs from `data/synthetic/`
4. Re-send events
5. Compute verdicts

**Files:** `src/ubid/api/routers/admin.py` (new endpoint), `frontend/reviewer_console.py` (button).

#### 3. Toast notifications + loading skeletons · ~30 min
Replace inline `st.success()` with toasts; replace "Loading..." with skeleton placeholders.

**Build:**
- Use [`st.toast`](https://docs.streamlit.io/library/api-reference/status/st.toast) instead of `st.success`/`st.warning` where appropriate
- For loading states, render greyed-out card placeholders before the API call returns

**Files:** `frontend/reviewer_console.py`.

#### 4. "Time travel" view · ~1 hr
For any UBID, show what it looked like at a past date.

**Build:**
- New endpoint `GET /api/v1/ubid/{ubid}/snapshot?as_of=YYYY-MM-DD` that walks the audit trail backward from today and reconstructs membership at the given date
- A date-picker on Activity Status that switches between "now" and "as-of" view
- Strong demo of the audit/reversibility story

**Files:** `src/ubid/api/routers/status.py`, `frontend/reviewer_console.py`.

#### 5. Comparison page "before vs after" · ~45 min
A page framing the platform's value proposition.

**Build:** Single page with two columns. Left: "Without UBID — 4 disconnected source systems, no join key, exemplar query impossible." Right: "With UBID — 1 platform, single join key, exemplar query returns N results." Pulls live numbers.

**Files:** `frontend/reviewer_console.py`.

---

### 🤖 Model quality (numbers go up)

#### 6. Self-hosted Nominatim geocoding · ~2 hr · ⭐
Adds lat/lng to canonical records → enables `addr_geo_distance_km` feature → significant recall lift.

**Build:**
- Add `nominatim` service to `docker-compose.yml` using `mediagis/nominatim:4.x`
- Bootstrap with India OSM extract from Geofabrik (download ~5GB; container takes ~15 min to import)
- New `src/ubid/canonicalize/geocoder.py` that calls `nominatim:8080/search?q=…` and writes lat/lng back to the canonical record
- Trigger geocoding asynchronously after canonicalization in `ingest.py`
- Re-score everything once populated

**Expected lift:** pairwise recall 0.84 → ~0.92, B3 F1 0.92 → ~0.95

**Files:** `docker-compose.yml`, new `src/ubid/canonicalize/geocoder.py`, modify `src/ubid/api/routers/ingest.py`. Need a background task or queue for async geocoding.

#### 7. Per-source feature weights · ~1 hr
BESCOM matches should weight address ↑ and name ↓ (because the consumer name is often the landlord).

**Build:**
- New per-source weight config in `data/dictionaries/source_weights.json`
- `src/ubid/scoring/lgbm_scorer.py` multiplies feature contributions by source-specific weights before final score
- Or: train per-source-pair sub-models (more complex but cleaner)

**Expected lift:** BESCOM-touching pair F1 ↑ ~5%

**Files:** new dict + scorer changes.

#### 8. Better active-learning queue ordering · ~45 min
Replace the heuristic priority with proper uncertainty sampling.

**Build:**
- In `src/ubid/review/queue.py` `compute_priority()`, replace the manual formula with binary entropy `H(p) = -p log p - (1-p) log(1-p)` where `p = calibrated_probability`
- Add cluster-impact term: priority *= log(1 + n_records_in_cluster) for the larger cluster involved
- Tune mix coefficients against reviewer-throughput synthetic test

**Expected effect:** reviewer effort produces more learning per decision

**Files:** `src/ubid/review/queue.py`.

#### 9. 4-gram name blocking · ~30 min
Currently trigram-based. 4-grams catch more variants.

**Build:**
- Modify the OpenSearch analyzer in `src/ubid/blocking/opensearch_blocker.py` to add a 4-gram filter alongside the existing trigram
- Lower `minimum_should_match` to 50% if precision is OK
- Re-index existing records (one-time)

**Files:** `src/ubid/blocking/opensearch_blocker.py`.

---

### 🏗 Production hardening

#### 10. Authentication (basic + roles) · ~1.5 hr · ⭐
Login screen, three roles: viewer / reviewer / admin. Pages hidden by role.

**Build:**
- Add `UserORM` table (username, password_hash, role, created_at)
- Implement basic auth middleware in FastAPI
- Streamlit login flow with `streamlit-authenticator` library, OR write a custom login state machine that asks for username/password at the top of `reviewer_console.py` before rendering anything
- Conditional page visibility:
  - viewer: Dashboard, Browse UBIDs, Lookup, Activity Status, Query
  - reviewer: above + Review Queue, Audit Merges, Reviewer Log
  - admin: all 11 pages
- Seed user `admin / admin` for first run

**Files:** `src/ubid/storage/postgres.py` (new ORM), new `src/ubid/api/routers/auth.py`, `frontend/reviewer_console.py` (login state).

#### 11. 5th adapter (BWSSB or Fire Safety) · ~1 hr · ⭐
Proves the architectural pluggability claim from the proposal.

**Build:**
- Add `BWSSB` (or `FIRE`) to `SourceSystem` enum in `src/ubid/schema/canonical.py`
- New `src/ubid/ingest/bwssb_adapter.py` extending `BaseAdapter` (similar to bescom_adapter.py — water connection number, consumer name, address, tariff)
- Register in `_ADAPTERS` dict in `src/ubid/api/routers/ingest.py`
- Generate a synthetic BWSSB CSV (~30 connections matching existing UBIDs) and add to `data/synthetic/`
- Add new event types if applicable (e.g. `bwssb_bill_paid`, `bwssb_disconnect`) to `src/ubid/schema/events.py` and signal weights to `src/ubid/activity/signal_catalog.py`

**Files:** schema/canonical.py, schema/events.py, new adapter file, ingest router, signal_catalog.py.

#### 12. Drift monitoring chart · ~1 hr
Show calibration ECE over time (we already have retrain history).

**Build:**
- Modify `/admin/retrain-history` chart to overlay calibration ECE
- Add `/admin/feature-distribution-history` endpoint that snapshots the mean of every feature daily
- Plot mean(name_jaro_winkler) over time, etc., to detect drift

**Files:** `src/ubid/api/routers/admin.py`, `frontend/reviewer_console.py`.

#### 13. Schema drift detection · ~1 hr
Validate every CSV ingest against the canonical schema; alert if columns change.

**Build:**
- In each adapter's `adapt_batch`, validate that every required column exists, log a warning if columns are added/removed
- Add a `schema_versions` table that records the column set seen per source per ingest
- Surface drift in the Quarantine page (or a new "Schema Health" tab)

**Files:** `src/ubid/ingest/base_adapter.py`, `src/ubid/api/routers/ingest.py`, new ORM.

#### 14. Real Kafka wiring · ~2 hr
Currently `/api/v1/events` bypasses Kafka. Wiring it through proves the stream architecture.

**Build:**
- Modify `/api/v1/events` to publish via `src/ubid/kafka/producer.py` instead of writing directly to DuckDB
- The Kafka consumer (`src/ubid/kafka/consumer.py`) is already wired to handle the topic — make sure it's running and consuming
- Verify events flow: HTTP POST → Kafka producer → Kafka topic → consumer → DuckDB
- Update HANDOFF.md to note that the worker container must be running

**Files:** `src/ubid/api/routers/events.py`, restart worker.

---

### 📊 Functional / Operational

#### 15. Bulk CSV import with progress bar · ~45 min
For thousands of records, show progress + ETA + cancel.

**Build:** Streamlit's file uploader returns the whole file at once, so:
- Read file, split into batches of 500
- For each batch, POST to `/api/v1/ingest/{source}` (batch endpoint, not upload)
- Update a `st.progress()` bar with `i/total`
- Show ETA based on time per batch

**Files:** `frontend/reviewer_console.py` (Ingest Data page).

#### 16. Webhook notifications · ~1 hr
"When verdict changes from active → closed, POST to URL X."

**Build:**
- New `webhook_subscriptions` table (id, event_type, target_url, secret)
- Hook into the verdict-recompute path: when a verdict changes, fire matching webhooks via httpx async POST with HMAC signature
- Admin UI to add/remove webhooks

**Files:** new ORM, modify `src/ubid/api/routers/status.py` `_persist_verdict()`, new webhook router.

#### 17. Sample-queries gallery · ~30 min
Pre-built queries on Query Explorer.

**Build:** Above the query form, a row of preset cards:
- "Active factories in pin 560058 with no inspection in last 18 months"
- "Dormant proprietorships in Bengaluru Urban"
- "Records with conflicting GSTINs"
- Each card is a button that pre-fills the form fields below

**Files:** `frontend/reviewer_console.py` (Query Explorer page).

#### 18. PDF export of UBID detail · ~45 min
"Download as PDF" on Activity Status.

**Build:**
- Use `weasyprint` or `reportlab` library
- Render the UBID detail (members, verdict, audit trail) as HTML, convert to PDF
- Stream as a download via `st.download_button`

**Files:** new `src/ubid/api/routers/export.py`, requirements.txt addition.

#### 19. Glossary / FAQ page · ~30 min
Plain-language definitions of every term: UBID, B3, calibration, Brier, ECE, decay, must-link, cannot-link, etc.

**Build:** New page entry. Static markdown content with collapsible sections per term.

**Files:** `frontend/reviewer_console.py`.

#### 20. Keyboard shortcuts · ~30 min
`j`/`k` to navigate review queue, `y`/`n` for confirm/reject, `Ctrl+/` to show shortcut help.

**Build:** Streamlit doesn't natively support keyboard shortcuts — need to inject JavaScript via `st.components.v1.html()` that listens for keypress and triggers buttons by their key.

**Files:** `frontend/reviewer_console.py`.

---

## 🤔 Things to NOT do (low ROI for hackathon)

- **Mobile-friendly mode** — government back-office tool, desktop-only is fine
- **Dark mode** — saffron + navy theme IS the brand
- **Multi-language (Kannada) UI** — high effort, no judge impact
- **Print-friendly pages** — niche
- **CDC connectors per department** — production-only, not demoable
- **Online incremental learning** — overkill, retrain history already shows the loop
- **Grafana / Prometheus** — judges won't see it
- **mkdocs documentation site** — README + HANDOFF.md is enough
- **GitHub Actions CI** — single-developer hackathon, not needed
- **Mypy / type checking** — code is already typed

---

## ✅ How to pick up this list as a future Claude

1. Read `HANDOFF.md` to understand the current state, file paths, and how to start the stack.
2. Run `docker compose up -d` from `ubid-platform/ubid_platform/` and wait for `UBID Platform API ready.`
3. Hard-refresh `http://localhost:8501` in the browser.
4. Pick an item from above. Update todos with `TodoWrite`.
5. After implementing, **append a "Done" subsection to HANDOFF.md** with what changed, why, and where.
6. Move the item from this file to a "Completed" section at the bottom.

---

## ✏️ Completed items

### ✅ #11 — 5th adapter (BWSSB / water supply) (May 2026)

End-to-end proof of the proposal's pluggability claim. Added BWSSB through the entire stack with **zero changes** to the scoring, clustering, blocking, verdict, or reviewer code paths.

**Files created / modified:**
- `src/ubid/schema/canonical.py` — `BWSSB = "bwssb"` enum value
- `src/ubid/schema/events.py` — 5 new event types
- `src/ubid/activity/signal_catalog.py` — 5 new signal configs (slightly lower weight than BESCOM)
- `src/ubid/ingest/bwssb_adapter.py` — new adapter (114 lines, modelled on BESCOM)
- `src/ubid/api/routers/ingest.py` — registered BWSSBAdapter in `_ADAPTERS`
- `data/synthetic/bwssb_records.csv` — 31 connections sampled from existing addresses
- `data/synthetic/bwssb_events.jsonl` — 767 events (Jan 2024 → Apr 2025)
- `scripts/gen_bwssb_data.py` — regenerates the synthetic data deterministically

**Bug fixed along the way:** UBID merge in inline-clustering deleted ubid_nodes without first deleting their dependent activity_verdicts rows → FK violation. One-line fix in `ingest.py`.

**Live numbers:** 31 records ingested, 28 auto-linked to existing UBIDs by address, 3 created new UBIDs. 643/767 events joined.

### ✅ #6 — Nominatim geocoding fully live (May 2026)

Earlier session wired the infrastructure (dict + Nominatim fallback). This session:
- Operator dropped the 126MB Karnataka OSM extract into `nominatim_data/`.
- Uncommented the Nominatim service in `docker-compose.yml`.
- Added `NOMINATIM_URL=http://nominatim:8080` to `.env`.
- Recreated `ubid-api` with the new env var.
- Nominatim imported the OSM data in ~10 minutes.
- Reversed the geocoder priority so Nominatim runs first (most precise) and the dict is fallback.
- Added a Karnataka-bbox sanity check to reject garbage Nominatim results.
- New `scripts/regeocode_with_nominatim.py` re-geocoded all 267 records.

**Limitation honestly noted:** synthetic addresses have made-up plot numbers ("Site No. 112/A", "Plot 87") that Nominatim can't pinpoint, so only 19/267 records got Nominatim-precision coords. The other 240 fell back to the curated dict. Real Karnataka business addresses would do significantly better — expect ≥70% Nominatim hit rate in production.

### ✅ #6 — Self-hosted Nominatim geocoding infrastructure (May 2026)

Wired the full geocoding pipeline. Three layers:
1. **Hand-curated locality dict** — 42 Bengaluru/Karnataka localities + 24 pin codes + 19 districts at `data/dictionaries/locality_coordinates.json`. Sub-ms lookup.
2. **`src/ubid/canonicalize/geocoder.py`** — `geocode(record)` tries dict → Nominatim if configured.
3. **Nominatim service** — commented-out entry in `docker-compose.yml` with full enable instructions in the comment block.

Hooked into ingest so new records get coords. Backfill script populated 200/208 (96.2%) of existing records.

**Honest result:** No measurable metric lift from the dict-based path because every record in the same locality gets the same centroid → the geo-distance feature is redundant with `addr_locality_match`. Guard added in `features.py`: identical-coord pairs → MISSING, so the feature only fires for cross-locality pairs.

**To get the real lift:** operator drops in a Karnataka OSM extract (~250 MB), uncomments the Nominatim service, and runs the backfill again. The pipeline is 100% ready for that switch.

**Files modified/added:**
- `data/dictionaries/locality_coordinates.json` (new)
- `src/ubid/canonicalize/geocoder.py` (new)
- `src/ubid/api/routers/ingest.py` (geocode_and_attach call before persist)
- `src/ubid/scoring/features.py` (identical-coord guard)
- `scripts/backfill_geocoding.py` (new)
- `docker-compose.yml` (Nominatim entry, commented)

### ✅ #1 — About / How-it-works page (May 2026)

Built. Sits as the first entry in the top-nav (`ℹ️ About`). Sections:
- **Hero** — 1-paragraph plain-English summary of what the platform does
- **Live metric strip** — 8 cards pulled from `/query/stats`, `/admin/calibration-report`, `/admin/retrain-history`, `/admin/labels-since-last-retrain`
- **Architecture diagram** — pure HTML/CSS flow showing 4 source CSVs → canonicalise → block → score → cluster → UBID → activity engine + reviewer console
- **Proposal-compliance checklist** — 10 ✅ items with brief justifications, ECE pulled live
- **Glossary** — 12 terms in collapsible expanders (UBID, PAN, GSTIN, Brier, ECE, B3, decay, must-link, cannot-link, etc.)
- **Tech stack** — 9 cards, navy for infra, saffron for ML/UI

**Files modified:** `frontend/reviewer_console.py` (only).

**Why this first:** It's what a judge sees on first click — sets the framing for everything else they explore.
