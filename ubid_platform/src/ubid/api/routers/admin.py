"""Admin endpoints — retraining, calibration monitoring, locality dictionary.

These endpoints close the proposal's feedback loops:
  • Reviewer labels accumulate in training_labels and reviewer_decisions
  • /admin/retrain re-fits LightGBM + isotonic on the latest labels and
    reports A/B comparison against the previous model
  • /admin/calibration-report exposes reliability-diagram data so the team
    can monitor calibration drift weekly per Section 8.1 of the proposal
  • /admin/synonyms/apply re-canonicalises records affected by a new
    locality synonym so subsequent blocking and scoring can use it
"""
from __future__ import annotations
import csv
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text

from ubid.api.routers.ingest import _orm_to_canonical
from ubid.scoring import features as feat_module
from ubid.scoring.lgbm_scorer import get_scorer
from ubid.storage.postgres import (
    CanonicalRecordORM,
    LinkagePairORM,
    ReviewerQueueORM,
    RetrainRunORM,
    TrainingLabelORM,
    get_db,
)

router = APIRouter()
logger = logging.getLogger(__name__)


GROUND_TRUTH_PATH = Path("/app/data/synthetic/ground_truth_links.csv")


def _load_reviewer_labelled_pairs() -> list[tuple[str, str, int]]:
    out = []
    with get_db() as db:
        for row in db.execute(select(TrainingLabelORM)).scalars():
            out.append((str(row.canonical_id_a), str(row.canonical_id_b),
                        1 if row.is_match else 0))
    return out


def _load_ground_truth_pairs() -> list[tuple[str, str, int]]:
    """Optional: include synthetic ground truth in the training set so the
    model has a base before reviewer labels accumulate."""
    if not GROUND_TRUTH_PATH.exists():
        return []
    entities: list[dict] = []
    with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            members = []
            for src, col in [("ekarmika", "ekarmika_record_id"),
                             ("fbis", "fbis_record_id"),
                             ("kspcb", "kspcb_record_id"),
                             ("bescom", "bescom_record_id")]:
                for rid in (row.get(col) or "").split(";"):
                    rid = rid.strip()
                    if rid:
                        members.append((src, rid))
            entities.append({"id": row["entity_id"], "members": members})

    canonical_id: dict[tuple[str, str], str] = {}
    with get_db() as db:
        for orm in db.execute(select(CanonicalRecordORM)).scalars():
            canonical_id[(orm.source_system, orm.source_record_id)] = str(orm.canonical_id)

    pairs: list[tuple[str, str, int]] = []
    # Positives: same-entity combinations
    for e in entities:
        present = [canonical_id[m] for m in e["members"] if m in canonical_id]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                pairs.append((present[i], present[j], 1))

    # Negatives: random different-entity combinations, balanced to positives
    import random
    rng = random.Random(42)
    flat = [(e["id"], canonical_id[m]) for e in entities for m in e["members"] if m in canonical_id]
    target_neg = 3 * sum(1 for _, _, lbl in pairs if lbl == 1)
    seen: set[frozenset[str]] = set()
    attempts = 0
    while len([p for p in pairs if p[2] == 0]) < target_neg and attempts < target_neg * 10:
        attempts += 1
        a = rng.choice(flat)
        b = rng.choice(flat)
        if a[0] == b[0]:
            continue
        key = frozenset([a[1], b[1]])
        if key in seen:
            continue
        seen.add(key)
        pairs.append((a[1], b[1], 0))

    return pairs


def _featurise(pair_list: list[tuple[str, str, int]]) -> tuple[list[list[float]], list[int]]:
    canon: dict[str, object] = {}
    needed = {pid for pair in pair_list for pid in pair[:2]}
    with get_db() as db:
        for orm in db.execute(select(CanonicalRecordORM).where(
            CanonicalRecordORM.canonical_id.in_(list(needed))
        )).scalars():
            canon[str(orm.canonical_id)] = _orm_to_canonical(orm)

    X: list[list[float]] = []
    y: list[int] = []
    for a, b, lbl in pair_list:
        if a in canon and b in canon:
            fv = feat_module.compute(canon[a], canon[b])
            X.append(feat_module.to_vector(fv))
            y.append(lbl)
    return X, y


# ── Retrain ──────────────────────────────────────────────────────────────────

class RetrainRequest(BaseModel):
    include_ground_truth: bool = True
    min_reviewer_labels: int = 0


@router.post("/retrain")
def retrain_scorer(body: RetrainRequest):
    import uuid as _uuid
    from datetime import datetime, timezone

    reviewer_pairs = _load_reviewer_labelled_pairs()
    if len(reviewer_pairs) < body.min_reviewer_labels:
        raise HTTPException(
            400,
            f"Only {len(reviewer_pairs)} reviewer labels — minimum required is {body.min_reviewer_labels}",
        )

    pairs = list(reviewer_pairs)
    if body.include_ground_truth:
        pairs.extend(_load_ground_truth_pairs())

    if not pairs:
        raise HTTPException(400, "No labelled pairs to train on")

    # Open a retrain-run row up front so we always log the attempt
    run_id = str(_uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    pre_metrics = _evaluate_holdout(pairs)

    X, y = _featurise(pairs)
    if not X:
        raise HTTPException(400, "Featurisation produced 0 vectors — canonical records missing")

    t0 = time.time()
    scorer = get_scorer()
    scorer.train(X, y)
    duration = time.time() - t0

    post_metrics = _evaluate_holdout(pairs)

    finished_at = datetime.now(timezone.utc)

    # Persist a retrain-run row for history + label-budget tracking
    try:
        with get_db() as db:
            db.add(RetrainRunORM(
                run_id=run_id,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=round(duration, 3),
                n_reviewer_labels=len(reviewer_pairs),
                n_ground_truth_pairs=len(pairs) - len(reviewer_pairs),
                n_total_pairs=len(pairs),
                pre_brier=pre_metrics.get("brier"),
                pre_ece=pre_metrics.get("ece"),
                pre_f1=pre_metrics.get("f1"),
                pre_precision=pre_metrics.get("precision"),
                pre_recall=pre_metrics.get("recall"),
                post_brier=post_metrics.get("brier"),
                post_ece=post_metrics.get("ece"),
                post_f1=post_metrics.get("f1"),
                post_precision=post_metrics.get("precision"),
                post_recall=post_metrics.get("recall"),
                triggered_by="manual",
                notes=None,
            ))
    except Exception as e:
        logger.warning("Could not persist retrain-run row: %s", e)

    return {
        "status": "trained",
        "run_id": run_id,
        "n_reviewer_labels": len(reviewer_pairs),
        "n_ground_truth_pairs": len(pairs) - len(reviewer_pairs),
        "n_total_pairs": len(pairs),
        "duration_seconds": round(duration, 2),
        "pre_train": pre_metrics,
        "post_train": post_metrics,
    }


@router.get("/retrain-history")
def retrain_history(limit: int = 20):
    """Return the most recent retrain runs with their before/after metrics.

    Drives the Admin → Retrain history chart so users can see the model
    improving (or regressing) over time.
    """
    from sqlalchemy import select, desc
    with get_db() as db:
        rows = db.execute(
            select(RetrainRunORM)
            .order_by(desc(RetrainRunORM.started_at))
            .limit(limit)
        ).scalars().all()

    return {
        "total": len(rows),
        "runs": [
            {
                "run_id": str(r.run_id),
                "started_at": str(r.started_at) if r.started_at else None,
                "finished_at": str(r.finished_at) if r.finished_at else None,
                "duration_seconds": r.duration_seconds,
                "n_reviewer_labels": r.n_reviewer_labels,
                "n_ground_truth_pairs": r.n_ground_truth_pairs,
                "n_total_pairs": r.n_total_pairs,
                "pre": {
                    "f1": r.pre_f1, "brier": r.pre_brier, "ece": r.pre_ece,
                    "precision": r.pre_precision, "recall": r.pre_recall,
                },
                "post": {
                    "f1": r.post_f1, "brier": r.post_brier, "ece": r.post_ece,
                    "precision": r.post_precision, "recall": r.post_recall,
                },
                "triggered_by": r.triggered_by,
                "notes": r.notes,
            }
            for r in rows
        ],
    }


@router.get("/labels-since-last-retrain")
def labels_since_last_retrain():
    """How many reviewer labels have accumulated since the last retrain.

    Used by the Admin page to show a label-budget counter:
      - 0 new labels   → retraining is pointless
      - small budget   → retraining gives marginal gain
      - large budget   → retraining will probably move metrics
    """
    from sqlalchemy import select, desc, func
    with get_db() as db:
        last = db.execute(
            select(RetrainRunORM)
            .order_by(desc(RetrainRunORM.started_at))
            .limit(1)
        ).scalar_one_or_none()

        total_labels = db.execute(
            select(func.count()).select_from(TrainingLabelORM)
        ).scalar() or 0

        if last is None:
            return {
                "last_retrain_at": None,
                "total_labels": total_labels,
                "labels_since_last_retrain": total_labels,
                "recommendation": "first retrain — run whenever you have at least 50 labels",
            }

        new_count = db.execute(
            select(func.count()).select_from(TrainingLabelORM)
            .where(TrainingLabelORM.created_at > last.started_at)
        ).scalar() or 0

    if new_count == 0:
        rec = "no new labels — retrain would not change anything"
    elif new_count < 20:
        rec = f"only {new_count} new labels — wait for more (≥50 recommended)"
    elif new_count < 200:
        rec = f"{new_count} new labels — retrain would refresh calibration"
    else:
        rec = f"{new_count} new labels — retrain strongly recommended"

    return {
        "last_retrain_at": str(last.started_at),
        "last_retrain_run_id": str(last.run_id),
        "total_labels": total_labels,
        "labels_since_last_retrain": new_count,
        "recommendation": rec,
    }


@router.post("/rescore")
def rescore_pairs(mode: str = "smart"):
    """Re-score linkage_pairs with the current model.

    `mode=smart` (default): only re-score pairs that matter:
      • all pairs in the review queue (so reviewers see fresh probabilities)
      • boundary pairs in the calibrated_probability range [0.20, 0.97]
        (their auto-link / review / reject bucket might change)
    Skips pairs already firmly classified — they wouldn't move buckets
    even if the model shifted.

    `mode=full`: re-score every pair (slow at scale).
    """
    from datetime import datetime, timezone
    from sqlalchemy import select
    from ubid.api.routers.ingest import _orm_to_canonical
    from ubid.scoring.lgbm_scorer import get_scorer

    if mode not in ("smart", "full"):
        raise HTTPException(400, "mode must be 'smart' or 'full'")

    scorer = get_scorer()
    if not scorer._trained:
        raise HTTPException(409, "Scorer is not trained — run /admin/retrain first.")

    t0 = time.time()
    updated = 0
    skipped = 0

    with get_db() as db:
        # Pull canonical records once into a dict for fast lookup
        canon_by_id = {
            str(c.canonical_id): _orm_to_canonical(c)
            for c in db.execute(select(CanonicalRecordORM)).scalars()
        }

        if mode == "full":
            pairs = list(db.execute(select(LinkagePairORM)).scalars())
        else:
            # Boundary pairs (the only ones whose bucket might change)
            boundary_pairs = list(db.execute(
                select(LinkagePairORM).where(
                    LinkagePairORM.calibrated_probability >= 0.20,
                    LinkagePairORM.calibrated_probability <= 0.97,
                )
            ).scalars())
            # Pairs in the review queue
            queue_pair_ids = set(str(q.pair_id) for q in db.execute(
                select(ReviewerQueueORM).where(ReviewerQueueORM.status == "pending")
            ).scalars())
            queue_pairs = [p for p in db.execute(select(LinkagePairORM)).scalars()
                           if str(p.pair_id) in queue_pair_ids]
            seen = set()
            pairs = []
            for p in boundary_pairs + queue_pairs:
                if str(p.pair_id) in seen:
                    continue
                seen.add(str(p.pair_id))
                pairs.append(p)

        for p in pairs:
            a = canon_by_id.get(str(p.canonical_id_a))
            b = canon_by_id.get(str(p.canonical_id_b))
            if a is None or b is None:
                skipped += 1
                continue
            sp = scorer.score(a, b, fast=True)
            p.raw_score = sp.raw_score
            p.calibrated_probability = sp.calibrated_probability
            p.deterministic_tier_fired = sp.deterministic_tier_fired
            p.deterministic_result = sp.deterministic_result
            p.feature_vector = sp.feature_vector
            p.shap_contributions = sp.shap_contributions
            p.shared_blocks = sp.shared_blocks
            p.scored_at = datetime.now(timezone.utc)
            updated += 1

    return {
        "mode": mode,
        "pairs_rescored": updated,
        "skipped_missing_records": skipped,
        "duration_seconds": round(time.time() - t0, 2),
    }


def _evaluate_holdout(pairs: list[tuple[str, str, int]], frac: float = 0.2) -> dict:
    """Score a held-out subset with the current model (heuristic if untrained)
    and return precision/recall/F1 at threshold 0.95 plus calibration metrics.
    """
    import random
    rng = random.Random(42)
    n_holdout = max(20, int(len(pairs) * frac))
    holdout = rng.sample(pairs, min(n_holdout, len(pairs)))

    canon: dict[str, object] = {}
    needed = {pid for pair in holdout for pid in pair[:2]}
    with get_db() as db:
        for orm in db.execute(select(CanonicalRecordORM).where(
            CanonicalRecordORM.canonical_id.in_(list(needed))
        )).scalars():
            canon[str(orm.canonical_id)] = _orm_to_canonical(orm)

    scorer = get_scorer()
    y_true: list[int] = []
    y_prob: list[float] = []
    for a, b, lbl in holdout:
        if a not in canon or b not in canon:
            continue
        sp = scorer.score(canon[a], canon[b], fast=True)
        y_true.append(lbl)
        y_prob.append(sp.calibrated_probability)

    if not y_true:
        return {"error": "no scorable holdout pairs"}

    return _compute_metrics(y_true, y_prob, threshold=0.95)


def _compute_metrics(y_true: list[int], y_prob: list[float], threshold: float) -> dict:
    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    brier = sum((p - t) ** 2 for p, t in zip(y_prob, y_true)) / len(y_true)

    n_bins = 10
    ece = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        bucket = [(p, t) for p, t in zip(y_prob, y_true)
                  if lo <= p < hi or (b == n_bins - 1 and p == 1.0)]
        if not bucket:
            continue
        avg_p = sum(p for p, _ in bucket) / len(bucket)
        avg_t = sum(t for _, t in bucket) / len(bucket)
        ece += abs(avg_p - avg_t) * len(bucket) / len(y_prob)

    return {
        "n": len(y_true),
        "threshold": threshold,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "brier": round(brier, 4),
        "ece": round(ece, 4),
    }


# ── Calibration report ──────────────────────────────────────────────────────

@router.get("/calibration-report")
def calibration_report(n_bins: int = Query(10, ge=2, le=20)):
    """Reliability-diagram data for the current scorer.

    Bins the predicted probability into n_bins, then reports the average
    predicted probability, the observed match rate, and bucket count for
    each bin. A well-calibrated model has avg_predicted ≈ observed in
    every bucket.
    """
    pairs = list(_load_reviewer_labelled_pairs()) + _load_ground_truth_pairs()
    if not pairs:
        raise HTTPException(400, "No labelled pairs available")

    canon: dict[str, object] = {}
    needed = {pid for p in pairs for pid in p[:2]}
    with get_db() as db:
        for orm in db.execute(select(CanonicalRecordORM).where(
            CanonicalRecordORM.canonical_id.in_(list(needed))
        )).scalars():
            canon[str(orm.canonical_id)] = _orm_to_canonical(orm)

    scorer = get_scorer()
    y_true: list[int] = []
    y_prob: list[float] = []
    for a, b, lbl in pairs:
        if a in canon and b in canon:
            sp = scorer.score(canon[a], canon[b], fast=True)
            y_true.append(lbl)
            y_prob.append(sp.calibrated_probability)

    bins = []
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        bucket = [(p, t) for p, t in zip(y_prob, y_true)
                  if lo <= p < hi or (b == n_bins - 1 and p == 1.0)]
        if not bucket:
            bins.append({
                "bin": b, "lo": lo, "hi": hi,
                "n": 0, "avg_predicted": None, "observed": None,
            })
        else:
            bins.append({
                "bin": b, "lo": round(lo, 3), "hi": round(hi, 3),
                "n": len(bucket),
                "avg_predicted": round(sum(p for p, _ in bucket) / len(bucket), 4),
                "observed": round(sum(t for _, t in bucket) / len(bucket), 4),
            })

    metrics = _compute_metrics(y_true, y_prob, threshold=0.95)
    return {
        "n_pairs": len(y_true),
        "metrics_at_0_95": metrics,
        "reliability_diagram": bins,
        "is_well_calibrated": metrics["ece"] < 0.05,
    }


# ── Locality synonym application ─────────────────────────────────────────────

class SynonymApplyRequest(BaseModel):
    variant: str
    canonical: str
    reviewer_id: Optional[str] = None


@router.post("/synonyms/apply")
def apply_synonym(body: SynonymApplyRequest):
    """Re-canonicalise existing records whose locality_raw matches `variant`,
    so subsequent blocking and scoring use the new synonym entry."""
    from ubid.canonicalize.locality_normalizer import add_synonym, normalize

    add_synonym(body.variant, body.canonical)

    affected = 0
    with get_db() as db:
        rows = db.execute(text("""
            SELECT canonical_id, locality_raw
            FROM canonical_records
            WHERE LOWER(locality_raw) LIKE :v
            LIMIT 5000
        """), {"v": f"%{body.variant.lower()}%"}).fetchall()

        for cid, raw in rows:
            new_canonical = normalize(raw or "")
            db.execute(text("""
                UPDATE canonical_records SET locality_canonical = :c WHERE canonical_id = :id
            """), {"c": new_canonical, "id": str(cid)})
            affected += 1

    return {
        "status": "applied",
        "variant": body.variant,
        "canonical": body.canonical,
        "records_recanonicalised": affected,
    }


# ── Verdict batch refresh ────────────────────────────────────────────────────

@router.post("/verdicts/refresh")
def refresh_all_verdicts(reference_date: Optional[str] = Query(None)):
    """Recompute the activity verdict for every UBID in one pass.

    Calls the same code path as /api/v1/ubid/{ubid}/status?force_recompute=true
    but in-process, so it's much faster than the looping HTTP-based script.
    """
    import datetime as _dt

    from ubid.activity.verdict import compute_verdict
    from ubid.api.routers.status import _persist_verdict
    from ubid.schema.events import ActivityEvent, EventType
    from ubid.storage import redis_cache as _rc
    from ubid.storage.duckdb_warehouse import get_events_for_ubid
    from ubid.storage.postgres import UBIDNodeORM

    ref: Optional[_dt.date] = None
    if reference_date:
        ref = _dt.date.fromisoformat(reference_date)

    counts: dict[str, int] = {}
    failed = 0

    with get_db() as db:
        ubids = list(db.execute(select(UBIDNodeORM)).scalars())

    for node in ubids:
        try:
            raw_events = get_events_for_ubid(
                str(node.ubid), lookback_days=730, reference_date=ref
            )
            events: list[ActivityEvent] = []
            import json as _json
            for row in raw_events:
                md = row.get("metadata")
                if isinstance(md, str):
                    try:
                        md = _json.loads(md)
                    except Exception:
                        md = {}
                try:
                    events.append(ActivityEvent(
                        event_id=row["event_id"],
                        source_system=row["source_system"],
                        source_record_id="",
                        event_type=EventType(row["event_type"]),
                        event_date=row["event_date"],
                        ubid=str(node.ubid),
                        metadata=md or {},
                    ))
                except Exception:
                    continue

            result = compute_verdict(
                ubid=str(node.ubid),
                events=events,
                sector=node.sector_canonical,
                reference_date=ref,
            )
            _persist_verdict(str(node.ubid), result)
            _rc.invalidate_verdict(str(node.ubid))
            verdict_str = (
                result.verdict.value if hasattr(result.verdict, "value")
                else str(result.verdict)
            )
            counts[verdict_str] = counts.get(verdict_str, 0) + 1
        except Exception as e:
            failed += 1
            logger.warning("Verdict refresh failed for %s: %s", node.ubid, e)

    return {
        "ubids_processed": len(ubids),
        "failed": failed,
        "verdict_distribution": counts,
        "reference_date": str(ref) if ref else "today",
    }
