# UBID Platform — Complete Session Handoff

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
`E:\AI_For_Bharat\Theme1\ubid_platform\`

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
