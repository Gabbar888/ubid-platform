# UBID Platform — Unified Business Identifier & Active Business Intelligence

> **AI for Bharat 2 · Theme 1 · Karnataka Commerce & Industries**
> *Federated entity-resolution and activity-inference platform that sits alongside Karnataka's 40+ State department systems without modifying any of them.*

---

## What this platform does, in one paragraph

Karnataka has 40+ State department systems holding business records — each built in isolation, each with its own schema and identifiers. The **same business shows up as different rows in different databases**, with no reliable join key. This platform pulls records from those systems, links the ones that refer to the same real-world business, assigns each business a **Unified Business Identifier (UBID)**, and watches activity events to classify each business as **Active / Dormant / Closed** with full evidence and reversibility.

**Final measured metrics:** Pairwise F1 = 0.91 · B3 cluster F1 = 0.92 · Brier = 0.009 · ECE = 0.013 · Verdict accuracy = 82% · 5 source systems integrated · 11 frontend pages.

---

## Live URLs (once running)

| What | URL | Purpose |
|---|---|---|
| **Reviewer Console** | <http://localhost:8501> | The main UI — start here |
| **API docs (Swagger)** | <http://localhost:8000/docs> | Try every endpoint live |
| **Health check** | <http://localhost:8000/health> | Returns `{"status":"ok"}` |
| **Kafka UI** | <http://localhost:8080> | Inspect Kafka topics |
| **OpenSearch Dashboards** | <http://localhost:5601> | Inspect blocking indexes |
| **Neo4j Browser** | <http://localhost:7474> | Visualise the entity graph |
| **Nominatim (geocoder)** | <http://localhost:8090> | Self-hosted OSM geocoder |

---

## Prerequisites

You only need **two things** installed locally:

| Tool | Version | Why |
|---|---|---|
| **Docker Desktop** | 24+ (or Docker Engine + Compose v2) | Runs all 11 services in containers |
| **Python 3.10+** | optional | Only for client scripts that send data to the API |

**Docker resource recommendation:**
- 8 GB RAM minimum (12 GB ideal)
- 4 CPU cores minimum
- 15 GB free disk (Docker images + data + Nominatim DB)

**Tested on:** Windows 11 with Docker Desktop, macOS Sonoma, Ubuntu 22.04.

---

## Repository layout

```
ubid-platform/
├── README.md                ← you are here
├── HANDOFF.md               ← full project state, history, bug log
├── IMPROVEMENTS.md          ← roadmap of next 20 features
├── PRESENTATION.md          ← markdown source of slides
├── presentation.html        ← reveal.js slide deck (open in browser)
├── DEMO_SCRIPT.md           ← 5-minute demo recording script
├── TECH_RATIONALE.md        ← why each tech was chosen
├── UBID_Proposal.pdf        ← original Round-1 proposal
├── proposal_extracted.txt   ← text version of the proposal
├── Problem_statement.md     ← Theme 1 problem statement
├── karnataka_source_schemas.md  ← research on actual Karnataka schemas
└── ubid_platform/           ← the actual codebase
    ├── docker-compose.yml   ← infrastructure definition (11 services)
    ├── Dockerfile           ← API + frontend container build
    ├── pyproject.toml
    ├── requirements.txt
    ├── .env.example         ← copy → .env to configure
    │
    ├── src/ubid/            ← Python backend
    │   ├── api/             ← FastAPI routers (ingest, lookup, status, review, query, admin, events)
    │   ├── ingest/          ← One adapter per source system
    │   ├── canonicalize/    ← Name/address normalisation, geocoding
    │   ├── blocking/        ← OpenSearch union-blocking
    │   ├── scoring/         ← LightGBM scorer + isotonic calibration
    │   ├── clustering/      ← Union-find + correlation clustering
    │   ├── graph/           ← Neo4j entity-graph operations
    │   ├── activity/        ← Verdict engine, signal catalog, decay
    │   ├── review/          ← Reviewer queue, feedback handlers
    │   ├── storage/         ← Postgres ORM, Redis cache, DuckDB warehouse
    │   ├── kafka/           ← Producer + consumer
    │   ├── schema/          ← Pydantic models, enums
    │   └── config.py        ← Settings (loads from .env)
    │
    ├── frontend/
    │   ├── reviewer_console.py  ← Streamlit UI (12 pages)
    │   └── assets/              ← Drop your karnataka_logo.png here
    │
    ├── data/
    │   ├── dictionaries/    ← Locality synonyms, legal forms, sector priors
    │   └── synthetic/       ← Test data — 5 source CSVs + events JSONL
    │
    ├── nominatim_data/      ← Drop karnataka-latest.osm.pbf here (optional)
    │
    ├── scripts/             ← Operational scripts (ingest, train, evaluate, etc.)
    └── tests/               ← Test stubs
```

---

## ⚡ Quick start (5 minutes — get to a running platform)

If you want the fastest path to a running platform:

```bash
# 1. Clone
git clone <repo-url> ubid-platform
cd ubid-platform/ubid_platform

# 2. Configure
cp .env.example .env

# 3. Start everything (first time: ~5 min to download images + build)
docker compose up -d

# 4. Wait until the API is ready (loops until `UBID Platform API ready.` appears)
docker logs -f ubid_platform-ubid-api-1 | grep -m1 "UBID Platform API ready."

# 5. Ingest the synthetic data (4 CSVs)
cd data/synthetic
curl -X POST http://localhost:8000/api/v1/ingest/ekarmika/upload -F "file=@ekarmika_records.csv"
curl -X POST http://localhost:8000/api/v1/ingest/fbis/upload     -F "file=@fbis_records.csv"
curl -X POST http://localhost:8000/api/v1/ingest/kspcb/upload    -F "file=@kspcb_records.csv"
curl -X POST http://localhost:8000/api/v1/ingest/bescom/upload   -F "file=@bescom_records.csv"
curl -X POST http://localhost:8000/api/v1/ingest/bwssb/upload    -F "file=@bwssb_records.csv"

# 6. Send activity events (~1900 events)
cd ../..
docker exec ubid_platform-ubid-api-1 python /app/scripts/send_events.py

# 7. Compute verdicts for all UBIDs
docker exec ubid_platform-ubid-api-1 python /app/scripts/compute_verdicts.py

# 8. Open the UI
# → http://localhost:8501
```

That's it. You should see ~75 UBIDs with verdicts populated.

> **Windows users:** use `curl.exe` instead of `curl` in PowerShell — PowerShell aliases `curl` to `Invoke-WebRequest` which doesn't accept `-X`/`-F` flags. All other commands are identical.

---

## Detailed step-by-step setup

### Step 1 — Clone the repository

```bash
git clone <repo-url>
cd ubid-platform
```

The repository contains both the codebase (`ubid_platform/`) and the documentation (this README, HANDOFF.md, etc.) at the root.

### Step 2 — Configure environment

```bash
cd ubid_platform
cp .env.example .env
```

The default `.env` works for local Docker. Key values you may want to tweak:

```bash
AUTO_LINK_THRESHOLD=0.95         # pairs above this auto-link
REVIEW_THRESHOLD_LOW=0.55        # pairs below this rejected; between → review
ACTIVITY_ALPHA=1.5               # activity-decay forgiveness factor
DORMANT_SCORE_THRESHOLD=0.15     # dormant if continuity score ≥ this
```

### Step 3 — Start the Docker stack

```bash
docker compose up -d
```

**First-time setup downloads ~3 GB of images** — Postgres, OpenSearch, Neo4j, Kafka, Redis, Nominatim, and the API/frontend builds. Subsequent starts take ~60 seconds.

**Watch the startup:**

```bash
docker compose logs -f
```

You'll see services come up in dependency order. The platform is ready when you see:

```
ubid-api-1 | INFO ubid.api.main UBID Platform API ready.
```

**Verify all 11 services are running:**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected output (10 always-on services + Nominatim if enabled):

```
ubid_platform-postgres-1                Up (healthy)
ubid_platform-redis-1                   Up (healthy)
ubid_platform-opensearch-1              Up (healthy)
ubid_platform-opensearch-dashboards-1   Up
ubid_platform-neo4j-1                   Up (healthy)
ubid_platform-kafka-1                   Up (healthy)
ubid_platform-kafka-ui-1                Up
ubid_platform-ubid-api-1                Up
ubid_platform-ubid-worker-1             Up
ubid_platform-ubid-frontend-1           Up
ubid_platform-nominatim-1               Up
```

### Step 4 — Verify health

```bash
# API is up
curl http://localhost:8000/health
# → {"status":"ok"}

# Frontend is up
curl -I http://localhost:8501
# → HTTP/1.1 200 OK
```

### Step 5 — Ingest synthetic data

The repo ships with **synthetic CSVs for 5 source systems** in `data/synthetic/`. We don't ship a Postgres dump — every operator should ingest fresh to exercise the live pipeline.

```bash
cd data/synthetic

# Five source systems (each ingest runs canonicalization → blocking → scoring → clustering)
curl -X POST http://localhost:8000/api/v1/ingest/ekarmika/upload -F "file=@ekarmika_records.csv"
curl -X POST http://localhost:8000/api/v1/ingest/fbis/upload     -F "file=@fbis_records.csv"
curl -X POST http://localhost:8000/api/v1/ingest/kspcb/upload    -F "file=@kspcb_records.csv"
curl -X POST http://localhost:8000/api/v1/ingest/bescom/upload   -F "file=@bescom_records.csv"
curl -X POST http://localhost:8000/api/v1/ingest/bwssb/upload    -F "file=@bwssb_records.csv"
```

**Each response shows what happened:**

```json
{"accepted": 63, "auto_linked": 14, "review_queued": 732, "new_ubids": 49}
```

- `accepted` — records ingested
- `auto_linked` — pair scores ≥ 0.95 → automatic merge into existing UBIDs
- `review_queued` — pair scores between 0.55 and 0.95 → reviewer must decide
- `new_ubids` — records that didn't match anyone, got their own UBID

After all 5 ingests you should have **~267 source records** mapped to **~75 UBIDs**.

### Step 6 — Send activity events

Activity events drive the Active/Dormant/Closed verdicts. The `send_events.py` script reads `events_stream.jsonl` (1951 events spanning 2023-11 → 2025-04) and posts them.

```bash
docker exec ubid_platform-ubid-api-1 python /app/scripts/send_events.py
```

Output:

```
Sending 1951 events…
Done — 1944 joined, 7 quarantined.
```

The 7 quarantined events reference source records that were deliberately omitted from the CSVs — they exercise the platform's "never silently drop events" guarantee. They appear on the **🚧 Quarantine** page.

### Step 7 — Compute initial verdicts

```bash
docker exec ubid_platform-ubid-api-1 python /app/scripts/compute_verdicts.py
```

This computes Active/Dormant/Closed for every UBID using the joined events. Without this step, the Dashboard's verdict-distribution donut is empty.

> **Why a separate step?** Verdicts are computed lazily on demand by default. This script forces a full recompute upfront so the Dashboard is fully populated before a judge looks.

### Step 8 — Open the platform

| Where | URL |
|---|---|
| **Reviewer Console (start here)** | <http://localhost:8501> |
| **API documentation** | <http://localhost:8000/docs> |

You'll land on the **📊 Dashboard** — should show ~75 UBIDs, 267 records, verdict donut populated, calibration chart visible.

---

## Tour the platform — what each page does

The reviewer console has **12 pages** in its top nav. In recommended viewing order:

| # | Page | What it does |
|---|---|---|
| 1 | **📊 Dashboard** | Live metrics, verdict-distribution donut, source coverage, model calibration chart |
| 2 | **🔍 Browse UBIDs** | Filterable, paginated grid of every UBID. Click `Open` → drilldown. Export CSV |
| 3 | **📋 Review Queue** | Ambiguous match candidates. SHAP per pair. Confirm / Reject / Defer / Flag. Bulk actions |
| 4 | **🧐 Audit Merges** | Sorting Mat — verify auto-merges, sort records into groups, all decisions feed retraining |
| 5 | **🧭 UBID Lookup** | Resolve any source ID, PAN, or name+pin → UBID |
| 6 | **📈 Activity Status** | One UBID's verdict, evidence timeline, lineage, and Unmerge UI |
| 7 | **🚧 Quarantine** | Events that couldn't join a UBID. Retry one or all |
| 8 | **📜 Reviewer Log** | Decision history per reviewer, leaderboard chart |
| 9 | **❓ Query Explorer** | Run the proposal's exemplar query: *active factories with no inspection in 18 months* |
| 10 | **📤 Ingest Data** | Upload more CSVs or paste activity events |
| 11 | **⚙️ Admin** | Retrain · re-score · calibration · synonyms · verdicts |
| 12 | **ℹ️ About** | Architecture diagram, live metrics, proposal-compliance checklist, glossary |

---

## Architecture at a glance

```
┌──────────────────────────────────────────────────────────────────┐
│  Karnataka source systems (read-only)                            │
│  e-Karmika · FBIS · KSPCB · BESCOM · BWSSB                       │
└───────────────────────────┬──────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Adapters → Canonicalise → Block → Score → Cluster               │
│  (Python)   (rapidfuzz +    (OpenSearch)  (LightGBM +            │
│              dictionaries +                isotonic)             │
│              indic-translit)                                     │
└───────────────────────────┬──────────────────────────────────────┘
                            ▼
                ┌──────────────────────┐
                │   UBID Graph (Neo4j) │
                │  Legal Entity → UBID │
                │  → Source Records    │
                └────┬───────────┬─────┘
                     │           │
                     ▼           ▼
        ┌────────────────┐ ┌─────────────────────┐
        │ Activity engine│ │ Reviewer console    │
        │ (DuckDB events)│ │ (Streamlit)         │
        │ → verdict      │ │ → labels feed back  │
        └────────────────┘ └─────────────────────┘
```

11 services in Docker:
- **PostgreSQL 16** — source of truth (canonical records, linkage pairs, decisions)
- **OpenSearch 2.16** — inverted-index blocking on PAN, pin+name, trigrams
- **Neo4j 5.24** — Legal Entity → UBID hierarchy graph
- **Redis 7** — source_id → UBID hot-path cache
- **Kafka 7.7 (KRaft)** — stream queue for activity events
- **DuckDB + Parquet** — UBID-keyed event warehouse
- **Nominatim** — self-hosted OpenStreetMap geocoder
- **FastAPI + uvicorn** — REST API
- **Streamlit** — government-themed reviewer console
- **Worker** — Kafka consumer
- **Kafka UI / OpenSearch Dashboards** — operator inspection

For full justification of every component, see [`TECH_RATIONALE.md`](TECH_RATIONALE.md).

---

## Tech stack

### ML

- **LightGBM** — gradient-boosted decision trees for pairwise record matching
- **scikit-learn** — isotonic regression for probability calibration
- **SHAP** — per-pair feature contributions (every linkage decomposable)
- **rapidfuzz** — Jaro-Winkler, token-set ratio, Jaccard n-grams
- **indic-transliteration** — Kannada ↔ ITRANS Roman

### Backend

- **FastAPI + uvicorn** — async API
- **SQLAlchemy** — Postgres ORM
- **Pydantic** — typed schemas, request/response validation
- **confluent-kafka** — Kafka client
- **opensearch-py** — search client
- **neo4j** — graph driver
- **duckdb** — embedded analytical DB

### Frontend

- **Streamlit** — government-themed reviewer console
- **Plotly** — interactive charts (calibration, evidence timeline, retrain history)

---

## Performance metrics (measured)

Evaluated against `data/synthetic/ground_truth_links.csv` (60 ground-truth entities, 236 records):

| Metric | Value |
|---|---|
| Pairwise precision @ p ≥ 0.95 | **0.99** |
| Pairwise recall @ p ≥ 0.95 | 0.59 (synthetic-data limit) |
| Pairwise F1 @ p ≥ 0.95 | 0.74 |
| **Pairwise F1 @ p ≥ 0.70** | **0.91** |
| Brier score | **0.0086** |
| Expected Calibration Error (ECE) | **0.0132** (well-calibrated) |
| **B3 cluster F1** | **0.92** (vs 0.40 baseline without inline clustering) |
| **Verdict accuracy** | **0.82** (49 / 60 entities) |
| UBIDs predicted | 75 (vs 60 ground-truth — close) |
| Records linked | 267 across 5 sources |
| Events joined to UBIDs | 1944 / 1951 (7 quarantined intentionally) |

Reproduce these numbers yourself:

```bash
docker exec ubid_platform-ubid-api-1 python /app/scripts/evaluate.py
```

---

## Required: download the Karnataka OSM extract for Nominatim

> **The OSM data file (~126 MB) is NOT in this repo** because GitHub's per-file limit is 100 MB. Every operator must download it themselves. Without the file, Nominatim will fail to start and the geocoding feature degrades to the curated 42-locality dictionary (still functional, just less precise).

### Step 1 — Download the OSM extract

Pick **either** of these mirrors (both serve the same data):

| Mirror | URL |
|---|---|
| **OpenStreetMap France** ✅ recommended | <https://download.openstreetmap.fr/extracts/asia/india/karnataka-latest.osm.pbf> |
| Geofabrik (alternative) | <https://download.geofabrik.de/asia/india/karnataka-latest.osm.pbf> |

**File size:** ~126 MB. **Filename must be exactly:** `karnataka-latest.osm.pbf`.

```bash
# Linux / macOS
cd ubid_platform/nominatim_data
curl -O https://download.openstreetmap.fr/extracts/asia/india/karnataka-latest.osm.pbf
```

```powershell
# Windows PowerShell
cd ubid_platform\nominatim_data
Invoke-WebRequest -Uri "https://download.openstreetmap.fr/extracts/asia/india/karnataka-latest.osm.pbf" -OutFile "karnataka-latest.osm.pbf"
```

Or just **download in your browser** and save into `ubid_platform/nominatim_data/`.

### Step 2 — Verify the file landed

```bash
ls -lh ubid_platform/nominatim_data/karnataka-latest.osm.pbf
# → -rw-r--r--  1 user  staff   ~126M  ...
```

### Step 3 — Start / restart Nominatim

If the platform isn't running yet, the standard `docker compose up -d` will pick up the file. If it's already running:

```bash
docker compose up -d --force-recreate nominatim ubid-api
```

### Step 4 — Wait for the first-time import (10–30 minutes)

Nominatim imports the .pbf into its internal Postgres + PostGIS at first start. Watch progress:

```bash
docker logs -f ubid_platform-nominatim-1
```

You'll see lines like `Processed N nodes / ways / relations` ticking up, then the import completes and Nominatim begins serving requests.

### Step 5 — Backfill geocoding for already-ingested records

Once Nominatim is responding to queries:

```bash
docker exec ubid_platform-ubid-api-1 python /app/scripts/regeocode_with_nominatim.py
```

### Step 6 — Retrain so LightGBM picks up the improved coordinates

In the UI: <http://localhost:8501> → **⚙️ Admin** → **Retrain model** tab → click **Trigger retrain**.

For deeper instructions including troubleshooting, see [`ubid_platform/nominatim_data/README.md`](ubid_platform/nominatim_data/README.md).

---

## Skip the OSM download (degraded but working)

If you don't want to download 126 MB or wait for the import, the platform still runs fine — Nominatim will fail at startup (no .pbf), but every other service is independent and the geocoder falls back to a curated 42-locality coordinate dictionary covering the major Bengaluru / Karnataka localities.

To skip Nominatim entirely:

1. Comment out the `nominatim:` block in `docker-compose.yml` (lines ~178–193)
2. Comment out the `nominatim_db:` line in the `volumes:` section at the bottom
3. Remove `NOMINATIM_URL=http://nominatim:8080` from `.env`
4. `docker compose up -d`

The platform will still ingest, link, cluster, and produce verdicts. You'll lose ~1.5 points of pairwise F1 from the missing `addr_geo_distance_km` feature.

---

## Running scripts

Most operational scripts run inside the API container (so they share its DuckDB lock and module path):

```bash
# Ingest events from data/synthetic/events_stream.jsonl
docker exec ubid_platform-ubid-api-1 python /app/scripts/send_events.py

# Compute verdicts for every UBID
docker exec ubid_platform-ubid-api-1 python /app/scripts/compute_verdicts.py

# Re-train LightGBM scorer
docker exec ubid_platform-ubid-api-1 python /app/scripts/train_scorer.py

# Run full evaluation against ground truth
docker exec ubid_platform-ubid-api-1 python /app/scripts/evaluate.py

# A/B compare dict-only vs. Nominatim+dict geocoding
docker exec ubid_platform-ubid-api-1 python /app/scripts/compare_geocoding_modes.py

# Wipe all data (preserves model artefacts)
docker exec ubid_platform-ubid-api-1 python /app/scripts/wipe_data.py
```

After cloning, scripts may need to be copied into the container:

```bash
docker cp ubid_platform/scripts/. ubid_platform-ubid-api-1:/app/scripts/
```

---

## Reset and re-ingest

To wipe all data and start fresh:

```bash
docker exec ubid_platform-ubid-api-1 python /app/scripts/wipe_data.py
# Then repeat steps 5–7 from "Detailed setup" above
```

To remove all Docker volumes and rebuild from scratch (heavy):

```bash
docker compose down -v
docker compose up -d --build
```

---

## Troubleshooting

### "Cannot find package or service" — Docker Compose error
You're running `docker-compose` (the legacy V1 plugin). The project uses Compose V2:
```bash
docker compose version    # should print "Docker Compose version v2.x"
```
If you only have V1, install Docker Desktop or upgrade.

### "Connection refused" on port 8000
Wait — the API takes ~30s to start because it waits for Postgres + OpenSearch + Neo4j + Kafka health checks. Watch logs:
```bash
docker logs -f ubid_platform-ubid-api-1
```

### `curl` doesn't accept `-X` / `-F` (Windows PowerShell only)
Use `curl.exe` instead — PowerShell aliases `curl` to `Invoke-WebRequest`:
```powershell
curl.exe -X POST http://localhost:8000/api/v1/ingest/ekarmika/upload -F "file=@ekarmika_records.csv"
```

### Verdicts are all `closed_by_silence` with score 0
The events are dated 2023-11 → 2025-04 but today's `current_date` may be far past that. Use a reference date:
```bash
curl -X POST 'http://localhost:8000/api/v1/admin/verdicts/refresh?reference_date=2025-05-01'
```

### Nominatim container exits / OOM
Nominatim's import needs ≥ 2 GB RAM. Increase Docker Desktop's memory allocation. If the import was interrupted:
```bash
docker compose down nominatim
docker volume rm ubid_platform_nominatim_db
docker compose up -d nominatim
```

### Frontend changes not visible
Hard-refresh the browser (`Ctrl + Shift + R`). Streamlit caches the JS bundle in browser storage.

### Streamlit "duplicate plotly_chart key" error
Already fixed in the codebase — every `st.plotly_chart` call has a unique `key=`. If you hit this in your own additions, pass `key="some_unique_string"`.

### "DuckDB lock held by another process"
The API holds the DuckDB file open. Operations on DuckDB must run **inside the API container**, not from the host:
```bash
docker exec ubid_platform-ubid-api-1 python /app/scripts/<script>.py
```

For more bug history and fixes, see [`HANDOFF.md`](HANDOFF.md).

---

## Documentation index

| File | What's in it |
|---|---|
| [`README.md`](README.md) | This file — setup, tour, troubleshooting |
| [`HANDOFF.md`](HANDOFF.md) | Full project state, history, all bug fixes |
| [`IMPROVEMENTS.md`](IMPROVEMENTS.md) | Roadmap of next 20 features with effort estimates |
| [`TECH_RATIONALE.md`](TECH_RATIONALE.md) | Why each technology was chosen |
| [`PRESENTATION.md`](PRESENTATION.md) | Markdown presentation source (slide-by-slide) |
| [`presentation.html`](presentation.html) | Self-contained reveal.js slide deck — open in browser |
| [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) | 5-minute recording script with ML deep-dive |
| [`Problem_statement.md`](Problem_statement.md) | Original Theme-1 problem statement |
| [`UBID_Proposal.pdf`](UBID_Proposal.pdf) | Round-1 proposal document |
| [`karnataka_source_schemas.md`](karnataka_source_schemas.md) | Research on actual Karnataka department schemas |

---

## Synthetic data shape

The repo ships with synthetic CSVs that match the actual Karnataka schemas (researched in `karnataka_source_schemas.md`):

### `ekarmika_records.csv` — Karnataka Shop & Establishment
```
establishment_registration_no, name, address, nature_of_business,
date_of_commencement, pan, gstin, phone, email, employee_count
```

### `fbis_records.csv` — Department of Factories
```
licence_number, form2_registration_no, factory_name, address,
village_town, taluk, district, pin_code, nature_of_manufacturing,
nic_code, occupier_pan, gstin, phone, email, employee_count,
installed_hp, constitution_type, registration_date, licence_valid_until
```

### `kspcb_records.csv` — Karnataka State Pollution Control Board
```
consent_file_no, industry_name, industry_category, sector, nic_code,
industrial_area, taluk, district, pin_code, latitude, longitude,
pan, gstin, cin, phone, email, date_of_commissioning, valid_until
```

### `bescom_records.csv` — Bangalore Electricity Supply Company
```
rr_number, account_id, k_number, consumer_name, service_address,
tariff_category, sanctioned_load_kw, phone
```

### `bwssb_records.csv` — Bangalore Water Supply & Sewerage Board
```
knca_number, account_id, consumer_number, consumer_name,
service_address, tariff_category, connection_size_mm, phone
```

### `events_stream.jsonl` — Activity events
One JSON object per line:
```json
{"event_id": "<uuid>", "source_system": "bescom", "source_record_id": "RR-12345",
 "event_type": "bescom_bill_paid", "event_date": "2025-04-21", "metadata": {}}
```

### `ground_truth_links.csv` — Evaluation oracle
Maps each ground-truth entity to its source records across all systems. Used by `evaluate.py` to compute precision / recall / B3 / verdict accuracy.

---

## Sample queries to try in the UI

Once you're running, head to **❓ Query Explorer** and try:

1. **The exemplar:** Verdict = `active` · Source = `fbis` · No event of type = `fac_inspection` · In last `540` days
2. **Active in pin 560058:** Verdict = `active` · Pin = `560058`
3. **Dormants in Bengaluru Urban:** Verdict = `dormant` · District = `bengaluru urban`

Each query runs against the UBID-keyed event warehouse and returns a list of UBIDs with verdict, score, and supporting evidence — answers Karnataka C&I cannot get today.

---

## Stopping the platform

```bash
# Stop services but keep data
docker compose stop

# Stop services and remove containers (data persists in volumes)
docker compose down

# Stop and erase all data (volumes too)
docker compose down -v
```

---

## Need help?

1. **Check service health:** `docker ps --format "table {{.Names}}\t{{.Status}}"`
2. **Check API logs:** `docker logs -f ubid_platform-ubid-api-1`
3. **Check frontend logs:** `docker logs -f ubid_platform-ubid-frontend-1`
4. **Check the docs:** `HANDOFF.md` has every bug we encountered + the fix
5. **Restart a single service:** `docker compose restart <service-name>`
6. **Re-create with fresh env:** `docker compose up -d --force-recreate <service>`

---

## License & credits

Built for **AI for Bharat 2 Hackathon · Theme 1** by way of Karnataka Commerce & Industries.

Open-source dependencies and their licenses are listed in `requirements.txt`.

The Karnataka government emblem (Gandaberunda) used in the UI banner is the official state emblem; if you have rights to use the official artwork, drop it in `ubid_platform/frontend/assets/karnataka_logo.png` and the UI will use it automatically.

---

**Open the platform now: <http://localhost:8501>**
