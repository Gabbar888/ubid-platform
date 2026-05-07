# Tech rationale — why each piece of the stack

> A proper justification for every component in the platform. Lives next to `HANDOFF.md`, `IMPROVEMENTS.md`, `PRESENTATION.md`, `DEMO_SCRIPT.md`.

The platform runs **11 services** in Docker Compose. Each one earns its place by solving a problem the others can't. This document explains exactly which problem and why.

---

## Storage layer — 5 databases? Yes, deliberately.

A common eyebrow-raise: "Why do you have Postgres AND OpenSearch AND Neo4j AND DuckDB AND Redis?" Each one solves a problem the others physically cannot at the access patterns we need.

### 1. PostgreSQL 16 — source of truth (transactional, relational)

**What it stores:** canonical_records, ubid_nodes, ubid_source_links, linkage_pairs, linkage_constraints, reviewer_decisions, reviewer_queue, training_labels, activity_verdicts, retrain_runs, quarantine_events.

**Why Postgres:**

- **ACID transactions** — when a reviewer confirms a match, we need: write decision row + write constraint + write training label + update queue status, atomically. Either all 5 happen or none do. NoSQL alternatives like MongoDB don't give multi-document transactions cheaply.
- **Strong typing + foreign keys** — `ubid_source_links.canonical_id` REFERENCES `canonical_records.canonical_id`. Schema enforces invariants; we caught half the bugs in HANDOFF.md *because* Postgres complained loudly when our code drifted.
- **JSONB columns where flexibility matters** — `feature_vector`, `evidence_timeline`, `metadata` are JSON-schema'd inside relational rows. Best of both worlds.
- **SQLAlchemy ecosystem** — mature ORM, well-documented, supports temporal tables for versioned writes.
- **Boring, mature, government-procurable** — every State PSU runs Postgres. Procurement won't blink.

**What we considered and rejected:**

| Alternative | Why we rejected it |
|---|---|
| MySQL | No JSONB. Weaker FK enforcement. |
| MongoDB | Multi-document transactions are expensive and recent. Schema-less drift would bite us. |
| SQLite | Single-writer doesn't fit Kafka consumer + API serving the same DB. |

### 2. OpenSearch 2.16 — inverted-index blocking

**What it stores:** an index of every canonical record, with structured fields for blocking keys (PAN, derived_PAN, pin+name_soundex, pin+door, phone) plus a trigram-analysed `name_normalized` field.

**Why OpenSearch (and not Postgres for this):**

The blocking step asks: *"For this new record, find every other record that shares any of these 6 keys — even fuzzy ones."*

Postgres can do this with `GIN` indexes and `pg_trgm`, but:
- Each blocking-key index is a separate B-tree → query planner picks one
- Multi-key UNION queries become expensive joins
- Trigram similarity in Postgres is slow (it scans the candidate set)

OpenSearch gives us:
- **Inverted indexes natively** — every blocking key is its own posting list, lookups are O(1) in the term dictionary
- **Built-in fuzzy / phonetic / trigram analyzers** — `match` query with `minimum_should_match=60%` returns candidates in microseconds
- **Union of conditions** is the idiomatic `should` clause — exactly what union-blocking needs
- **Scales to millions of records** — was the whole point of the design

**What we considered:**

| Alternative | Why we rejected it |
|---|---|
| Postgres pg_trgm | Slow at scale. ~50ms per record at 100K records. Linear with collection size. |
| Elasticsearch | OpenSearch is the AWS-forked open-source version. Same engine, no licensing complications. |
| Vespa | Overkill for blocking. Hard to operate. |
| Custom inverted index | Reinventing the wheel. |

### 3. Neo4j 5.24 — graph relationships (Legal Entity hierarchy)

**What it stores:** the proposal's three-layer hierarchy as a graph:

```
LegalEntity (anchored to PAN)
   └── owns ──► UBID (one per establishment)
                  └── linked_to ──► SourceRecord (per department row)
                                       └── infrastructure ──► BescomConnection / BwssbConnection
```

Plus must-link / cannot-link constraint edges between SourceRecord nodes.

**Why Neo4j (and not Postgres):**

The data model is **fundamentally graph-shaped**. Postgres CAN store it (parent FK columns + recursive CTEs), but:

- "Show me every source record belonging to the same legal entity as record X" → recursive CTE in Postgres, **one Cypher line** in Neo4j: `MATCH (le:LegalEntity)<-[:OWNED_BY*]-(r) WHERE r.id = $id RETURN r`
- Multi-state legal entity (one PAN, GSTINs in 5 states) requires walking up to LegalEntity then down through all UBIDs in different states. Graph traversal is O(edges); SQL recursive CTE is exponential in worst case.
- Constraint propagation — "transitively close the must-links" — is `MATCH p=(a)-[:MUST_LINK*]-(b)` in Cypher; in SQL it's a UNION ALL nightmare.

**Honest disclosure:** at hackathon-scale (75 UBIDs) most queries still go to Postgres. Neo4j becomes load-bearing at production scale (10M records) where:
- Cross-state legal entity queries
- "Who did this reviewer also review?" social-graph queries
- Constraint-propagation visualisations

**What we considered:**

| Alternative | Why we rejected it |
|---|---|
| Postgres with recursive CTEs | Works at scale ≤10K but query plans degrade. Hard to write. |
| Amazon Neptune | Vendor lock-in. Can't run on-prem. |
| In-memory NetworkX | Doesn't survive process restart. Doesn't scale past RAM. |
| ArangoDB | Graph + document, but Neo4j has stronger Cypher tooling. |

### 4. Redis 7 — hot-path cache

**What it stores:** `source_id → UBID` mapping (TTL 1 hour), verdict cache per UBID (TTL 5 min).

**Why Redis (and not Postgres):**

When an event comes in keyed by `bescom/9059120456`, we need to know its UBID **fast** to write it to the right partition. Postgres can do this with a B-tree index — **~1ms** per lookup. Redis does it in **~50µs**. At 10K events/sec that 20× speedup is the difference between fitting in one machine and needing a fleet.

Plus:
- **TTL-based invalidation** — write a UBID assignment, set TTL, let Redis garbage-collect. Postgres needs application-level expiry.
- **Atomic compare-and-swap** for the merge case (UBID A becomes UBID B → invalidate every cached source_id pointing at A).

**What we considered:**
- **In-process LRU cache** — doesn't share state across API replicas. As soon as we run 2 API containers we'd serve stale.
- **Memcached** — no persistence, no TTL on individual keys without ttl tier; Redis is strictly better.

### 5. DuckDB + Parquet — UBID-keyed event warehouse

**What it stores:** every activity event, partitioned by month, written in append-only Parquet on disk. Indexed by `(ubid, event_date)`.

**Why DuckDB (and not Postgres):**

Activity events at 10M-record scale could be ~100M+ events/year. Putting that in Postgres works but:
- Every analytical query (`"sum decayed contributions for UBID X"`) scans many rows
- Bloats the OLTP database with read-heavy workload
- Vacuum / autovacuum tuning becomes a thing

DuckDB is **columnar OLAP embedded in the API process** (no separate server):
- ~10× faster than Postgres on `SUM`/`AVG`/`GROUP BY`
- Reads Parquet files directly; cheap to back up (just copy the file)
- Embedded means no network hop for the activity engine
- One file = one warehouse; can be moved between machines trivially

**What we considered:**

| Alternative | Why we rejected it |
|---|---|
| Postgres for everything | Mixed OLTP+OLAP workload kills both. |
| ClickHouse | Excellent at scale but heavier to operate; overkill for hackathon. |
| BigQuery | Cloud-only, vendor lock-in, latency. |
| Plain Parquet + pandas | Pandas doesn't have predicate pushdown. DuckDB does. |

### 6. Kafka 7.7 (KRaft mode, no Zookeeper) — stream queue

**What it carries:** activity events from each source system arriving as a stream (`ubid.events.activity`), reviewer decisions (`ubid.review.decisions`), source-record updates (`ubid.source.records`), quarantine retries.

**Why Kafka:**

The proposal explicitly mentions stream-subscription ingestion as the production path. Activity events from 40 source systems, each producing 30-day-cadence bills, return forms, compliance reports → millions of events per day at scale. We need:
- **Decoupling** — source-system ingest cadence ≠ consumer cadence
- **Replay** — quarantine events get re-tried automatically when linkage updates
- **Durability** — events survive consumer crashes
- **Ordering** — per-source-record events arrive in order
- **Backpressure** — bursty ingestion (end-of-month bills) doesn't blow up the consumer

KRaft mode means no Zookeeper — modern Kafka deployment with one fewer moving part.

**What we considered:**

| Alternative | Why we rejected it |
|---|---|
| RabbitMQ | Per-message ack semantics are nice but no log retention; can't replay. |
| Postgres LISTEN/NOTIFY | Doesn't survive consumer restart. No replay. |
| Direct HTTP webhooks | No durability, no backpressure. |
| Pulsar | Kafka has much wider operator familiarity in India. |

> **Honest note:** at hackathon scale we currently bypass Kafka for the simple `/api/v1/events` endpoint. The Kafka producer + consumer worker are wired and running but used mainly for the source-record topic. Real production would route activity events through Kafka. This is in `IMPROVEMENTS.md` item #14 as a known gap.

### 7. Nominatim (self-hosted) — OpenStreetMap geocoder

**What it does:** turns "Plot 23, Whitefield, Bangalore" into `(12.9698, 77.7500)`.

**Why self-hosted Nominatim:**

The proposal explicitly forbids hosted geocoders (Google Maps, HERE) because:
- Ships State PII addresses to a third-party cloud
- Google's terms restrict long-term storage of geocoded outputs (incompatible with persistent UBID-anchored coordinates)
- Indian coverage in Google's offerings is patchy / pre-GA

Nominatim:
- **Open-source** (BSD license) — runs in our Docker stack
- **Uses OpenStreetMap data** — free, well-curated for India
- **No per-call costs** — no rate limits, no quotas
- **All data stays on-prem** — proposal-compliant

The `addr_geo_distance_km` feature is the 5th-most-important feature in the trained model — measurable contribution to recall. See A/B comparison in `IMPROVEMENTS.md` ✅ #6.

**What we considered:**
- **Google Maps API** — proposal violation
- **Mapbox** — same restriction
- **OpenCage** — better coverage but pay-per-call, network egress

---

## Pipeline / API layer

### FastAPI + uvicorn

**Why:**
- **Async-first** — handles concurrent requests without thread-pool tuning
- **Pydantic-native** — request/response validation comes free, errors are typed
- **Auto-generated OpenAPI docs** — `/docs` works out of the box, judges can poke it
- **Type hints throughout** — IDE autocomplete + mypy-friendly

**What we considered:**
- Flask — older, no async, no automatic docs
- Django — too much for an API-only service
- aiohttp — lower-level, would write our own request validation

### SQLAlchemy ORM

**Why:**
- Postgres ORM that understands JSONB, foreign keys, transactions
- The standard in the Python ecosystem — every Postgres library/tutorial assumes it
- Lets us mix raw SQL (for performance-critical aggregates) with ORM patterns (for transaction boundaries)

### Pydantic — typed schemas

**Why:**
- Every API request/response is a typed Pydantic model
- Validation at the boundary — bad data gets rejected at the door, not deep in business logic
- The same models double as ORM-input adapters

---

## ML stack

### LightGBM — pairwise scorer

Already covered in detail in `DEMO_SCRIPT.md`. Summary:
- **Gradient-boosted trees** beat linear classifiers on heterogeneous tabular features and beat neural nets on small data
- **Native handling of mixed feature types** (continuous, binary, categorical, missing-values)
- **Fast inference** — sub-millisecond per pair
- **SHAP-explainable** — every decision is decomposable
- We rejected **Fellegi-Sunter** (assumes feature independence; ours are correlated) and **neural embeddings** (poor Indic vocab coverage; opaque)

### scikit-learn — isotonic regression for calibration

**Why:**
- LightGBM raw scores are **not probabilities** — calibration is essential
- Isotonic is **non-parametric** — no assumption about how the miscalibration shape looks
- Monotonic by construction — preserves the score ranking
- Live measurements: Brier 0.009, ECE 0.013 (well-calibrated)

**What we considered:**
- Platt scaling (logistic regression on raw scores) — assumes sigmoid shape; fails for skewed distributions
- Beta calibration — better for boosted trees but more parameters to tune

### SHAP — per-pair feature contributions

**Why:**
- The proposal demands every linkage decision be **explainable to a human reviewer**
- SHAP gives us "this feature pushed score up by +0.18, that feature pushed it down by -0.12" — exactly the breakdown a reviewer needs
- Visible in the Review Queue and Audit Merges UIs as horizontal bar charts

**Without SHAP** the model is a black box and the proposal's explainability requirement fails.

### rapidfuzz — string distance algorithms

**Why:**
- Drop-in replacement for `fuzzywuzzy` but **C-implemented** → 10× faster
- Implements Jaro-Winkler, token_set_ratio, Levenshtein, Jaccard — all the name-comparison primitives we need
- No external services required — pure Python install

### indic-transliteration — Kannada ↔ Roman

**Why:**
- Karnataka S&E records often carry Kannada-script name boards (mandatory under Rule 24-A)
- "Sharma Traders" and its Kannada equivalent must block together
- Open-source library; runs locally; no third-party calls
- Deterministic transliteration → reproducible canonicalisation

**How it's wired:**
`src/ubid/canonicalize/name_normalizer.py` detects Kannada-script characters (Unicode block U+0C80–U+0CFF) and transliterates to ITRANS Roman before the rest of the canonicalisation pipeline runs. The library is in `requirements.txt` and the import is gated with a try/except so the platform survives if it's missing.

> **Honest caveat:** our synthetic CSVs are all Roman-script — they don't contain Kannada names — so this code path is wired but **not actually exercised on the live demo data.** It's tested with manual inputs only. Real Karnataka S&E ingest in production will exercise it heavily.

---

## Frontend layer

### Streamlit — reviewer console

**Why:**
- **Pure Python** — no separate JavaScript build pipeline, no React state management, no API client to hand-write
- **Built-in widgets** match the reviewer-workflow needs (data_editor, selectbox, file_uploader, plotly_chart)
- **Auto-rerun on interaction** — every reviewer click re-fetches fresh data without explicit websocket handling
- **Session state** — preserves selections across page navigation
- Government back-office tool, not consumer-facing — Streamlit's "fast to build, looks decent enough" trade-off is correct

**What we considered:**

| Alternative | Why we rejected it |
|---|---|
| React + FastAPI | 5× the development time. State management ceremony. |
| Dash | Slower than Streamlit for similar power; less momentum. |
| Plain HTML + jQuery | We'd be writing our own widget library. |

### Plotly — charts

**Why:**
- Interactive (hover tooltips, zoom, pan) without per-chart JS
- Plays well with Streamlit (`st.plotly_chart`)
- Government-themed easily via the template system we set up (`pio.templates`)
- Full feature set — donuts, scatter, bars, calibration plots — one library

---

## Orchestration

### Docker Compose

**Why:**
- One file (`docker-compose.yml`) defines all 11 services with their networking
- One command (`docker compose up`) starts the whole platform
- Lifecycle commands are uniform (`docker compose restart ubid-api`)
- Operators new to the project get to a working stack in minutes, not hours

**What we considered:**
- **Kubernetes** — overkill for hackathon; production migration is straightforward (kompose tool exists)
- **Bash setup scripts** — fragile, OS-dependent

---

## What we deliberately did NOT pick

Worth flagging because absence is itself a choice:

| Tool | Why not |
|---|---|
| **Hosted LLMs (GPT, Claude, Gemini)** | Proposal forbids sending PII to hosted APIs. Plus opaque — fails explainability bar. |
| **Spark / Hadoop** | Overkill; our scale fits one box. Adding a JVM cluster adds operational burden. |
| **Airflow / Prefect** | We have ~5 cron-style jobs (retrain, refresh-verdicts, geocoding). Plain scheduled scripts work; orchestrator complexity not yet justified. |
| **Sentry / Datadog** | Monitoring matters in production but not at hackathon scale. Loguru is enough. |
| **Auth0 / Keycloak** | Authentication is on the IMPROVEMENTS list (#10). Hardcoded reviewer ID is fine for the demo. |
| **Vault / AWS Secrets Manager** | `.env` file is acceptable for hackathon. Production needs secrets management — known gap. |
| **CI/CD (GitHub Actions, etc.)** | Single-developer hackathon. No CI needed yet. |
| **Real OAuth federation** | One state government, one platform — no federated identity story for now. |

---

## The honest summary

If a judge asks "**why so many databases?**" the one-liner is:

> *Each of our 5 storage layers solves a problem the others physically cannot at the access patterns we need. Postgres is the source of truth. OpenSearch handles million-record inverted-index blocking that Postgres can't do fast. Neo4j handles the legal-entity hierarchy and constraint graph that's awkward in SQL. Redis handles the 50-µs hot-path cache that Postgres can't match. DuckDB handles the columnar analytics that would otherwise crush the OLTP database. Each is on-prem, open-source, and operationally well-understood.*

If they ask "**why not just use Postgres for everything?**" the one-liner is:

> *We could and we did try mentally — but the workload mixes OLTP transactions, full-text/fuzzy search, graph traversal, columnar analytics, and a stream queue. Postgres is good at the first one and acceptable at the others; specialised stores are 10–50× faster on the workloads they were designed for. The cost of running 5 services in Docker is one config file. The benefit is sub-millisecond response times across all access patterns at scale.*
