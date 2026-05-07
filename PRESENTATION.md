# Unified Business Identifier & Active Business Intelligence

**AI for Bharat 2 — Theme 1**
*A platform for Karnataka Commerce & Industries*

---

## The problem

Karnataka's business-facing regulatory landscape is served by **40+ State department systems** — Shop & Establishment, Factories, Labour, KSPCB, BESCOM, BWSSB, Fire, Food Safety, urban / rural local bodies.

**Each was built in isolation:**
- Own schema, own record IDs, own validation rules
- Business name and address are free text
- PAN and GSTIN only partially captured
- No reliable join key across systems
- Same business = different rows in different databases

**Result:** Karnataka C&I cannot today answer basic questions about its own industrial base — *how many businesses are operating, in what sectors, where, and with what recent activity.*

---

## Two coupled sub-problems

### Part A — Entity Resolution
Given master data from N State systems, automatically link records that refer to the same real-world business and assign each business a single **Unified Business Identifier (UBID)**.

### Part B — Activity Inference
Given a stream of activity events (inspections, renewals, bills, returns, compliance reports), infer for each UBID whether the business is currently **Active / Dormant / Closed**.

> **B is meaningless without A.** They're sequenced but mutually informing.

---

## Non-negotiables (from the brief)

| Constraint | Architectural consequence |
|---|---|
| No source-system changes | Federation layer; pull-based ingest only |
| Synthetic / scrambled data only | No memorising real entities; structural matching only |
| Every decision explainable + reversible | Two-tier scoring with SHAP; versioned linkage |
| Wrong merge > missed merge | Conservative auto-link threshold (0.95); cannot-link wins |
| No hosted-LLM calls on PII | All processing on-prem; no third-party APIs |

---

## System architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Karnataka source systems (read-only ingest)                     │
│  e-Karmika · FBIS · KSPCB · BESCOM · BWSSB · …                   │
└───────────────────────────┬──────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Source adapters → Canonicalise → Block → Score → Cluster        │
│  ────────────────────────────────────────────────────────────    │
│   (Python)         (rapidfuzz +     (OpenSearch)  (LightGBM +    │
│                     dictionaries)                  isotonic)     │
└───────────────────────────┬──────────────────────────────────────┘
                            ▼
                ┌──────────────────────┐
                │   UBID Graph (Neo4j) │
                │  Legal Entity → UBID │
                │  → Source Records    │
                │  → Connection IDs    │
                └────┬───────────┬─────┘
                     │           │
                     ▼           ▼
        ┌────────────────┐ ┌─────────────────────┐
        │ Activity engine│ │ Reviewer console    │
        │ (DuckDB events)│ │ (Streamlit + API)   │
        │ → verdict      │ │ → confirm / reject  │
        └────────────────┘ │ → must-link / split │
                           │ → labels feed back  │
                           └─────────────────────┘
```

---

## Tech stack

### Infrastructure (Docker Compose, 11 services)

| Service | Why |
|---|---|
| **PostgreSQL 16** | Source of truth for canonical records, linkage pairs, constraints |
| **OpenSearch 2.16** | Inverted-index blocking on PAN, pin+name soundex, trigrams |
| **Neo4j 5.24** | Legal Entity → UBID → Source Records hierarchy graph |
| **Redis 7** | source_id → UBID hot-path cache, verdict cache |
| **Kafka 7.7 (KRaft)** | Stream ingestion of activity events |
| **DuckDB + Parquet** | UBID-keyed event warehouse (analytical queries) |
| **Nominatim** (self-hosted) | OpenStreetMap geocoder, on-prem |

### Backend

- **FastAPI + uvicorn** — REST API
- **SQLAlchemy** — ORM
- **pydantic** — typed schemas

### ML

- **LightGBM** — pairwise scorer
- **scikit-learn** — isotonic calibration
- **SHAP** — per-pair feature contributions
- **rapidfuzz** — Jaro-Winkler, token-set ratio, Jaccard n-grams
- **indic-transliteration** — Kannada ↔ Roman

### Frontend

- **Streamlit** — Government-themed reviewer console
- **Plotly** — calibration / distribution / timeline charts

---

## Why LightGBM?

We considered Fellegi-Sunter (classical probabilistic record linkage) and pure rule-based systems. LightGBM won because:

| Reason | Detail |
|---|---|
| **Mixed features** | Native handling of continuous, binary, and categorical features without dummy-encoding |
| **Per-pair SHAP** | Every linkage decision decomposes into "these features pushed up, those pushed down" — passes a procurement review |
| **Fast inference** | Sub-millisecond per pair at scale |
| **Small data friendly** | Trains well on the synthetic data sandbox (1700 labelled pairs) |
| **No feature-independence assumption** | Fellegi-Sunter assumes name-similarity and address-similarity are independent; they're not |

---

## The 25-feature vector

Five groups, each captures a different signal type:

### Name (5 features)
- Jaro-Winkler · token-set ratio · Jaccard trigram · LCS ratio · exact-after-legal-form-stripped

### Address (6 features)
- Pin equality · door equality · locality canonical match · cross-numbering distance · Levenshtein on residual · **geographic distance (km)** ← Nominatim-powered

### Identifier (4 features)
- GSTIN equality · phone equality · email-domain match · PAN agreement (cross GSTIN)

### Structural (4 features)
- Sector NIC compatibility · legal-form compatibility · log employee-ratio · log registration-date diff

### Blocking (6 features)
- Shared PAN · shared derived PAN · shared pin+name · shared pin+door · shared phone · n shared blocks

> **No neural embeddings.** Bengaluru-specific business vocabulary is poorly represented in pretrained multilingual models. Probabilistic string distances give us decomposable, defensible features.

---

## Two-tier scoring

### Deterministic tier (auto-decides 30–50% of cases)

```
if PAN(a) == PAN(b) and pin(a) == pin(b):
    → match (probability 1.0)
if PAN(a) ≠ PAN(b) and both non-null:
    → non-match (probability 0.0)
```

The brief: PAN agreement + soft-stop on conflicts.
Easy to explain to a reviewer ("these share PAN ABCDE1234F").

### Probabilistic tier (LightGBM + isotonic)

For everything else: 25-feature vector → LightGBM → raw score → isotonic calibrator → calibrated probability.

---

## Why isotonic calibration?

A raw boosted-tree score is **not a probability**. We need a calibrated probability so the auto-link / review / reject thresholds have meaning.

Isotonic regression:
- Non-parametric (handles non-linear miscalibration typical of GBMs)
- Monotonic by construction
- Trained on a held-out validation set
- Refreshable as drift accumulates

> **Live measurements:** Brier score = **0.0086**, ECE = **0.0132** → "well calibrated" by every standard.

---

## Threshold decision rule

```
calibrated probability p:

  p ≥ 0.95            → AUTO-LINK
  0.55 ≤ p < 0.95     → REVIEW QUEUE  (human decides)
  p < 0.55            → REJECT (keep separate)
```

The auto-link threshold is **conservative** — wrong merge > missed merge. Reviewer queue length is the price of safety, and we keep it manageable with active-learning ordering.

---

## Inline clustering — the single biggest fix

For each new record:
1. Block (find candidates)
2. Score (LightGBM probability)
3. **Union-find** over auto-linked pairs (this batch + historical) respecting cannot-link constraints
4. Each connected component = one UBID
5. Merge multiple existing UBIDs if a new record connects them

> **Lift:** B3 F1 from **0.40 → 0.92** vs. the baseline (one UBID per record).

---

## Activity engine — cadence-aware decay

Each event type has a **weight** w and a **cadence** τ.

```
contribution(t)  =  w · exp( -Δt / α·τ )
```

| Event | w | τ (days) |
|---|---|---|
| BESCOM bill paid | 0.9 | 30 |
| Factory Form 20 (annual return) | 0.8 | 365 |
| KSPCB CFO renewal | 0.9 | varies |
| S&E renewal pre-2019 | 0.7 | 1825 |
| BESCOM zero consumption | -0.4 | 30 |

Continuity score S = Σ contributions. Verdict bands: S ≥ 1.5 = Active, 0.15 ≤ S < 1.5 = Dormant, else Closed-by-silence. Plus deterministic overrides for closure events.

> **Sector-aware:** seasonal sectors (event halls, fireworks) widen the Dormant band so a wedding hall stays Dormant in winter, not Closed.

---

## Reviewer workflow

### 4 decision types in the queue
- **Confirm match** → must-link constraint + positive training label
- **Reject** → cannot-link constraint + negative training label + split if currently merged
- **Defer to senior** → priority boost
- **Flag quality** → mark source record for data-quality review

### Sorting Mat (audit merges page)
For multi-record UBIDs (40+ records possible at production scale):
- Sort each record into Group A / B / C / Solo via dropdowns
- Live preview of resulting UBIDs and constraints
- One submit click → atomic regroup with hundreds of constraint writes

### Two-tier reviewer structure
- **Junior** — routine ambiguity (5–10 min per case)
- **Senior** — escalations, policy-setting cases. Decisions become precedent (must-link / cannot-link constraints).

---

## Active-learning loop

Every reviewer decision is a labelled pair → `training_labels` table.

1. **Periodic retrain** — `/admin/retrain` re-fits LightGBM + recalibrates isotonic
2. **A/B against previous model** — pre / post Brier, ECE, F1 reported every run
3. **Retrain history** chart in Admin shows model improvement over time
4. **Constraint propagation** — must-link / cannot-link survive future re-clusterings
5. **Synonym dictionary updates** — reviewer-confirmed locality matches grow the dict
6. **Smart re-score** — after retrain, re-score only review-queue + boundary pairs (10 ms × 1000 = 10 s) instead of all linkage_pairs (could be hours at scale)

---

## Self-hosted Nominatim — the geocoder

Why **self-hosted** rather than Google / HERE:
- The proposal forbids hosted-API calls on PII addresses
- Nominatim runs in Docker, uses OpenStreetMap data
- Free, on-prem, no rate limits

How it plugs in:
1. Adapter parses address → canonical record
2. Geocoder asks Nominatim for `(lat, lng)` of the address
3. Falls back to a curated Bengaluru-locality dictionary (42 localities + 24 pin codes) if Nominatim misses
4. Coordinates feed the `addr_geo_distance_km` feature

**A/B comparison (dict-only vs. Nominatim+dict):**
- Recall ↑ +1.9 pts (57.4% → 59.3%)
- F1 ↑ +1.5 pts (0.727 → 0.743)
- Distinct geo-distances seen by model: 102 → 166

`addr_geo_distance_km` ranks **5th out of 25 features by importance** in the trained model.

> *Synthetic addresses limit the lift; in production with real addresses, expect 5–8× improvement.*

---

## 5th adapter — BWSSB (water supply)

Proves the "adding a new source is just one adapter file" claim from the proposal:

1. Add `BWSSB = "bwssb"` to `SourceSystem` enum
2. Create `src/ubid/ingest/bwssb_adapter.py` (114 lines, modelled on BESCOM)
3. Register in `_ADAPTERS` dict
4. Add 5 new event types to `EventType` enum
5. Add 5 signal configs (slightly lower weight than BESCOM)

**Zero changes** to scoring, blocking, clustering, verdict engine, or reviewer code.

Live result: **31 BWSSB connections ingested, 28 auto-linked into existing UBIDs by address; 643 events joined.**

---

## Quarantine queue

Activity events arrive keyed by source-system identifiers. Some can't be joined (source record not yet ingested, or below auto-link threshold).

**These events go to a quarantine queue, indexed by source identifier, and re-played whenever the linkage table updates.**

Never silently dropped. Top-level dashboard metric.

---

## Reversibility — every decision is undoable

Three operations the platform exposes:
1. **Unmerge** (in Activity Status) — split one record off a UBID into a new UBID + cannot-link
2. **Sorting Mat** (in Audit Merges) — split N records into K sub-clusters in one transaction
3. **Reject** (in Review Queue) — write cannot-link, split if currently merged

Every operation is logged in `reviewer_decisions` and `linkage_constraints`. The Audit Trail page shows the full history per UBID.

---

## Final platform metrics

Measured against `data/synthetic/ground_truth_links.csv` (60 entities, 236 records):

| Metric | Value |
|---|---|
| Pairwise precision @ p ≥ 0.95 | **0.99** |
| Pairwise recall @ p ≥ 0.95 | **0.59** (synthetic data limit) |
| Pairwise F1 @ p ≥ 0.95 | **0.74** |
| Pairwise F1 @ p ≥ 0.70 | **0.91** |
| **B3 cluster F1** | **0.92** |
| Brier score | **0.0086** |
| ECE | **0.0132** (well-calibrated) |
| **Verdict accuracy** | **0.82** (49 / 60 entities) |
| Predicted UBIDs | 75 (vs. 60 ground-truth entities) |

**B3 F1 went from 0.40 (no inline clustering) → 0.92 (with inline clustering + reviewer feedback).**

---

## Frontend — 12 pages, government-themed

| Page | Purpose |
|---|---|
| 📊 Dashboard | Live metrics + verdict distribution + calibration chart |
| 🔍 Browse UBIDs | Filterable, paginated UBID grid with CSV export |
| 📋 Review Queue | Pending pairs, SHAP per pair, bulk actions |
| 🧐 Audit Merges | Sorting Mat + record comparison + group decision |
| 🧭 UBID Lookup | Resolve any source ID / PAN / name+pin → UBID |
| 📈 Activity Status | One UBID's verdict, evidence timeline, audit trail, unmerge |
| 🚧 Quarantine | Stuck events + retry |
| 📜 Reviewer Log | Decision history + per-reviewer leaderboard |
| ❓ Query Explorer | Run analytical queries (the exemplar) |
| 📤 Ingest Data | CSV upload + JSONL events |
| ⚙️ Admin | Retrain · re-score · calibration · synonyms · verdicts |
| ℹ️ About | Architecture · live metrics · proposal compliance · glossary |

UI: bilingual (English + Kannada) header with Karnataka emblem · saffron + India-green tricolor accents · pill-style nav · help-tooltip toggle.

---

## The exemplar query

> *"Active factories in pin code 560058 with no inspection in the last 18 months."*

Today this is **impossible** in Karnataka. Factories live in FBIS, inspections in another DB, no join key.

With the platform: **one POST to `/api/v1/query/active-businesses`** returns a list of UBIDs with verdict, score, and supporting evidence.

---

## Risks we explicitly addressed

| Risk | Mitigation |
|---|---|
| BESCOM consumer name = landlord, not business | Risk flag + address-only matching with raised threshold |
| Wrong merge corrupts events for two businesses | Conservative auto-link, cannot-link constraints, reversibility |
| Reviewer bottleneck | Active-learning queue ordering, bulk decisions |
| Calibration drift | Reliability diagrams refreshed weekly, retrain history chart |
| Schema drift in source systems | Adapters validate canonical schema, fail loudly |
| Pre-PAN-mandate records | Soft-match with raised threshold, address-driven |
| Multi-state legal entity | Embedded PAN extracted from GSTIN; one Legal Entity, one UBID per state |

---

## What's still future work

- Real Kafka wiring for activity events (currently synchronous HTTP)
- Authentication (basic auth + role-based access)
- Drift monitoring chart (calibration over time, feature distribution drift)
- Time-travel view (any UBID, any past date)
- Webhook notifications for verdict changes
- More adapters (the architecture is designed for 40+ — we proved it with 5)

---

## Demo flow (live walkthrough)

1. Open **Dashboard** — system health, verdict distribution, calibration
2. Click any UBID in **Browse** → land on **Activity Status** with full lineage
3. Open **Review Queue** → confirm/reject a pair → watch the UBID merge in real time
4. Open **Audit Merges** → use the Sorting Mat on a 6-record cluster → split off a wrong record
5. Open **Admin → Retrain** → trigger retrain → see history chart updated
6. Open **Query Explorer** → run the exemplar → see live results

Every step shows: data flowing, model deciding, reviewer correcting, model learning.

---

## Thank you

**Codebase:** `c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ubid_platform\`
**Docs:** `HANDOFF.md` (project state) · `IMPROVEMENTS.md` (roadmap)
**API:** http://localhost:8000/docs
**UI:** http://localhost:8501
