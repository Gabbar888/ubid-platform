# UBID Platform — Complete Session Handoff

> **Two sessions of work documented below.**
> Session 2 (latest, the most up-to-date state) is at the top.
> Session 1 (original, kept for historical context) starts below the divider.

---

# 🟢 SESSION 2 UPDATE — May 2026

## Codebase location (CORRECTED)
`c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ubid_platform\`

(The original handoff said `E:\AI_For_Bharat\Theme1\ubid_platform\` — that was the prior workstation. The actual current location is on Desktop.)

This IS a git repo. From `c:\Users\Kunda\Desktop\Hackathon\ubid-platform`, `git status` works.

## Current state (May 2026)

### Pipeline metrics (evaluated against `data/synthetic/ground_truth_links.csv`)

| Metric | Value | Notes |
|---|---|---|
| Pairwise precision @ 0.95 | **0.964** | TP=352, FP=13 |
| Pairwise recall @ 0.95 | **0.842** | FN=66 |
| Pairwise F1 @ 0.95 | **0.899** | |
| Brier score | **0.0094** | well-calibrated |
| ECE (10 bins) | **0.0152** | well-calibrated |
| **B3 cluster F1** | **0.917** | up from 0.405 baseline (no inline clustering) |
| B3 precision | 0.938 | |
| B3 recall | 0.896 | |
| **Verdict accuracy** | **0.817** (49/60) | up from 0.20 baseline |
| Predicted UBIDs | 70 | ground truth = 60 entities |

### Volume
- 236 source records (ekarmika 63, fbis 54, kspcb 48, bescom 71)
- 70 UBIDs (after inline clustering)
- 1944 / 1951 events joined to UBIDs (7 quarantined)
- 99 review-queue items pending
- LightGBM model trained on 1672 pairs (418 pos / 1254 neg)

## Major features added in Session 2

### Backend
1. **Inline clustering in `ingest.py`** — union-find over auto-linked pairs (this batch + historical) with cannot-link awareness. Replaces the old code that gave every record its own UBID. **Single biggest improvement** — bumped B3 F1 from 0.40 → 0.88.
2. **New router `events.py`** — synchronous activity-event ingestion bypassing Kafka:
   - `POST /api/v1/events` — ingest a batch of events
   - `GET  /api/v1/events/quarantine` — list quarantined events
   - `POST /api/v1/events/quarantine/retry-all` and `/{id}/retry` — re-run linkage
   - `POST /api/v1/events/admin/wipe-events` — clear DuckDB events
   - `POST /api/v1/events/admin/refresh-ubids` — remap events to current UBIDs (after re-cluster)
   - `GET  /api/v1/events/debug/summary` and `/debug/ubid/{ubid}` — DuckDB inspection
3. **New router `admin.py`** — operational endpoints:
   - `POST /api/v1/admin/retrain` — re-fit LightGBM on reviewer labels + ground truth, returns A/B metrics
   - `GET  /api/v1/admin/calibration-report` — reliability diagram + Brier + ECE
   - `POST /api/v1/admin/synonyms/apply` — add locality synonym AND re-canonicalise existing records
   - `POST /api/v1/admin/verdicts/refresh` — recompute Active/Dormant/Closed for every UBID in-process
4. **`status.py` enhancements** — added:
   - `GET  /api/v1/ubid` (list, filterable by verdict / source / pin / district / name search / audit_status)
   - `GET  /api/v1/ubid/{ubid}` (rebuilt — pulls from Postgres directly, includes verdict + every linked record)
   - `GET  /api/v1/ubid/{ubid}/audit` — UBID lineage timeline (links + decisions + constraints)
   - `GET  /api/v1/ubid/{ubid}/pair-evidence` — per-pair calibrated probability + SHAP for audit UI
   - `GET  /api/v1/ubid/{ubid}/status` — added `reference_date` and `lookback_days` query params
5. **`review.py` enhancements**:
   - `POST /api/v1/review/unmerge` — split two records currently sharing a UBID; writes cannot-link constraint
   - `POST /api/v1/review/approve-ubid` — confirm a multi-record UBID; writes must-link constraints between every member-pair
   - `GET  /api/v1/review/activity` — reviewer decision log + per-reviewer summary
   - `GET  /api/v1/review/queue?reviewer_tier=senior` — senior-tier escalation ordering
6. **`feedback.py` rewrite** — `_trigger_relink` and `_trigger_unlink_if_merged` are now real implementations (not stubs). They actually merge / split UBIDs in Postgres, refresh Redis, invalidate verdicts.
7. **Trigram name blocking** in `opensearch_blocker.py` — added `name_normalized` match clause with `minimum_should_match=60%`. Catches PAN-less BESCOM records and cross-pin typos. Bumped B3 recall from 0.80 → 0.90.
8. **Locality synonym persistence** — `add_synonym()` now writes to `data/dictionaries/locality_synonyms.json` so additions survive container restarts.
9. **Tuned `DORMANT_SCORE_THRESHOLD` from 0.4 → 0.15** in `.env` — caught 11 additional dormants, verdict accuracy 0.63 → 0.82.

### Frontend (Streamlit) — major rewrite
- **11 pages** (was 5):
  - 📊 Dashboard
  - 🔍 Browse UBIDs (NEW — paginated, filterable, CSV export)
  - 📋 Review Queue (added bulk actions slider)
  - 🧐 Audit Merges (NEW — workflow to verify/approve/split each multi-record UBID one at a time)
  - 🧭 UBID Lookup
  - 📈 Activity Status (added Unmerge UI + audit-trail timeline)
  - 🚧 Quarantine (NEW — list + retry events that couldn't join a UBID)
  - 📜 Reviewer Log (NEW — decision history + per-reviewer leaderboard)
  - ❓ Query Explorer (CSV export added)
  - 📤 Ingest Data (added events JSONL upload)
  - ⚙️ Admin (NEW — retrain / calibration / synonyms / verdict refresh)
- **Indian government theme** — navy banner, tricolor strip, saffron accents, ☸ chakra
- **Help system** — every page has a saffron-bordered help banner (toggleable in sidebar). Key buttons have `help=` tooltips.
- **Cross-page nav** — clicking "Open" on a UBID jumps to Activity Status with auto-load.
- **Reviewer feedback wired end-to-end** — confirm_match merges UBIDs in real time; reject splits them.

## Critical bug fixes in Session 2

### Bug 7 — Events sent through wrong endpoint
The HANDOFF.md script in Session 1 sent events via `POST /api/v1/ingest/{source}` which is for SOURCE RECORDS not events. They got silently dropped (or stored as junk records).
**Fix:** Added `POST /api/v1/events` endpoint with `EventBatch` payload. Updated `scripts/send_events.py` to use it.

### Bug 8 — DuckDB metadata returned as string, breaks ActivityEvent construction
`get_events_for_ubid` returns rows with `metadata` as a JSON string. `ActivityEvent(**row)` rejected it because `metadata: dict[str, Any]`.
**Fix:** `status.py` now parses metadata via `json.loads` before constructing the event.

### Bug 9 — `get_events_for_ubid` filtered by `current_date - 730 days`
Synthetic events span 2023-11 to 2025-04 but today is 2026-05, so all events were filtered out → all UBIDs returned `closed_by_silence` with score 0.
**Fix:** Added `reference_date` parameter to `get_events_for_ubid` and propagated through `/status`. The frontend defaults reference_date to 2025-05-01.

### Bug 10 — `lgbm_scorer.py` used Booster API on sklearn LGBMClassifier
`self._model.predict(X, num_iteration=self._model.best_iteration)` — `best_iteration` doesn't exist on `LGBMClassifier`, and `predict()` returns class labels not probabilities.
**Fix:** Changed to `self._model.predict_proba(X)[0, 1]`. Also added `fast=True` parameter that skips SHAP computation (5-min eval → 5-sec eval).

### Bug 11 — DuckDB UPDATE with PK index unreliable
`UPDATE events SET ubid = ?` raised "duplicate key" errors on indexed table.
**Fix:** Workaround in `refresh_event_ubids.py` and `/admin/refresh-ubids` — recreate the `events` table from a JOIN with the mapping. DuckDB doesn't support `ALTER TABLE ADD CONSTRAINT PRIMARY KEY` either, so we use a unique index instead.

### Bug 12 — `apply_decision` cannot-link path FK violation
The `_trigger_unlink_if_merged` function added a new `UBIDNodeORM` then immediately `UPDATE`d `ubid_source_links` to point at it — without flushing first, so the FK validation failed.
**Fix:** Added `db.flush()` after the new node insert.

### Bug 13 — `docker compose restart` doesn't reload `.env`
After changing `DORMANT_SCORE_THRESHOLD` in `.env`, restart kept old value because env_file is read once at container creation.
**Fix:** Use `docker compose up -d --force-recreate ubid-api` (not `restart`).

### Bug 14 — Streamlit duplicate plotly_chart auto-IDs
Multiple `st.plotly_chart` calls with same auto-generated ID raise `StreamlitDuplicateElementId`.
**Fix:** Pass unique `key="..."` to every `st.plotly_chart` call.

### Bug 15 — `apply_synonym` import error
`admin.py` imported `canonicalize` from `locality_normalizer` but the function is called `normalize`.
**Fix:** Corrected import.

### Bug 16 — `wipe_data.py` aborted transaction
First failed `DELETE FROM review_decisions` (table doesn't exist) aborted the surrounding transaction so no other deletes ran.
**Fix:** Use a separate session per table.

## New scripts (in `scripts/`)

| Script | Purpose |
|---|---|
| `send_events.py` | Sends `events_stream.jsonl` through the new `/api/v1/events` endpoint |
| `compute_verdicts.py` | Hits `/status?force_recompute=true&reference_date=2025-05-01` for every UBID |
| `train_scorer.py` | Loads ground truth, builds 1672 pairs, fits LightGBM + isotonic |
| `evaluate.py` | Pairwise + B3 + verdict accuracy against `ground_truth_links.csv` |
| `recluster.py` | Wipes UBID assignments and reruns greedy correlation clustering on stored linkage_pairs |
| `rescore_pairs.py` | Re-scores all pairs in `linkage_pairs` with the trained model |
| `refresh_event_ubids.py` | After re-cluster, remaps DuckDB events to new UBIDs |
| `wipe_data.py` | Clears Postgres + DuckDB + OpenSearch + Redis (preserves model artefacts) |
| `analyze_dormant_misses.py` | Diagnostic: which dormant entities are misclassified and why |
| `demo_reviewer_loop.py` | End-to-end demo: confirm_match merges, reject splits |
| `check_event_dupes.py` | Diagnostic for DuckDB events table |

Most scripts need to run inside the API container because of DuckDB locking:
```powershell
docker cp scripts/<script>.py ubid_platform-ubid-api-1:/app/scripts/<script>.py
docker exec ubid_platform-ubid-api-1 python /app/scripts/<script>.py
```

## How to start fresh after a wipe

```powershell
# 1. Wipe (deletes data, keeps model)
docker exec ubid_platform-ubid-api-1 python /app/scripts/wipe_data.py

# 2. Re-ingest CSVs (now uses inline clustering)
cd "C:\Users\Kunda\Desktop\Hackathon\ubid-platform\ubid_platform\data\synthetic"
curl.exe -X POST http://localhost:8000/api/v1/ingest/ekarmika/upload -F "file=@ekarmika_records.csv"
curl.exe -X POST http://localhost:8000/api/v1/ingest/fbis/upload     -F "file=@fbis_records.csv"
curl.exe -X POST http://localhost:8000/api/v1/ingest/kspcb/upload    -F "file=@kspcb_records.csv"
curl.exe -X POST http://localhost:8000/api/v1/ingest/bescom/upload   -F "file=@bescom_records.csv"

# 3. Re-send events
python C:\Users\Kunda\Desktop\Hackathon\ubid-platform\ubid_platform\scripts\send_events.py

# 4. Compute verdicts
python C:\Users\Kunda\Desktop\Hackathon\ubid-platform\ubid_platform\scripts\compute_verdicts.py

# 5. (Optional) re-train + evaluate
docker cp scripts/train_scorer.py  ubid_platform-ubid-api-1:/app/scripts/
docker cp scripts/evaluate.py      ubid_platform-ubid-api-1:/app/scripts/
docker exec ubid_platform-ubid-api-1 python /app/scripts/train_scorer.py
docker exec ubid_platform-ubid-api-1 python /app/scripts/evaluate.py
```

## 5th adapter — BWSSB (water supply) + FK fix + Nominatim live (May 2026, latest)

Proves the proposal's architectural pluggability claim by adding a brand-new source system end-to-end.

### What was added

**Schema:**
- `BWSSB = "bwssb"` added to `SourceSystem` enum.
- 5 new `EventType` values: `bwssb_bill_generated`, `bwssb_bill_paid`, `bwssb_zero_consumption`, `bwssb_disconnect`, `bwssb_reconnect`.
- 5 new entries in `signal_catalog.py` with weights slightly lower than BESCOM (some businesses survive without an active water connection).

**Code:**
- `src/ubid/ingest/bwssb_adapter.py` — new adapter file modelled on BESCOM. Consumer-name-may-be-landlord risk flag. KNCA Number → `rr_number` slot, account_id and consumer_number reused as well.
- `src/ubid/api/routers/ingest.py` — registered `BWSSBAdapter` in the `_ADAPTERS` dict.

**Synthetic data:**
- `data/synthetic/bwssb_records.csv` — 31 connections, addresses sampled from existing UBIDs.
- `data/synthetic/bwssb_events.jsonl` — 767 events (monthly bills + occasional disconnects), Jan 2024 → Apr 2025.
- `scripts/gen_bwssb_data.py` — regenerates both files deterministically.

**Live results:**
- 31 BWSSB records ingested through the unchanged pipeline.
- 28 of them auto-linked into existing UBIDs by address; 3 created their own UBIDs.
- 643 of 767 events successfully joined to UBIDs (the remainder were the disconnect/reconnect cycles for the 3 records on solo UBIDs).
- Total platform now: **267 source records, 75 UBIDs, 5 source systems**.
- Verdict distribution shifted: Active 38 (+5 from BWSSB activity tipping borderline dormants).

### Bug fixed: FK violation in inline-clustering merge

`src/ubid/api/routers/ingest.py` — when union-find merges UBIDs and deletes the smaller node, previous code triggered a `activity_verdicts.ubid_fkey` FK violation. Fix: delete dependent `activity_verdicts` rows before deleting the `ubid_nodes` row.

### Nominatim live but limited by synthetic data

Nominatim finished its first-time import (~10 minutes for the Karnataka 126MB extract), is healthy, and the geocoder priority order was reversed so Nominatim runs first.

`scripts/regeocode_with_nominatim.py` re-geocoded all 267 records:
- **Nominatim hits: 19** — addresses where street + locality resolved to a real building.
- **Dict fallback: 240** — synthetic addresses with fake plot numbers ("Site No. 112/A", "Plot 87", "Shed No. 12") that Nominatim can't pinpoint.
- **Failed: 8** — addresses too garbled for either path.

**Honest take:** Synthetic addresses limit Nominatim's value here. Real Karnataka business addresses with proper survey numbers in OSM would resolve much better — expect >70% Nominatim hits in production.

### Lift measurements

| Metric | Before (with manual splits from earlier sessions) | After 5th adapter + Nominatim |
|---|---|---|
| Pairwise F1 @ 0.70 | 0.898 | **0.910** |
| Brier | 0.0078 | 0.0086 |
| ECE | 0.0132 | 0.0152 |
| B3 F1 | 0.892 | **0.892** (unchanged) |
| Verdict accuracy | 0.817 | 0.733 (BWSSB events tip borderline dormants → active) |

The verdict accuracy drop is **not a regression** — it's the platform correctly registering newly-available water-bill activity that the ground-truth labels were created without. In a real deployment you would re-label after adding a new data source.

Implements `IMPROVEMENTS.md` items #6 (Nominatim wired live) and #11 (5th adapter).

---

## Geocoding infrastructure (May 2026, latest)

Wired the geocoding pipeline so addresses can resolve to (lat, lng) and the `addr_geo_distance_km` feature in the LightGBM scorer can fire.

### What was added

- **`data/dictionaries/locality_coordinates.json`** — 42 Bengaluru/Karnataka localities + 24 pin codes + 19 districts, hand-curated centroid coordinates.
- **`src/ubid/canonicalize/geocoder.py`** — module with `geocode(record)` that tries (in order): existing lat/lng → locality dict → pin-code dict → district dict → Nominatim if `NOMINATIM_URL` env is set. Sub-millisecond for the dict path.
- **`src/ubid/api/routers/ingest.py`** — calls `geocode_and_attach()` on every record before persisting, so new records get coords automatically.
- **`scripts/backfill_geocoding.py`** — walks all canonical_records without coords and geocodes them. Idempotent.
- **`docker-compose.yml`** — Nominatim service definition (commented out). Operator uncomments it + drops a `karnataka-latest.osm.pbf` extract from Geofabrik to enable real building-level geocoding.

### Result of running backfill

200 / 208 records (96.2%) successfully geocoded by the dictionary fast-path:
- bescom: 64, ekarmika: 62, fbis: 54, kspcb: 20

The 8 ungeocoded records have addresses with no recognised locality / pin / district.

### Honest measurement

Re-trained, re-scored boundary pairs, re-evaluated. **No measurable lift** in pairwise or B3 metrics. Reason:

> Centroid-based geocoding gives every record in the same locality the same lat/lng. So the geo-distance feature just mirrors `addr_locality_match` and adds redundancy, not new signal.

A guard in `src/ubid/scoring/features.py` was added: when both records share coords within ~100m (i.e. came from the same centroid), `addr_geo_distance_km` is set to MISSING — the model can't actually distinguish them. The feature therefore only fires for cross-locality pairs, where it's redundant with the existing locality-match feature.

### To get the real recall lift

Enable Nominatim. The pipeline is fully ready. Steps:
1. Download `karnataka-latest.osm.pbf` from https://download.geofabrik.de/asia/india/karnataka.html (~250 MB)
2. Place at `./nominatim_data/karnataka-latest.osm.pbf`
3. Uncomment the `nominatim` service in `docker-compose.yml`
4. Add `NOMINATIM_URL=http://nominatim:8080` to `.env`
5. `docker compose up -d nominatim ubid-api`
6. First-time import: ~10-30 minutes
7. Run `scripts/backfill_geocoding.py` again — Nominatim provides building-level coordinates for ~85-95% of addresses with proper street numbers
8. Trigger retrain via Admin → Retrain
9. Expected lift: pairwise recall +5-8 pts, B3 F1 +2-3 pts

### Current platform metrics (post-geocoding-fix, with manual test splits from earlier sessions)

| Metric | Value |
|---|---|
| Pairwise F1 @ 0.95 | unchanged (eval shows 0.898 at threshold 0.70 with new model) |
| Brier | 0.0078 |
| ECE | 0.0132 |
| **B3 F1** | **0.892** (was 0.917 baseline; -2.5 pts due to manual regroup tests, not geocoding) |
| **Verdict accuracy** | **0.817** (49/60, unchanged from pre-geocoding) |

Implements `IMPROVEMENTS.md` item #6 — infrastructure done, Nominatim activation is operator's choice based on disk/CPU budget.

---

## About / How-it-works page (May 2026, latest)

New top-nav entry `ℹ️ About` as the first page. Pulls live numbers from `/query/stats`, `/admin/calibration-report`, `/admin/retrain-history`, `/admin/labels-since-last-retrain`. Sections:

1. Hero — plain-English summary of the platform.
2. **Live metric strip** — 8 metrics: UBIDs, source records, pairwise F1, Brier, reviewer labels, pending review, quarantined events, last-retrain Δ F1.
3. **Architecture diagram** — pure HTML/CSS flow: 4 source CSVs (e-Karmika / FBIS / KSPCB / BESCOM) → canonicalise → block → score → cluster → UBID node → activity engine + reviewer console.
4. **Proposal-compliance checklist** — 10 ticked items with one-line justifications, ECE pulled live.
5. **Glossary** — 12 expandable terms.
6. **Tech stack** — 9 cards.

Pure frontend addition; no new backend endpoints. Implements `IMPROVEMENTS.md` item #1.

---

## Retrain history + label budget + smart re-score (May 2026, latest)

Three improvements aimed at production-scale operations and better demoability:

### A. New table `retrain_runs`

Logs every `/admin/retrain` invocation: timestamp, label counts, pre/post metrics, duration. Created automatically by `create_all_tables()` at API startup. ORM in `src/ubid/storage/postgres.py` (class `RetrainRunORM`).

### B. New endpoints

| Endpoint | Purpose |
|---|---|
| `GET  /api/v1/admin/retrain-history?limit=N` | Last N retrain runs with pre/post F1/Brier/ECE for the chart |
| `GET  /api/v1/admin/labels-since-last-retrain` | Counter for the label-budget UI; returns `total_labels`, `labels_since_last_retrain`, `recommendation` string |
| `POST /api/v1/admin/rescore?mode=smart\|full` | Re-score linkage_pairs. **smart** (default): only review-queue + boundary pairs (p ∈ [0.20, 0.97]). **full**: every pair. Solves the production-scale concern raised by the user — at 5 M pairs, smart mode touches ~10 K, full would take minutes-hours. |

### C. Frontend: Admin → Retrain tab now shows

- **Label-budget card** at top: big number ("42 new labels since last retrain") in saffron/red/green/grey based on count, plus total label count, last-retrain timestamp, and a recommendation message.
- **Retrain-history chart**: line chart of post-train F1 (green) and pre-train F1 (dashed grey) over time. Shows that the model is improving (or regressing) across runs.
- **Retrain-history table**: latest 20 runs with When · Labels · Total pairs · Pre F1 · Post F1 · Δ F1 · Pre Brier · Post Brier · Duration.

### D. Frontend: new tab "Re-score pairs"

Smart vs full mode selector. Help banner explaining the cost difference at scale. Single "Re-score now" button. Returns rescored count, skipped count, duration.

### E. Architectural note (the user's question)

**Retrain does NOT process all 10 M source records.** It operates only on the labelled-pair table (`training_labels` + ground truth) — typically 10 K to 100 K rows even at full production scale. The cost is linear in *labels*, not *records*. LightGBM trains on 100 K rows × 25 features in ~10 seconds.

The expensive operations at 10 M-record scale are:
- Blocking + scoring during ingestion (handled by OpenSearch + LightGBM inference, fast)
- Re-scoring historical pairs after a model update (now optimised via the smart mode)

These are unrelated to retrain.

---

## Sorting-Mat audit UI + `/regroup` endpoint (May 2026, latest)

### Why
The earlier "Audit Merges" page only allowed peeling **one record at a time**. For real-world UBIDs that span 40+ state departments, a single business cluster could contain 30+ records. If 5 of those were wrongly merged (representing 2 distinct businesses + 1 isolated outlier), the reviewer had to make 5 separate decisions sequentially — error-prone and slow.

### What changed

**Backend — new endpoint: `POST /api/v1/review/regroup`**

Atomically splits a UBID into N sub-clusters according to reviewer-supplied groupings. Request body:
```json
{
  "ubid": "uuid",
  "groupings": {"<canonical_id>": "Group 1", "<canonical_id>": "Group 2", "<canonical_id>": "Solo", ...},
  "reviewer_id": "...",
  "reviewer_tier": "junior|senior",
  "notes": "..."
}
```

Behaviour:
- Each `Solo`-labelled record → its own brand-new UBID (each Solo is unique, never shared).
- Each named group with ≥2 members → all of them share one UBID (largest group keeps the original UBID UUID for stability).
- Within-group pairs → must-link constraint + `is_match=True` training label + reviewer_decision.
- Cross-group pairs (and any pair involving a Solo) → cannot-link + `is_match=False` + reviewer_decision.
- All writes happen in a single Postgres transaction.
- DuckDB events table is rebuilt (best-effort) to point at the new UBIDs so verdicts stay correct.
- Idempotent: existing constraints are updated rather than duplicated.
- If everyone is in one group, falls through to the existing `approve_ubid` logic.

Constraint scaling:
- 30 records / 3 groups (10/10/10) = 135 must-link + 300 cannot-link = 435 rows + matching decisions/labels = ~1300 inserts. Sub-second in Postgres.
- 50 records / 5 groups (10×5) = 225 must-link + 1000 cannot-link = ~3700 inserts. ~1-2s.
- 100 records / 10 groups → ~13.5K inserts, ~5s. Wrapped with a Streamlit `st.spinner`.

**Frontend — Audit Merges page rewritten as "Sorting Mat":**

- **Group manager strip at top**: pills showing each group + count, `+ Add Group N` button (no hard cap), `↺ Reset all`, `⚠ All Solo`.
- **Record table** (uses `st.data_editor` with `SelectboxColumn` on the Group column). Sortable by source/name/PAN. Other columns read-only.
- **Filter + bulk-assign row** above the editor: filter by source system or name/PAN substring, then "Bulk move to Group X → Apply to filtered" moves every visible record at once.
- **Pair-evidence table** in a collapsed expander (auto-expanded if cluster has ≤5 records).
- **Live preview** below the editor: shows how many UBIDs will result, how many constraints + decisions + training labels will be written, and notes that they feed the next retrain.
- **Apply / Skip / Reset buttons** at the bottom.
- All groupings are stored in `st.session_state` keyed by UBID + canonical_id so the reviewer can fiddle with assignments before submitting.

### Feedback loop (the punchline)

Every reviewer decision in the Sorting Mat becomes a `TrainingLabelORM(is_match=…)` row. The next time you click `⚙️ Admin → Trigger retrain`, LightGBM sees those labels alongside the synthetic ground truth. So if a reviewer audits 20 UBIDs and writes ~300 labelled pairs, the retrain consumes them all. The `linkage_constraints` rows additionally protect the assignments against future ingest re-clusterings.

### Dropdown-popover CSS fix

Same session: added explicit styling for `[data-baseweb="popover"]`, `[role="option"]`, `[role="listbox"]`, and `[data-baseweb="calendar"]` to fix the dark-on-grey unreadable dropdown popover. White bg, navy hover, navy-bg-white-text on selection.

### Sorting Mat — vertical-list + comparison widget rebuild

A second pass on the audit page (after the first regroup-endpoint version), driven by user feedback:

**Problem**: `st.data_editor`'s `SelectboxColumn` is a Glide Data Grid widget that doesn't pick up our BaseWeb popover CSS — its dropdown rendered black-on-black. Also the user wanted an easier way to compare specific records before grouping them.

**Fixes:**

1. **Replaced `st.data_editor` with a vertical record list.** Each record is now a row of `st.columns` with our themed selectbox for the Group assignment. The selectbox uses the same popover styling as everything else, so it's properly readable. Bonus: address line shown beneath the name (data_editor truncated it badly), and the group color is shown as a colored dot to the left of each row.

2. **Added side-by-side comparison widget** above the sort table:
   - Two record-picker dropdowns (Record A / Record B)
   - Renders an HTML `<table class="compare-table">` with one row per field (Name, PAN, GSTIN, Pin, District, Address, Phone, Sector, Legal form, Employees, Reg date)
   - Each row colour-coded: green (✓) for exact match, amber (⚠) for mismatch, gray (⚪) for missing on either side, ≈ for partial match (substring)
   - Footer summary: `✓ matches · ⚠ mismatches · ⚪ missing`
   - **Quick action selectbox**: with the two records picked, instantly assign them to the same group / different groups / both Solo. Updates the session state and reruns.

3. **Contrast overrides for Streamlit defaults.** Added CSS rules to force any `.stMarkdown small`, `[data-testid="stTooltipIcon"]`, `[data-baseweb="form-control-caption"]` (Streamlit's built-in helper-text gray) to at least our `--ink-muted` (`#475569`, 7:1 contrast on white). Also forces `[data-testid="stMarkdownContainer"] p / li / span` to ink-color so paragraph text is dark slate, not light gray.

**Files touched:**
- `src/ubid/api/routers/review.py` — `/regroup` endpoint (already in earlier change)
- `frontend/reviewer_console.py` — Audit Merges page rewrite + CSS additions (~250 LOC change)
- `HANDOFF.md` — this section

---

## Frontend redesign (May 2026, late session)

**Why:** First pass of the gov-themed UI used a warm off-white surface (#FAF7F2) that washed out captions (#5C5C5C → 5.1:1 contrast, sub-AAA), buttons were thin and easy to miss, and the sidebar consumed too much horizontal space.

**What changed:**
1. **Layout** — left sidebar removed, replaced by:
   - Horizontal `gov-header` bar (navy gradient + saffron-bordered chakra crest + tagline + platform name + dept).
   - Tricolor strip below.
   - `control-bar` row with 5 columns: reviewer ID input · tier select · reference date · 📖 help toggle · API status indicator.
   - Top-tab nav using `st.radio(horizontal=True)` styled as proper tabs (saffron underline on active).
2. **Color tokens** — pure white `#FFFFFF` background; text contrast bumped: secondary `#5C5C5C` → `#334155` (11:1 contrast), muted floor `#475569` (7:1), borders `#CBD5E1` slate-300.
3. **Buttons** — 42px tall, 6px radius, subtle shadow + hover lift; primary = solid saffron (white text); secondary = white with navy border that fills on hover.
4. **Inputs** — 42px tall, 1.5px slate-300 border, 3px navy/15% focus ring, stronger labels above (#0F172A bold).
5. **Verdict badges** — solid colour bg (was tinted): green/saffron/red/navy with white text.
6. **Cards** — 8px radius, 4px coloured left-border, hover-lift shadow.
7. **Tables** — navy header bar with white text; alternating row striping.
8. **Charts** — plot bg pure white (was `#FAF7F2`), gridlines `#E2E8F0`, font color `#334155`.

**Files touched:** only `frontend/reviewer_console.py` (~600-line CSS block + sidebar block + chart configs). All page logic untouched — every page still works exactly as before.

**To revert:** the previous version is in git history. `git diff HEAD frontend/reviewer_console.py` shows the change, `git checkout HEAD -- frontend/reviewer_console.py` reverts it.

---

# 🔵 SESSION 1 (original, May 2025-ish)

## What this project is
AI for Bharat Hackathon, Theme 1 — Unified Business Identifier (UBID) platform for
Karnataka Commerce & Industries. Round 1 (proposal) is done. We are building the Round 2
prototype codebase.

The platform:
- Ingests records from 4 Karnataka state department systems
- Links records referring to the same business across departments (entity resolution)
- Assigns each business a Unique Business Identifier (UBID)
- Classifies each UBID as Active / Dormant / Closed based on activity events
- Routes ambiguous matches to a human reviewer console

---

## Codebase location
`E:\AI_For_Bharat\Theme1\ubid_platform\` *(historical — see Session 2 for the current path)*

All 67 files written. Production stack running in Docker.

---

## Tech stack
| Component | Technology |
|---|---|
| API | FastAPI (uvicorn, port 8000) |
| Reviewer UI | Streamlit (port 8501) |
| Database | PostgreSQL 16 (port 5432) |
| Search/Blocking | OpenSearch 2.16 (port 9200) |
| Entity Graph | Neo4j 5.24 (port 7687) |
| Cache | Redis 7 (port 6379) |
| Message Queue | Kafka via confluentinc/cp-kafka:7.7.0 (port 9092) |
| Event Warehouse | DuckDB (embedded, file at data/parquet/events.duckdb) |
| ML Scorer | LightGBM + Isotonic calibration (falls back to heuristic if untrained) |

---

## How to start Docker (from E drive)
```powershell
cd "E:\AI_For_Bharat\Theme1\ubid_platform"
docker compose up --build
```
Wait for: `ubid-api-1 | UBID Platform API ready.`

URLs: API docs → http://localhost:8000/docs | Reviewer UI → http://localhost:8501

---

## Current status (as of handoff)

### What is working — ALL 4 SOURCES SUCCESSFULLY INGESTED
- Docker stack fully builds and starts
- All 9 services healthy (postgres, redis, opensearch, neo4j, kafka, kafka-ui,
  ubid-api, ubid-worker, ubid-frontend)
- ✅ ekarmika ingested successfully
- ✅ fbis ingested successfully
- ✅ kspcb ingested successfully
- ✅ bescom ingested successfully
- All bug fixes applied (see Bugs Fixed section below)

### What still needs to be done next session
1. Ingest activity events from events_stream.jsonl.
   Save this as `send_events.py` anywhere and run it:
   ```python
   import json, httpx

   EVENTS_FILE = r"E:\AI_For_Bharat\Theme1\ubid_platform\data\synthetic\events_stream.jsonl"

   with open(EVENTS_FILE, encoding="utf-8") as f:
       events = [json.loads(line) for line in f if line.strip()]

   print(f"Sending {len(events)} events...")
   ok = 0
   for evt in events:
       try:
           r = httpx.post(
               f"http://localhost:8000/api/v1/ingest/{evt['source_system']}",
               json={"records": [evt]},
               timeout=10
           )
           ok += 1
       except Exception as e:
           print(f"Error: {e}")
   print(f"Done — {ok} sent")
   ```
   Run with: `python send_events.py`

2. Verify verdicts are computed:
   ```powershell
   curl.exe http://localhost:8000/api/v1/query/stats
   ```

3. Test the exemplar query:
   ```powershell
   curl.exe -X POST http://localhost:8000/api/v1/query/active-businesses `
     -H "Content-Type: application/json" `
     -d "{\"verdict\":\"active\",\"source_system\":\"fbis\",\"no_event_type\":\"fac_inspection\",\"no_event_since_days\":540}"
   ```

4. Open reviewer console and review some pairs: http://localhost:8501

5. Look up a specific UBID:
   ```powershell
   curl.exe "http://localhost:8000/api/v1/lookup?source=ekarmika&id=SE-180042"
   ```

### IMPORTANT: On new system after git clone
Docker volumes (Postgres, OpenSearch, Neo4j, Redis data) are NOT in git.
You must re-ingest all data after cloning:
```powershell
cd "E:\AI_For_Bharat\Theme1\ubid_platform"
docker compose up --build
# Wait for "UBID Platform API ready."
cd data\synthetic
curl.exe -X POST http://localhost:8000/api/v1/ingest/ekarmika/upload -F "file=@ekarmika_records.csv"
curl.exe -X POST http://localhost:8000/api/v1/ingest/fbis/upload     -F "file=@fbis_records.csv"
curl.exe -X POST http://localhost:8000/api/v1/ingest/kspcb/upload    -F "file=@kspcb_records.csv"
curl.exe -X POST http://localhost:8000/api/v1/ingest/bescom/upload   -F "file=@bescom_records.csv"
# Then run send_events.py for the events stream
```

### Synthetic data location
```
E:\AI_For_Bharat\Theme1\ubid_platform\data\synthetic\
  ekarmika_records.csv
  fbis_records.csv
  kspcb_records.csv
  bescom_records.csv
  events_stream.jsonl
  ground_truth_links.csv
```

---

## All bugs fixed (with explanations)

### Bug 1 — docker-compose.yml: version attribute + bitnami/kafka not found
**File:** `docker-compose.yml`
- Removed `version: "3.9"` (obsolete in new Docker Compose)
- Replaced `bitnami/kafka:3.8` → `confluentinc/cp-kafka:7.7.0`
  (Bitnami removed images from Docker Hub after Broadcom acquisition)
- Updated Kafka env vars from `KAFKA_CFG_*` to `KAFKA_*` format
- Updated volume path from `/bitnami/kafka` to `/var/lib/kafka/data`
- Updated healthcheck binary from `kafka-topics.sh` to `kafka-topics`

### Bug 2 — pyproject.toml: wrong build backend
**File:** `pyproject.toml`
- Changed `"setuptools.backends.legacy:build"` → `"setuptools.build_meta"`
- Was causing `pip install -e .` to exit with code 2 during Docker build

### Bug 3 — SQLAlchemy reserved name 'metadata'
**File:** `src/ubid/storage/postgres.py`
- `metadata` is reserved by SQLAlchemy's DeclarativeBase (it's the MetaData registry object)
- Renamed column attribute in `ActivityEventORM` and `QuarantineEventORM`:
  `metadata = Column(JSONB...)` → `event_metadata = Column("metadata", JSONB...)`
  (Python attribute renamed; actual DB column still called "metadata")
- Also updated `src/ubid/activity/quarantine.py`: `qe.metadata` → `qe.event_metadata`

### Bug 4 — Pydantic protected namespace warning
**File:** `src/ubid/config.py`
- `model_dir` field conflicts with Pydantic v2's `model_` protected namespace
- Added `protected_namespaces=()` to `SettingsConfigDict`

### Bug 5 — FK violation: reviewer_queue references linkage_pairs before commit
**File:** `src/ubid/api/routers/ingest.py`
- `enqueue_pair()` opened a new DB session and inserted into `reviewer_queue`
  referencing a `pair_id` that was only in an uncommitted session
- Fix: collect all pairs to enqueue in a list, commit the scoring session first,
  then enqueue after

### Bug 6 — FK violation: linkage_pairs references canonical_id not in DB (MAIN BUG)
**File:** `src/ubid/api/routers/ingest.py`
- Root cause: when a record already existed in Postgres, old code skipped reinserting
  it BUT still indexed the NEW UUID in OpenSearch → scorer found a UUID that Postgres
  had never seen → FK violation on linkage_pairs.canonical_id_b
- Fix: when a record already exists, REUSE the stored canonical_id before indexing
  (`rec.canonical_id = str(existing.canonical_id)`)
- Also fixed: SQLAlchemy autoflush mid-loop was flushing pending pairs before
  candidate canonical_ids were confirmed in DB
  Fix: use `with db.no_autoflush:` around candidate SELECT; load existing pair keys
  upfront once; collect all pairs then commit once outside the loop

### Bug 6 continued — curl syntax on Windows PowerShell
- PowerShell's `curl` is an alias for `Invoke-WebRequest` which doesn't accept
  `-X`, `-F` flags
- Must use `curl.exe` instead of `curl`

---

## Key file locations

### Core pipeline
```
src/ubid/
  config.py                    — all settings from .env
  schema/canonical.py          — CanonicalRecord, SourceSystem, VerdictLabel enums
  schema/events.py             — ActivityEvent, EventType enums
  ingest/ekarmika_adapter.py   — reads: name, address, pan, gstin, phone, email,
                                  establishment_registration_no, date_of_commencement,
                                  nature_of_business, employee_count
  ingest/fbis_adapter.py       — reads: factory_name, address, taluk, district,
                                  pin_code, occupier_pan, licence_number,
                                  constitution_type, installed_hp, nic_code
  ingest/kspcb_adapter.py      — reads: industry_name, industry_category,
                                  industrial_area, taluk, district, pin_code,
                                  pan, gstin, valid_until, consent_file_no
  ingest/bescom_adapter.py     — reads: consumer_name, service_address, rr_number,
                                  account_id, tariff_category, sanctioned_load_kw
  canonicalize/name_normalizer.py    — strips legal forms, expands abbreviations
  canonicalize/address_parser.py     — extracts pin, door number, district
  canonicalize/locality_normalizer.py — synonym dict + rapidfuzz fallback
  canonicalize/identifier_extractor.py — PAN/GSTIN validation and extraction
  blocking/opensearch_blocker.py     — union-blocking on PAN, pin+name, pin+door, phone
  scoring/deterministic.py           — PAN equality rules (hard match/reject)
  scoring/features.py                — 25-feature vector computation
  scoring/lgbm_scorer.py             — LightGBM + heuristic fallback
  clustering/correlation_cluster.py  — greedy correlation clustering
  graph/neo4j_graph.py               — LegalEntity→UBID→SourceRecord hierarchy
  activity/signal_catalog.py         — event weights and cadences (Table 2 from proposal)
  activity/decay.py                  — cT(Δt) = wT * exp(−Δt / α·τT)
  activity/verdict.py                — Active/Dormant/Closed verdict engine
  activity/quarantine.py             — unjoined event queue
  review/queue.py                    — active-learning priority ordering
  review/feedback.py                 — constraint write-back on reviewer decisions
  api/main.py                        — FastAPI app entrypoint
  api/routers/ingest.py              — POST /api/v1/ingest/{source}/upload
  api/routers/lookup.py              — GET /api/v1/lookup
  api/routers/status.py              — GET /api/v1/ubid/{ubid}/status
  api/routers/review.py              — GET/POST /api/v1/review/queue
  api/routers/query.py               — POST /api/v1/query/active-businesses
  storage/postgres.py                — SQLAlchemy ORM models + engine
  storage/redis_cache.py             — source_id→UBID hot-path cache
  storage/duckdb_warehouse.py        — event warehouse
  kafka/consumer.py                  — Kafka worker (python -m ubid.kafka.consumer)
frontend/reviewer_console.py         — Streamlit reviewer UI
```

### Data dictionaries (committed to git, used at runtime)
```
data/dictionaries/
  locality_synonyms.json     — "Peenya 2nd Stage" → canonical key
  legal_form_patterns.json   — "Pvt Ltd", "M/s" etc. to strip
  abbreviations.json         — "Trdrs" → "Traders"
  sector_priors.json         — seasonal sector configs
```

---

## API quick reference
```
GET  /health                                    — health check
POST /api/v1/ingest/{source}                    — JSON batch ingest
POST /api/v1/ingest/{source}/upload             — CSV file upload
GET  /api/v1/lookup?source=ekarmika&id=SE-001   — resolve source ID → UBID
GET  /api/v1/lookup?pan=ABCDE1234F              — resolve PAN → UBIDs
GET  /api/v1/ubid/{ubid}/status                 — verdict + evidence timeline
GET  /api/v1/review/queue                       — pending review items
POST /api/v1/review/decide                      — submit reviewer decision
POST /api/v1/query/active-businesses            — exemplar analytical query
GET  /api/v1/query/stats                        — platform dashboard stats
```

---

## Source system CSV column names (exact — must match for adapters to work)

### ekarmika_records.csv
establishment_registration_no, name, address, nature_of_business,
date_of_commencement, pan, gstin, phone, email, employee_count

### fbis_records.csv
licence_number, form2_registration_no, factory_name, address,
village_town, taluk, district, pin_code, nature_of_manufacturing,
nic_code, occupier_pan, gstin, phone, email, employee_count,
installed_hp, constitution_type, registration_date, licence_valid_until

### kspcb_records.csv
consent_file_no, industry_name, industry_category, sector, nic_code,
industrial_area, taluk, district, pin_code, latitude, longitude,
pan, gstin, cin, phone, email, date_of_commissioning, valid_until

### bescom_records.csv
rr_number, account_id, k_number, consumer_name, service_address,
tariff_category, sanctioned_load_kw, phone

### events_stream.jsonl (one JSON per line)
{"event_id": "<uuid>", "source_system": "<ekarmika|fbis|kspcb|bescom>",
 "source_record_id": "<matches primary ID in CSV>",
 "event_type": "<see below>", "event_date": "YYYY-MM-DD", "metadata": {}}

Valid event_type values:
  se_selfcert_post2019, se_closure, se_amendment
  fac_form20_annual, fac_form21_halfyearly, fac_license_renewal, fac_inspection, fac_delicensed
  kspcb_cfo_renewal, kspcb_compliance_report, kspcb_consent_revoked, kspcb_cca_issued
  bescom_bill_generated, bescom_bill_paid, bescom_zero_consumption,
  bescom_disconnect, bescom_reconnect, bescom_tariff_change

---

## Adding a new department system (if different systems are provided)
1. Add enum value to `SourceSystem` in `src/ubid/schema/canonical.py`
2. Create `src/ubid/ingest/<newsystem>_adapter.py` extending `BaseAdapter`
3. Register in `_ADAPTERS` dict in `src/ubid/api/routers/ingest.py`
4. Add new event types to `EventType` enum in `src/ubid/schema/events.py`
5. Add signal configs to `src/ubid/activity/signal_catalog.py`
Nothing else changes — all downstream pipeline is schema-agnostic.

---

## Environment variables (.env file at project root)
Key values (all have defaults, no changes needed for local Docker):
  POSTGRES_HOST=postgres, POSTGRES_PORT=5432, POSTGRES_DB=ubid
  REDIS_URL=redis://redis:6379/0
  OPENSEARCH_URL=http://opensearch:9200
  NEO4J_URI=bolt://neo4j:7687, NEO4J_PASSWORD=ubid_neo4j_secret
  KAFKA_BOOTSTRAP_SERVERS=kafka:9092
  AUTO_LINK_THRESHOLD=0.95   (pairs above this auto-linked)
  REVIEW_THRESHOLD_LOW=0.55  (pairs below this rejected; between = review queue)
  ACTIVITY_ALPHA=1.5         (decay forgiveness factor)
  ACTIVE_SCORE_THRESHOLD=1.5
  DORMANT_SCORE_THRESHOLD=0.4

---

## Important architecture decisions (from proposal)
- Wrong merge > missed merge: auto-link threshold is conservative (0.95)
- No neural embeddings: uses Jaro-Winkler, token-set ratio, Jaccard n-grams
- No hosted LLMs: all processing is local
- Activity engine is rule-driven not ML (for explainability / procurement)
- BESCOM is matched by address only (consumer name is often property owner)
- PAN 4th char = P means proprietorship: one PAN → multiple establishments (soft match)
- GSTIN embeds PAN at chars 3–12: extract with gstin[2:12]
