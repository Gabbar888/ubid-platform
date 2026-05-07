# 5-minute demo script — UBID Platform

**Recording target:** 5 minutes (4:30 – 5:00 hard cap).
**Style:** confident, conversational, no jargon dump. **Speak ~120 words per 30 seconds**.
**Format:** the left column is what you say. The right column tells you what to show on screen.

---

## Pre-flight checklist (do this 1 minute before hitting Record)

```
☐ Docker stack is up      docker ps    →  all 11 containers "Up"
☐ Data is loaded          curl localhost:8000/api/v1/query/stats  →  total_ubids ≥ 70
☐ Browser tab open        http://localhost:8501 → Dashboard
☐ Browser zoom            Ctrl+0 (reset to 100%)
☐ Hide bookmarks bar      Ctrl+Shift+B
☐ Close other tabs        only the platform tab open
☐ Phone on silent
☐ Audio test: clap once, check waveform on recorder
```

Have **two tabs ready**:
1. `http://localhost:8501` — the platform UI
2. `http://localhost:8000/docs` — Swagger API (for the very end, optional)

---

## Master script with timing

### 🎬 0:00 – 0:30 — Hook + the problem (30 s)

| What to **say** | What to **show** |
|---|---|
| "Karnataka has more than 40 state department systems holding business records — Shop Establishment, Factories, Pollution Control Board, Electricity, Water, Fire Safety. **Each was built in isolation.** The same business shows up as different rows in different databases. There's no reliable join key." | Stay on Dashboard. Let the camera see the metric strip with the big numbers (75 UBIDs, 267 records, 5 sources). |
| "So Karnataka Commerce and Industries cannot today answer basic questions about its own industrial base — *how many businesses are operating, where, in what sectors, with what recent activity*." | Pause briefly on the verdict-distribution donut. |
| "We built a platform that fixes this — **without modifying any of those source systems**." | Let that line land. |

> **Speaker tip**: this is your hook. Confident, not rushed. Look at the camera once when you say "without modifying any of those source systems".

---

### 🎬 0:30 – 1:00 — High-level solution (30 s)

| Say | Show |
|---|---|
| "Our platform sits **alongside** the source systems. It pulls records, links the ones that refer to the same real-world business, and assigns each business a single **Unified Business Identifier** — a UBID. Then it watches activity events to classify each business as Active, Dormant, or Closed." | Click the **ℹ️ About** tab (top-right of the nav). The architecture diagram comes up. |
| "End to end: four department CSVs flow in, get canonicalised, blocked through OpenSearch, scored with a calibrated machine-learning model, clustered into UBIDs, and the activity engine produces a verdict for each business." | Let the architecture diagram render. Optionally trace the pipeline with the cursor while speaking. |

---

### 🎬 1:00 – 2:30 — Live platform tour (90 s)

| Say | Show |
|---|---|
| "Here's what it looks like working. **Right now we're tracking 75 unique businesses linked across 5 source systems** — e-Karmika, Factories, Pollution Control, Electricity, and Water." | Click **📊 Dashboard**. Camera holds on the metrics + verdict donut. |
| "The donut shows what the platform thinks of each business. **38 active, 13 dormant, 24 closed.**" | Brief pause on the donut. |
| "And this calibration chart proves the model's confidence is honest — predicted probabilities track observed match rates almost perfectly. **Brier score 0.009, ECE 0.013** — that's textbook well-calibrated." | Scroll down to the calibration chart. |
| "Let me show you a real merge decision." | Click **🔍 Browse UBIDs**, pick the top row, click **Open**. |
| "This UBID has 4 records — from e-Karmika, Factories, Pollution Control, and Electricity — all linked because the model decided they're the same business." | Activity Status page loads with the linked source records visible. |
| "And every linkage is **explainable** and **reversible**. Down here is the full audit trail — every link, every reviewer decision, every constraint." | Scroll to the lineage timeline. |
| "If a reviewer thinks a record was wrongly merged, they can split it off in one click — and the system writes a permanent cannot-link constraint, so it's never re-merged automatically." | Briefly hover over the Unmerge dropdown — don't actually click. |

---

### 🎬 2:30 – 4:00 — The ML model in detail (90 s)

> **This is the heart of the talk. Speak clearly. The numbers do the work.**

| Say | Show |
|---|---|
| "Now the **machine-learning model** itself. We use **LightGBM** — gradient-boosted decision trees — for pairwise record matching. For every candidate pair of records, we compute a 25-feature vector covering name similarity, address similarity, identifier agreement, sector, and shared blocking keys." | Click **⚙️ Admin** → **Calibration** tab. Reliability diagram visible. |
| "Why LightGBM and not a neural network? **Three reasons.** First, every linkage decision must be explainable — government procurement requires it. LightGBM gives us SHAP values, so for every pair we can show *which features pushed the score up or down*. Second, our training data is small — about 1700 labelled pairs from the synthetic ground truth — and gradient-boosted trees learn well on small data. Third, neural embeddings are poorly trained on Bengaluru-specific business vocabulary." | Stay on calibration. Optionally click **Retrain model** tab to show the F1 history chart. |
| "Then we run **isotonic regression** on top to calibrate raw scores into actual probabilities. So when the model says **0.85**, that genuinely means **85% of pairs scored 0.85 are true matches**. That's what makes the auto-link threshold of 0.95 meaningful." | Stay on Admin. |
| "And critically, the model has a **two-tier structure**. If two records share the exact same PAN, that's a deterministic match — no machine learning needed. If their PANs are different and non-null, that's a deterministic non-match. **Roughly 30 to 50 percent of our cases are auto-decided this way before LightGBM is even consulted.** The machine learning only handles the genuinely ambiguous middle." | Click on **🧐 Audit Merges** to show a multi-record cluster with pair-evidence visible. |
| "Pairs that score above 0.95 are auto-linked. Pairs between 0.55 and 0.95 go to the human reviewer queue — those are the cases the model isn't sure about. Below 0.55 we reject. **Wrong merge is more costly than missed merge** — that asymmetry is hard-coded into the threshold." | Let the audit page load with the SHAP-style "why this was grouped" table visible. |

---

### 🎬 4:00 – 4:30 — Why it works: active learning loop (30 s)

| Say | Show |
|---|---|
| "What makes this self-improving is the **active learning loop**. Every reviewer decision becomes a labelled training pair. We track them in a database table. The Admin page shows **how many labels have accumulated since the last retrain**, and triggers a fresh retrain in under a second." | Click **⚙️ Admin** → **Retrain model** tab. Show the label-budget card and history chart. |
| "Every retrain reports A/B metrics — F1, Brier, ECE before and after — so we can see the model getting better over time. **In our last retrain, F1 went from 0.89 to 0.95** with just 35 reviewer labels." | Point at the history chart with the green and grey lines. |
| "Plus the constraints — must-link and cannot-link — persist across retrainings. Once a senior reviewer says *these two records can never be merged*, no future model update can override it." | Brief beat. |

---

### 🎬 4:30 – 5:00 — The exemplar query + close (30 s)

| Say | Show |
|---|---|
| "And finally, the proposal's exemplar question: *'Active factories in pin code 560058 with no inspection in the last 18 months.'* Today, in Karnataka, this is impossible to answer — factories are in FBIS, inspections are scattered, no join key. With our platform —" | Click **❓ Query Explorer**. Fill in the exemplar (verdict=active, source=fbis, no_event_type=fac_inspection, no_event_since_days=540). Click Run. |
| "— one query, instant answer." | Result appears. |
| "**Pairwise F1: 0.91. Cluster F1: 0.92. Verdict accuracy: 82%**. All on synthetic data with reviewer-labelled pairs feeding back into the model. The platform is fully Docker-deployable, runs on-prem with no third-party dependencies, and the architecture is designed to scale to 40+ source systems — we proved it with 5." | Optionally land back on Dashboard for the closing shot. |
| "Thank you." | End recording. |

---

## Total spoken word count target

- 0:00 – 0:30 → ~75 words
- 0:30 – 1:00 → ~70 words
- 1:00 – 2:30 → ~180 words
- 2:30 – 4:00 → ~310 words ← **densest section, slow down here**
- 4:00 – 4:30 → ~80 words
- 4:30 – 5:00 → ~80 words

**Total: ~795 words in 5 minutes** — comfortable pace, no rush.

---

## Detailed ML model breakdown (read-ahead, in case judges ask follow-ups)

### Why this problem fits LightGBM perfectly

Entity resolution is fundamentally a **pairwise binary classification** problem: given two records (A, B), output the probability they refer to the same business. The features available are:

- **Continuous** (Jaro-Winkler similarity, Jaccard ratio, Levenshtein distance, geographic distance in km)
- **Binary** (PAN equality, GSTIN equality, phone equality)
- **Categorical** (sector NIC compatibility, legal-form match)
- **Counts** (n_shared blocking keys)

Mixing these in a single model is awkward for linear classifiers (need extensive feature engineering, dummy-encoding) and unnecessarily complex for neural networks. **Gradient-boosted decision trees handle all of these natively** — each split is just "is feature X above value Y?" — and they're known to be the strongest off-the-shelf classifiers on tabular data.

### Why we rejected the alternatives

| Alternative | Why we rejected it |
|---|---|
| **Fellegi-Sunter (classical probabilistic linkage)** | Assumes feature independence (P(name match \| true match) × P(address match \| true match)). Our name-similarity and address-similarity features are *strongly correlated* — same business has both similar name AND same address. F-S overestimates confidence on correlated agreement. |
| **Neural embeddings (BERT-style)** | Bengaluru business vocabulary (locality names, family-name compounds, sector slang) is poorly represented in pretrained multilingual models. Training a custom model needs millions of labelled pairs we don't have. Plus opaque — fails the explainability bar. |
| **Pure rule-based system** | Brittle. Every edge case becomes another rule. Doesn't generalise. Doesn't improve with reviewer feedback. |

### How LightGBM-specific choices matter

- **n_estimators=300, learning_rate=0.05, num_leaves=31** — standard LightGBM defaults that work well on tabular data without tuning
- **early_stopping_rounds=30** — prevents overfitting on the small label set
- **Binary log-loss objective** — directly optimises the metric we care about (calibrated probability of match)

### The 25 features — chosen deliberately

We split features into **5 semantic groups** so the model can learn interactions WITHIN groups and SHAP can explain decisions BETWEEN groups:

| Group | Why this group exists |
|---|---|
| **Name (5 features)** | Name match is the strongest single signal but noisy — typos, abbreviations, legal-form drift. Multiple algorithms (Jaro-Winkler for full strings, token-set for word-order, trigram for OCR-like errors) hedge against any single algorithm's blind spots. |
| **Address (6 features)** | Same business has same address. We capture pin-code equality (cheapest), door-number equality (more discriminating), locality canonical match (fuzzy), and finally `addr_geo_distance_km` from Nominatim — the only feature that distinguishes "same building" from "5 km apart in same locality". |
| **Identifier (4 features)** | PAN, GSTIN, phone, email-domain. PAN agreement is gold — almost deterministic. Phone is weak (people share phones across businesses). Email-domain is strong for incorporated entities. |
| **Structural (4 features)** | Sector compatibility, legal-form compatibility, employee-count ratio, registration-date proximity. These catch "same business" patterns when names and addresses differ across systems. |
| **Blocking (6 features)** | These tell the model *why this pair was even considered* — did they share a PAN, share pin+name, share phone? Useful as a meta-feature for the model to weight evidence accordingly. |

### Why isotonic calibration matters more than people realise

A LightGBM raw score of 0.85 might mean anything from "actually 60% match probability" to "actually 95% match probability" — it depends on the training data distribution. **Without calibration, you can't pick a meaningful auto-link threshold.**

Isotonic regression learns a monotonic mapping from raw scores to actual probabilities, fitted on a held-out validation set. After calibration, **a score of 0.95 actually means 95% probability of match** — so our auto-link threshold has a real-world meaning ("I'm willing to auto-merge when there's a 5% or smaller chance of being wrong").

This is what makes the **wrong-merge-greater-than-missed-merge** asymmetry implementable. We can dial the threshold up to 0.97 if we want to be even more conservative — and we know exactly what that means.

### How the model gets better

1. Reviewer decides on a pair → row written to `training_labels`
2. After 50+ new labels accumulate, an admin clicks **Retrain**
3. LightGBM re-fits on (ground-truth pairs + all reviewer labels)
4. Isotonic calibrator re-fits on a fresh held-out split
5. Pre/post metrics reported (F1, Brier, ECE) — promote new model only if it's better
6. Smart re-score updates the calibrated probability for boundary pairs (the only ones whose auto-link / review / reject bucket might change)

The same retrain takes **~10 seconds at hackathon scale**, **~1 minute at production scale (100K labels)**.

---

## Tips for recording

1. **Take 2 takes minimum.** First take warms you up, second take is the keeper.
2. **Speak 10% slower than feels natural.** Demos always sound rushed on playback.
3. **Don't read this script word-for-word during recording.** Read it twice beforehand to internalise the structure, then use bullet points (left column) as cues.
4. **If you flub a sentence, pause 2 seconds and repeat.** You can edit the silence out cleanly; you can't edit "umm".
5. **Keep your cursor visible** — viewers need to follow what you're clicking.
6. **End with a clear "Thank you"** so the editor knows where to cut.

---

## What to do if you're running long at 4:30

Skip the final Query Explorer demo (saves ~20 s). Replace with:

> "And the proposal's exemplar query — *active factories with no inspection in the last 18 months* — runs in milliseconds against the UBID-keyed warehouse. Pairwise F1 of 0.91, cluster F1 of 0.92, verdict accuracy 82%. All on synthetic data with reviewer feedback. Thank you."

Lands the same numbers in 15 seconds without a screen change.

---

## Appendix — what to do if a judge interrupts mid-demo

Common questions and 30-second answers ready to deploy:

**Q: "What if the model is wrong?"**
> Every decision is reversible. The reviewer console has Unmerge, Sorting Mat, and Reject. Cannot-link constraints persist forever — once written, no future model update can override them.

**Q: "Why don't you use ChatGPT / a language model?"**
> The proposal explicitly forbids hosted LLM calls on PII data. Plus LightGBM gives us SHAP for every decision — we can defend each linkage in court. A black-box model can't pass a procurement review.

**Q: "How do you handle 40 source systems instead of 5?"**
> The architecture is adapter-based. We proved pluggability by adding the 5th source — BWSSB water — with zero changes to scoring, blocking, clustering, or verdict code. Just one new adapter file, one enum value, signal weights for new event types. Linear effort per new source.

**Q: "What's the recall? It looks low."**
> Pairwise recall at the auto-link threshold is conservative by design — wrong merge is more costly than missed merge. At threshold 0.70 our F1 is 0.91. At 0.95 we're trading recall for precision because false positives compound. The reviewer queue catches the missed cases.
