"""Evaluate the linkage pipeline against ground_truth_links.csv.

Reports:
  • Pairwise metrics      — precision, recall, F1 at the auto-link threshold
  • Calibration metrics   — Brier score, Expected Calibration Error (ECE)
  • Cluster-level B3      — precision, recall, F1 over the realised UBID
                            partition vs. the ground-truth partition
  • Activity verdicts     — accuracy on Active/Dormant/Closed labels

Run:
    docker compose exec ubid-api python /app/scripts/evaluate.py
"""
from __future__ import annotations
import csv
import sys
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import select, text  # noqa: E402

from ubid.api.routers.ingest import _orm_to_canonical  # noqa: E402
from ubid.config import get_settings  # noqa: E402
from ubid.scoring.lgbm_scorer import get_scorer  # noqa: E402
from ubid.storage.postgres import (  # noqa: E402
    ActivityVerdictORM,
    CanonicalRecordORM,
    UBIDSourceLinkORM,
    get_db,
)

GROUND_TRUTH = _REPO / "data" / "synthetic" / "ground_truth_links.csv"


def parse_record_ids(field: str) -> list[str]:
    if not field:
        return []
    return [x.strip() for x in field.split(";") if x.strip()]


def load_ground_truth() -> tuple[dict, dict]:
    """Return (record_to_entity, entity_to_status)."""
    record_to_entity: dict[tuple[str, str], str] = {}
    entity_to_status: dict[str, str] = {}
    with open(GROUND_TRUTH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row["entity_id"]
            entity_to_status[eid] = row.get("ground_truth_status", "").strip().lower()
            for src, col in [
                ("ekarmika", "ekarmika_record_id"),
                ("fbis", "fbis_record_id"),
                ("kspcb", "kspcb_record_id"),
                ("bescom", "bescom_record_id"),
            ]:
                for rid in parse_record_ids(row.get(col, "")):
                    record_to_entity[(src, rid)] = eid
    return record_to_entity, entity_to_status


def load_canonical_map() -> dict[tuple[str, str], object]:
    out = {}
    with get_db() as db:
        for orm in db.execute(select(CanonicalRecordORM)).scalars():
            out[(orm.source_system, orm.source_record_id)] = _orm_to_canonical(orm)
    return out


# ── Pairwise metrics ─────────────────────────────────────────────────────────

def evaluate_pairwise(record_to_entity, canon, threshold: float) -> dict:
    """Score every pair of records that share an entity OR are sampled negatives.

    Computes precision/recall/F1 plus calibration metrics.
    """
    scorer = get_scorer()

    items = sorted(record_to_entity.keys())
    items = [k for k in items if k in canon]

    y_true: list[int] = []
    y_prob: list[float] = []

    # All pairs from ground truth (positives + within-entity negatives are zero)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a_key, b_key = items[i], items[j]
            same = record_to_entity[a_key] == record_to_entity[b_key]
            sp = scorer.score(canon[a_key], canon[b_key], fast=True)
            y_true.append(1 if same else 0)
            y_prob.append(sp.calibrated_probability)

    y_pred = [1 if p >= threshold else 0 for p in y_prob]

    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # Brier score
    brier = sum((p - t) ** 2 for p, t in zip(y_prob, y_true)) / len(y_true) if y_true else 0.0

    # Expected Calibration Error — 10 buckets
    n_bins = 10
    ece = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        bucket = [(p, t) for p, t in zip(y_prob, y_true) if lo <= p < hi or (b == n_bins - 1 and p == 1.0)]
        if not bucket:
            continue
        avg_p = sum(p for p, _ in bucket) / len(bucket)
        avg_t = sum(t for _, t in bucket) / len(bucket)
        ece += abs(avg_p - avg_t) * len(bucket) / len(y_prob)

    return {
        "threshold": threshold,
        "n_pairs": len(y_true),
        "n_positive": sum(y_true),
        "n_negative": len(y_true) - sum(y_true),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "brier": round(brier, 4),
        "ece": round(ece, 4),
    }


# ── B3 cluster metric ────────────────────────────────────────────────────────

def evaluate_b3(record_to_entity) -> dict:
    """Compare the actual UBID partition with the ground-truth partition.

    B3 precision: per-record share of fellow cluster-members that are also
    fellow ground-truth-entity members. B3 recall: per-record share of
    fellow ground-truth-entity members that are also in the same cluster.
    """
    # Build record -> ubid map from Postgres
    record_to_ubid: dict[tuple[str, str], str] = {}
    with get_db() as db:
        rows = db.execute(text("""
            SELECT cr.source_system, cr.source_record_id, usl.ubid
            FROM canonical_records cr
            JOIN ubid_source_links usl ON usl.canonical_id = cr.canonical_id
        """)).fetchall()
        for src, rid, ubid in rows:
            record_to_ubid[(src, rid)] = str(ubid)

    common = [k for k in record_to_entity if k in record_to_ubid]
    if not common:
        return {"error": "no overlap between ground truth and UBID assignments"}

    entity_clusters: dict[str, set] = defaultdict(set)
    ubid_clusters: dict[str, set] = defaultdict(set)
    for k in common:
        entity_clusters[record_to_entity[k]].add(k)
        ubid_clusters[record_to_ubid[k]].add(k)

    p_sum = 0.0
    r_sum = 0.0
    for k in common:
        e_set = entity_clusters[record_to_entity[k]]
        u_set = ubid_clusters[record_to_ubid[k]]
        intersect = e_set & u_set
        p_sum += len(intersect) / len(u_set)
        r_sum += len(intersect) / len(e_set)

    n = len(common)
    b3_p = p_sum / n
    b3_r = r_sum / n
    b3_f1 = 2 * b3_p * b3_r / (b3_p + b3_r) if (b3_p + b3_r) else 0.0

    return {
        "records_evaluated": n,
        "ground_truth_clusters": len(entity_clusters),
        "predicted_ubids": len(ubid_clusters),
        "b3_precision": round(b3_p, 4),
        "b3_recall": round(b3_r, 4),
        "b3_f1": round(b3_f1, 4),
    }


# ── Activity verdict accuracy ────────────────────────────────────────────────

def evaluate_verdicts(record_to_entity, entity_to_status) -> dict:
    """Compare each entity's true status with the verdict on its first UBID."""
    # Map entity -> set of UBIDs (typically 1 if linkage is good)
    entity_to_ubids: dict[str, set] = defaultdict(set)
    with get_db() as db:
        rows = db.execute(text("""
            SELECT cr.source_system, cr.source_record_id, usl.ubid
            FROM canonical_records cr
            JOIN ubid_source_links usl ON usl.canonical_id = cr.canonical_id
        """)).fetchall()
        for src, rid, ubid in rows:
            eid = record_to_entity.get((src, rid))
            if eid:
                entity_to_ubids[eid].add(str(ubid))

        verdict_map: dict[str, str] = {}
        for v in db.execute(select(ActivityVerdictORM)).scalars():
            verdict_map[str(v.ubid)] = str(v.verdict).lower()

    # Map system verdicts to ground truth labels
    def normalise(v: str) -> str:
        if v in ("active",): return "active"
        if v in ("dormant",): return "dormant"
        if v in ("closed", "closed_by_silence"): return "closed"
        if v in ("nascent",): return "nascent"
        return v

    correct = 0
    total = 0
    confusion: dict = defaultdict(lambda: defaultdict(int))
    for eid, gt in entity_to_status.items():
        gt_norm = gt.lower()
        ubids = entity_to_ubids.get(eid, set())
        if not ubids:
            continue
        # If multiple UBIDs (linkage imperfect), take the most-active one
        verdicts = [verdict_map.get(u, "unknown") for u in ubids]
        ranked = sorted(verdicts, key=lambda v: {"active": 0, "dormant": 1, "closed_by_silence": 2,
                                                  "closed": 2, "nascent": 3, "unknown": 4}.get(v, 5))
        chosen = normalise(ranked[0])
        confusion[gt_norm][chosen] += 1
        total += 1
        if chosen == gt_norm:
            correct += 1

    accuracy = correct / total if total else 0.0
    return {
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total": total,
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


def main():
    settings = get_settings()
    auto_thresh = settings.auto_link_threshold

    record_to_entity, entity_to_status = load_ground_truth()
    canon = load_canonical_map()
    print(f"Loaded ground truth: {len(record_to_entity)} records, "
          f"{len(entity_to_status)} entities")
    print(f"Canonical records in DB: {len(canon)}")

    print("\n── Pairwise metrics ────────────────────────────────────")
    for thr in (auto_thresh, 0.55, 0.7):
        m = evaluate_pairwise(record_to_entity, canon, threshold=thr)
        print(f"  threshold={m['threshold']:.2f}  "
              f"P={m['precision']}  R={m['recall']}  F1={m['f1']}  "
              f"(TP={m['tp']} FP={m['fp']} FN={m['fn']})")
    print(f"  Brier={m['brier']}  ECE={m['ece']}")

    print("\n── B3 cluster metric ───────────────────────────────────")
    b3 = evaluate_b3(record_to_entity)
    for k, v in b3.items():
        print(f"  {k}: {v}")

    print("\n── Activity verdict accuracy ────────────────────────────")
    av = evaluate_verdicts(record_to_entity, entity_to_status)
    print(f"  accuracy: {av['accuracy']}  ({av['correct']}/{av['total']})")
    print(f"  confusion (rows=truth, cols=predicted):")
    for gt, preds in sorted(av["confusion"].items()):
        line = "    " + gt + " ".ljust(12 - len(gt))
        for p, n in sorted(preds.items()):
            line += f"  {p}={n}"
        print(line)


if __name__ == "__main__":
    main()
