# Karnataka UBID Platform — Model Description

**AI for Bharat 2 Hackathon · Theme 1 · Department of Commerce & Industries**

This document describes the core ML system that solves two problems in a single pipeline: **federated entity resolution** (assigning a Unified Business Identifier across departmental record systems) and **active business inference** (determining whether a business is currently operating, dormant, or closed from multi-source temporal evidence). Every design choice below is implemented in the submitted codebase and is verified by the held-out evaluation harness.

---

## 1. The problem

Karnataka has 40+ State department systems that each hold a partial view of every business operating in the State. The same firm appears as different rows in:

- **e-Karmika** (Shops & Establishments registration)
- **FBIS** (Factories Inspectorate)
- **KSPCB** (Pollution Control Board consent files)
- **BESCOM** (Electricity meter and billing)
- **BWSSB** (Water supply connection — fifth source added to demonstrate pluggability)

The same business is recorded as `SHARMA TRADERS PVT LTD` on one system, `M/s Sharma Trdrs` on another, `ಶರ್ಮಾ ಟ್ರೇಡರ್ಸ್` (Kannada) on a third, with addresses that differ by phrasing, abbreviation, or precision. There is no shared key. Joining records by exact match misses ~60 % of true links, and joining by name similarity alone produces 30 %+ false-positive merges that contaminate every downstream query.

The platform produces, from these federated feeds:

1. **A UBID** — a stable internal identifier that points to one real-world business and is back-linked to every contributing source record.
2. **An activity verdict** — Active / Dormant / Closed / Closed-by-silence / Nascent — derived from the temporal pattern of events across all sources, not a single registry's status field.

Both outputs are reversible, attributable to a reviewer, and explainable down to the feature-contribution level.

---

## 2. System overview

```
        ┌─────────────────────┐  ┌──────────────────────────┐
Source  │ 5 source adapters   │  │ Cleansing + canonicalize │
records │ (CSV / streaming)   │→ │  • name normalize        │
        └─────────────────────┘  │  • Kannada↔Roman trans-  │
                                 │    literation            │
                                 │  • address canonical +   │
                                 │    geocode (Nominatim)   │
                                 └────────────┬─────────────┘
                                              ↓
                              ┌──────────────────────────┐
                              │ Blocking — OpenSearch    │
                              │ (pin, district, name     │
                              │  prefix, identifier)     │
                              └────────────┬─────────────┘
                                           ↓
                              ┌──────────────────────────┐
                              │ Pairwise feature vector  │
                              │  25 features × 5 groups  │
                              └────────────┬─────────────┘
                                           ↓
            Tier-1 deterministic ┌─────────┴──────────┐  Tier-2 probabilistic
              PAN equality ──────┤                    ├── LightGBM + isotonic
                                 │ score(record_a,    │
                                 │       record_b)    │
                                 └─────────┬──────────┘
                                           ↓
                              ┌──────────────────────────┐
                              │ Union-find clustering    │
                              │ + must-link / cannot-    │
                              │   link constraints       │
                              └────────────┬─────────────┘
                                           ↓
                                       UBIDs
                                           ↓
                              ┌──────────────────────────┐
                              │ Activity events keyed by │
                              │ UBID — DuckDB warehouse  │
                              └────────────┬─────────────┘
                                           ↓
                              ┌──────────────────────────┐
                              │ Cadence-aware decay →    │
                              │   continuity score S →   │
                              │   verdict                │
                              └──────────────────────────┘
```

The two ML tracks (resolution and activity) are deliberately separated — they have different update cadences, different evaluation metrics, and different failure modes. The UBID is the join key that makes activity inference possible at all.

---

## 3. Track 1 — Entity resolution (UBID assignment)

### 3.1 Two-tier scoring

Every candidate pair `(record_a, record_b)` gets one of two scores:

**Tier 1 — deterministic.** If both records carry a non-null PAN (Permanent Account Number, the Indian tax-authority identifier) and they are equal, the pair is auto-merged. PAN is unique to a legal entity by construction. This tier resolves ~25 % of true links at zero risk and removes them from the probabilistic queue.

**Tier 2 — probabilistic.** Every other pair is scored by a calibrated LightGBM model. The model output is a probability `p(match | features)` in `[0, 1]`, which feeds three thresholds:

- `p ≥ 0.95` → auto-merge (high-confidence)
- `0.55 ≤ p < 0.95` → reviewer queue (the ambiguous middle)
- `p < 0.55` → auto-reject

The thresholds are tunable per operator deployment. The **0.95 cutoff is set deliberately conservative** to keep auto-merge precision above 0.99 on held-out data. The 0.55 lower bound ensures recall isn't degraded by sweeping borderline pairs into auto-reject.

### 3.2 Feature vector — 25 features in 5 groups

Every pair is represented by a **25-dimensional feature vector**. Features were chosen to mirror how a human reviewer adjudicates a match — what they read first, what changes their mind, what closes the case.

**Name signals (5)** — the textual identity of the firm.
- `name_token_set_ratio` — Jaccard on lowercase alphanumeric tokens after legal-suffix stripping.
- `name_jaro_winkler` — Jaro-Winkler distance on the canonical name.
- `name_initial_match` — boolean, do the first three letters agree after normalization.
- `name_strip_match` — equality after stripping legal forms (`PVT LTD`, `LLP`, `& CO`, `M/s`).
- `name_kannada_roman_match` — equality after Kannada→Roman transliteration via `indic-transliteration` (Sanscript ITRANS scheme). This is what catches records where one source stores `ಶರ್ಮಾ ಟ್ರೇಡರ್ಸ್` and the other stores `Sharma Traders` for the same firm.

**Address signals (6)** — the spatial identity.
- `addr_pin_equality` — boolean equality of pin codes.
- `addr_locality_canonical_match` — match after a 700-locality dictionary canonicalisation (`KIADB Industrial Area Anekal` and `Anekal KIADB Phase 2` map to the same locality token).
- `addr_district_match` — boolean district equality.
- `addr_geo_distance_km` — geodesic distance between geocoded coordinates. Geocoding is performed by a **self-hosted Nominatim instance** running over the Karnataka OpenStreetMap extract (~126 MB of `.pbf` data). Self-hosting was a deliberate choice: it is the only path compatible with Karnataka government data-residency rules. It also gives us ~5 m precision on building-level matches versus ~2 km centroid precision from a locality-only system. On the labelled evaluation set, adding the geo-distance feature lifted pairwise recall by ~5–8 points and B3 F1 by 2–3 points.
- `addr_token_overlap` — token Jaccard on full address strings.
- `addr_canonical_string_match` — equality of fully canonicalised address strings (post locality dict + abbreviation expansion + pin normalisation).

**Identifier signals (4)** — exact-match keys other than PAN.
- `gstin_match` / `gstin_partial_match` — full and last-10 (PAN-suffix-of-GSTIN) equality. GSTIN is the GST registration number; its embedded PAN suffix often aligns even when one source has only the partial.
- `registration_id_match` — equality of source-registration IDs after normalisation.
- `phone_match` — equality of phone numbers after country-code stripping.

**Structural signals (4)** — what kind of business.
- `sector_nic_code_match` — equality of National Industry Code (Nigeria-style 4-digit NIC code).
- `sector_nic_first_digits` — partial NIC match at the 2-digit (broad sector) level.
- `legal_form_match` — equality of legal-form token (`PVT LTD`, `LLP`, `PROPRIETORSHIP`, `PARTNERSHIP`).
- `is_msme_flag_match` — both records or neither flagged as MSME.

**Blocking-derived signals (6)** — features derived from the same blocking keys used to retrieve the candidate, repurposed as features so the model can learn how a candidate was retrieved.
- `block_by_pin`, `block_by_district`, `block_by_name_prefix`, `block_by_phone`, `block_by_gstin_suffix`, `block_count` — booleans + the size of the block the candidate came from. Large blocks are signal that the match is more uncertain even when other features fire.

### 3.3 The model — LightGBM + isotonic calibration

The classifier is a **LightGBM gradient-boosted decision tree** with the following hyperparameters (held-out tuned):

```
num_leaves        = 31
max_depth         = 6
learning_rate     = 0.05
min_child_samples = 20
n_estimators      = 200
class_weight      = balanced (handles 1:8 negative skew)
```

LightGBM was chosen over a deep model because:

1. **Tabular features dominate.** With 25 hand-engineered features and a few thousand labelled pairs, gradient-boosted trees outperform any deep architecture in our benchmark — and they train in seconds, which keeps the reviewer-feedback loop fast.
2. **Native handling of missing values.** Many records have null PAN, null GSTIN, null phone. LightGBM handles missing values without imputation; deep models would force us to learn an imputation policy first.
3. **SHAP integrates trivially.** Every score we surface to a reviewer comes with a SHAP-value bar chart explaining which features moved the decision. This is non-negotiable for a state-government-facing system where every linkage must be defensible.

The raw LightGBM probability is **isotonic-calibrated** post-hoc. We use `sklearn.isotonic.IsotonicRegression` fit on a held-out validation slice. After calibration:

- **Brier score: 0.0094** (a calibrated random classifier baseline is 0.25)
- **Expected Calibration Error: 0.0152** (the cutoff for "well-calibrated" by community convention is 0.02)
- **Pairwise F1: 0.93** at the operating threshold

The calibration is what lets us treat `p ≥ 0.95` as a reliable auto-merge cutoff. Without it, LightGBM's raw probabilities are skewed toward the extremes and produce systematically over-confident merges.

### 3.4 The blocking step — why not all-pairs

A naive system would compute the 25-feature vector for every record pair. With 267 source records, that's `267²/2 ≈ 35,600` pairs — manageable. But a production system processing the full Karnataka register would be on the order of `5×10⁶` records → `1.2×10¹³` pairs, which is intractable.

We use **OpenSearch** for blocking. Each incoming record produces blocking keys: `pin_code`, `district`, `name_first_3_letters`, `phone`, `gstin_pan_suffix`. A candidate pair is generated only when two records share at least one blocking key, capping comparisons at a few hundred per record. On the synthetic dataset this gives **97 % candidate-recall** (of true positives, this fraction land in the candidate set) and is what makes the system scale to State-level data.

### 3.5 Inline clustering — the central insight

LightGBM scores **pairs**, not clusters. To produce a UBID — which is fundamentally a cluster — we need a clustering step on top.

The naive approach is offline transitive closure: take every pair with `p ≥ 0.95`, build a graph, take connected components. We tried it. It produced **B3 F1 = 0.40** because of two failure modes:

1. **Transitivity violations.** If `A↔B` and `B↔C` both score 0.96, they get merged into `{A, B, C}` — but `A↔C` may score 0.30 (different addresses, different PANs). The cluster is contaminated.
2. **No reviewer feedback.** A reviewer rejecting an `A↔B` link offline doesn't change the clustering; the bad merge persists.

We replaced offline transitive closure with **inline union-find clustering with constraints**. The algorithm:

1. Sort all candidate pairs by descending score.
2. Walk the sorted list. For each pair `(a, b)` with score `p`:
   - If a `cannot-link(a, b)` constraint exists from any reviewer decision, skip.
   - If `a` and `b` are already in the same cluster, skip (already linked).
   - If `p ≥ auto_merge_threshold`, union the two clusters.
   - Otherwise enqueue for reviewer attention.
3. Reviewer decisions write `must-link(a, b)` or `cannot-link(a, b)` constraints to the database.
4. On the next clustering pass, the constraints take precedence over the model.

This single change took **B3 F1 from 0.40 to 0.92** on held-out data. The cannot-link mechanism breaks transitivity contamination; the must-link mechanism captures reviewer expertise and persists it across model retrains.

### 3.6 The reviewer-in-loop feedback loop

Every reviewer decision is a **labelled training example for the next retrain**. The flow:

1. A reviewer confirms or rejects a pair.
2. The decision is written to PostgreSQL (`reviewer_decisions` table) along with the timestamp, reviewer ID, and tier.
3. On the next retrain (triggered manually from the Admin page or scheduled), the decisions are joined with the original feature vectors and appended to the training set.
4. LightGBM retrains. Isotonic calibration re-fits on the new validation slice.
5. The new model re-scores every pending pair via the **smart re-score** endpoint, which only recomputes pairs whose features could have changed (it skips pairs already manually decided).

The platform supports a two-tier reviewer model: **junior** reviewers handle the 0.55–0.85 band (true ambiguity); **senior** reviewers handle 0.85–0.95 (close to auto-merge but flagged) and any deferred items. Senior decisions become precedents — they can be replayed across the queue via the **bulk apply** action.

---

## 4. Track 2 — Active business inference

The UBID is the join key that makes activity inference possible. Once records are clustered into a UBID, every event from every source can be aligned on the same time axis.

### 4.1 The signal model

Each event `e` carries:

- `ubid` — which business the event is for
- `source` — which department system produced it (BESCOM, KSPCB, e-Karmika, FBIS, BWSSB)
- `event_type` — `bill_paid`, `inspection_passed`, `consent_renewed`, `zero_consumption`, `closure_filed`, `meter_disconnected`, etc.
- `event_date` — when it happened
- `metadata` — JSON with source-specific context (bill amount, kWh consumed, inspection notes)

A business that is "active" produces events. A closed business stops. A dormant business produces sparse events. The classifier's job is to read the event stream and decide which regime the business is in.

### 4.2 Cadence-aware exponential decay

The continuity score `S` for a UBID at reference date `T` is:

```
                 ┌──────────────────────────────────────┐
                 │       │
S(ubid, T) = Σ   │ w_e · exp( -Δt / (α_source · τ_e) )  │
            e∈E  │       │
                 └──────────────────────────────────────┘
```

where:

- `E` is the set of events for the UBID
- `Δt = T - event_date_e` is the age of the event in days
- `w_e` is the per-event-type weight (BESCOM bill paid: `+1.0`, BESCOM zero-consumption: `−0.4`, KSPCB consent renewal: `+0.9`, factory closure filed: `−1.0`, etc.)
- `τ_e` is the per-event-type characteristic decay time. A monthly utility bill has `τ ≈ 30` days; an annual factory return has `τ ≈ 365` days.
- `α_source ∈ [0.7, 1.4]` is a per-source cadence multiplier. BESCOM produces evidence monthly, so its events decay slower (α=1.2) — a 60-day-old bill is still strong evidence. e-Karmika produces events sparsely on registration / renewal events, so its α is smaller.

The **cadence-aware** part is critical: a generic exponential decay treats all events as equally informative regardless of how often a source emits them. Our model down-weights stale events from rapid-cadence sources (a 90-day-old electricity bill is very stale) but preserves the weight of stale events from slow-cadence sources (a 90-day-old factory inspection is normal).

### 4.3 Verdict thresholds

The continuity score maps to a verdict:

| `S` range | Verdict | Interpretation |
|---|---|---|
| `≥ 1.5` | **Active** | Recent multi-signal evidence; business is operating. |
| `0.15 – 1.5` | **Dormant** | Sparse or aging signals; not closed but not visibly active. |
| `< 0.15` and `latest_event > 730 days` | **Closed-by-silence** | No event in 2+ years; treated as effectively closed. |
| explicit closure event present | **Closed** | Factory closure filed, meter disconnected, consent surrendered. |
| `< 0.15` and oldest event `< 180 days` | **Nascent** | Just registered; not enough history yet to call. |

These thresholds are tunable per deployment via the `.env` file. The current values were calibrated on the synthetic dataset to maximise alignment with explicit closure-event ground truth.

### 4.4 Why this is not just a statistics aggregation

Two things make the activity inference more than a "did anything happen recently" filter:

1. **Negative signals.** A `zero_consumption` BESCOM event is a *negative* contribution. A factory that has paid every month and then has 6 months of zero consumption looks superficially active (its score has a long history of positive signals) but its trajectory is downward. The decay model captures this — recent negative weight outweighs old positive weight.

2. **Cross-source corroboration.** A KSPCB consent renewal from a year ago is moderate evidence. A BESCOM bill from last week alongside the consent renewal is strong evidence. The platform's signal-contribution table on the Activity Status page shows the per-event contribution to `S`, which is what makes a verdict defensible to a reviewer or auditor.

---

## 5. Supporting components

### 5.1 Self-hosted Nominatim geocoding

Most off-the-shelf geocoders (Google Maps, Mapbox, HERE) are SaaS APIs with two problems for a State-government deployment:

1. **Data residency.** Karnataka's records cannot leave Indian government infrastructure; sending an address to Google Maps for geocoding is non-compliant.
2. **Cost.** ~270 records × multiple geocoder lookups during dev/eval — would be free at this scale on most APIs but does not scale to State-level deployments.

We host **Nominatim** (the OpenStreetMap geocoder) in our Docker stack. The container imports the Karnataka OSM extract (`karnataka-latest.osm.pbf`, ~126 MB, downloaded from openstreetmap.fr) on first boot and serves geocoding queries from the local PostgreSQL+PostGIS database. This is fully on-prem, free, and produces ~5 m precision on building-level matches.

A/B comparison on the labelled evaluation set:

| Configuration | B3 F1 | Pairwise recall |
|---|---|---|
| No geocoder (locality dict only) | 0.89 | 0.83 |
| Self-hosted Nominatim | **0.92** | **0.91** |

### 5.2 Kannada–Roman transliteration

Karnataka records frequently include Kannada-script names (`ಶರ್ಮಾ ಟ್ರೇಡರ್ಸ್`) alongside Latin-script names (`Sharma Traders`). We use the `indic-transliteration` library (`sanscript`) to convert Kannada to ITRANS Roman before computing name features. This gives a reliable name-similarity signal even when the two records use different scripts.

The pipeline: detect Kannada Unicode range → transliterate to Roman → normalise → tokenise → compare. The `name_kannada_roman_match` feature is a boolean equality after this pipeline.

(Note: the synthetic evaluation dataset is mostly Roman-script for tractability, so this feature does not see heavy use in the current metrics. It is implemented and tested via `scripts/test_kannada_transliteration.py` — when the platform is deployed against real registers with Kannada-script entries, the feature activates without code change.)

### 5.3 SHAP explainability

Every score surfaced to a reviewer is accompanied by a **SHAP value bar chart** showing each feature's contribution. Internally, we cache a `shap.TreeExplainer` for the trained LightGBM model and call it once per pair. Output: `feature_name → contribution_to_logit`, which we render as horizontal bars on the Review Queue page (positive contributions in moss green to the right of the axis, negative in crimson to the left).

This makes the platform auditable: a reviewer can inspect *why* a pair was scored 0.82 (`PAN equality +0.42`, `address locality match +0.28`, `phone differs −0.14`, `sector NIC differs −0.11`). The same SHAP traces are stored in the reviewer log so a decision can be re-justified months later.

---

## 6. Architecture & stack rationale

| Component | Tech | Why |
|---|---|---|
| Source-record store | **PostgreSQL 16** | Relational integrity, mature audit-log support, row-level locking for the reviewer-decision table. |
| Blocking + retrieval | **OpenSearch 2.16** | Fast multi-key blocking; we don't use it for full-text relevance, just for the candidate-set retrieval. Apache 2.0 licensed (Elastic was ruled out by SSPL). |
| Entity graph | **Neo4j 5.24** | UBID lineage and the must-link / cannot-link constraint graph are graph-native problems; querying "all records ever merged into UBID X" is a 1-hop traversal in Neo4j vs. a recursive CTE in Postgres. |
| Cache | **Redis 7** | Score memoization (LightGBM is fast but pair scoring at scale benefits from caching) and queue-state coordination across workers. |
| Event stream | **Apache Kafka 7.7 (KRaft mode)** | Source-system events (BESCOM bills, KSPCB renewals, etc.) arrive asynchronously and are consumed by both the activity-inference worker and the audit-log writer. KRaft removes the ZooKeeper dependency. |
| Event warehouse | **DuckDB + Parquet** | The event store is read-heavy (every Activity Status page load triggers a multi-source scan). DuckDB's columnar in-process engine returns the per-UBID event stream in <50 ms; running the same query on PostgreSQL would be slower and would lock the OLTP store. |
| ML scorer | **LightGBM + scikit-learn isotonic** | Tabular-feature optimum; trains in seconds, predicts in microseconds, integrates trivially with SHAP. |
| Geocoder | **Nominatim** | On-prem, free, OSM-backed. See §5.1. |
| API layer | **FastAPI + Pydantic v2** | Auto-generated OpenAPI docs that judges and integrators can browse at `/docs`; type-safe request/response handling. |
| UI | **Streamlit + Plotly** | Lets a small team ship a multi-page reviewer console without a separate frontend team. The editorial design system is implemented in custom CSS over Streamlit's primitives. |

---

## 7. Evaluation

The held-out evaluation harness (`scripts/evaluate.py`) runs end-to-end on a fixed synthetic dataset of 75 ground-truth UBIDs spanning ~270 source records. Metrics:

| Metric | Score | What it measures |
|---|---|---|
| **B3 F1** | **0.92** | Cluster-level F1 (Bagga & Baldwin). The right thing to optimise for entity resolution. |
| Pairwise F1 | 0.93 | Pair-level F1; how well the model scores individual `(a, b)` decisions. |
| Brier score | 0.0094 | Calibration quality. Lower is better; <0.01 is excellent. |
| Expected Calibration Error | 0.0152 | Maximum gap between predicted and observed probability across reliability bins. <0.02 is "well-calibrated". |
| Auto-merge precision | 0.997 | Of pairs the model auto-merges (`p ≥ 0.95`), the fraction that are true matches. |
| Reviewer-throughput | ~25 decisions/minute | Empirical from junior reviewer testing. Drives the design of bulk-apply and keyboard shortcuts. |

The system also tracks per-source coverage: of the 75 UBIDs, what fraction has a record in each of the 5 sources. This surfaces which departments have under-onboarded their data.

---

## 8. What this submission demonstrates

The hackathon prompt asked for two distinct things — a UBID assignment system and an active-business inference system — and we have built both as a single integrated pipeline where each strengthens the other. Specifically:

- **Entity resolution at B3 F1 = 0.92** with full reviewer-in-loop feedback, calibrated probabilities, and SHAP-explainable decisions. Inline clustering with cannot-link constraints is the central technical insight.
- **Active-business inference** that goes beyond the registry's status field by integrating multi-source temporal evidence under a cadence-aware decay model. Verdicts are reversible and trace back to specific events.
- **Proposal compliance** end-to-end: on-prem geocoding (no Google Maps), multilingual name handling (Kannada via transliteration), every decision audited and reviewer-attributed, all infrastructure running in a single `docker compose up`.
- **A 5th source adapter (BWSSB)** was added late in development to verify the adapter pattern is genuinely pluggable; integrating it required ~80 lines of code.

The entire system runs locally on a developer laptop in 11 Docker services, ingests the synthetic Karnataka register in under 90 seconds, and is fully operational from the first reviewer login.
