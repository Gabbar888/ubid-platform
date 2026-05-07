"""A/B comparison: dict-only geocoding vs. Nominatim + dict.

Workflow:
  1. Snapshot the current (Nominatim + dict) lat/lng of every record.
  2. Wipe lat/lng on every record.
  3. Run dict-only backfill (Nominatim disabled). Train + evaluate.
  4. Restore the Nominatim-derived coords on the records that had them.
  5. Train + evaluate again.
  6. Diff and print.
"""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import select  # noqa: E402

from ubid.api.routers.ingest import _orm_to_canonical  # noqa: E402
from ubid.canonicalize.geocoder import (  # noqa: E402
    lookup_locality, lookup_pin, lookup_district,
)
from ubid.scoring.lgbm_scorer import get_scorer  # noqa: E402
from ubid.scoring import features as feat_module  # noqa: E402
from ubid.storage.postgres import CanonicalRecordORM, get_db  # noqa: E402


def _eval_pairwise(threshold: float = 0.95) -> dict:
    import csv
    GT = _REPO / "data" / "synthetic" / "ground_truth_links.csv"

    def parse(field: str) -> list[str]:
        return [x.strip() for x in (field or "").split(";") if x.strip()]

    record_to_entity = {}
    with open(GT, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for src, col in [("ekarmika", "ekarmika_record_id"),
                              ("fbis", "fbis_record_id"),
                              ("kspcb", "kspcb_record_id"),
                              ("bescom", "bescom_record_id")]:
                for rid in parse(row.get(col, "")):
                    record_to_entity[(src, rid)] = row["entity_id"]

    canon = {}
    with get_db() as db:
        for orm in db.execute(select(CanonicalRecordORM)).scalars():
            canon[(orm.source_system, orm.source_record_id)] = _orm_to_canonical(orm)

    items = sorted([k for k in record_to_entity if k in canon])
    scorer = get_scorer()

    y_true, y_prob = [], []
    geo_seen = set()
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            same = record_to_entity[items[i]] == record_to_entity[items[j]]
            sp = scorer.score(canon[items[i]], canon[items[j]], fast=True)
            y_true.append(1 if same else 0)
            y_prob.append(sp.calibrated_probability)
            geo = sp.feature_vector.get("addr_geo_distance_km", -1.0)
            if geo != -1.0:
                geo_seen.add(round(float(geo), 3))

    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    brier = sum((p - t) ** 2 for p, t in zip(y_prob, y_true)) / len(y_true)
    return {
        "n_pairs": len(y_true),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "brier": round(brier, 5),
        "distinct_geo_distances": len(geo_seen),
    }


def _retrain():
    from ubid.api.routers.admin import (
        _load_reviewer_labelled_pairs, _load_ground_truth_pairs, _featurise,
    )
    pairs = _load_reviewer_labelled_pairs() + _load_ground_truth_pairs()
    X, y = _featurise(pairs)
    if X:
        get_scorer().train(X, y)


def _print_feature_importance():
    scorer = get_scorer()
    if not scorer._trained:
        return
    booster = scorer._model.booster_
    importances = booster.feature_importance(importance_type="gain")
    feat_names = feat_module.FEATURE_NAMES
    paired = sorted(zip(feat_names, importances), key=lambda x: -x[1])
    total = sum(importances) or 1
    print("\nFeature importance (gain) — top 15:")
    for name, imp in paired[:15]:
        bar_len = int(40 * imp / paired[0][1]) if paired[0][1] > 0 else 0
        pct = 100 * imp / total
        marker = " <-- GEO FEATURE" if name == "addr_geo_distance_km" else ""
        print(f"  {name:32s} {'#' * bar_len:40s} {pct:5.1f}%{marker}")


def main():
    print("=" * 72)
    print("A/B GEOCODING COMPARISON: dict-only vs. Nominatim + dict")
    print("=" * 72)

    with get_db() as db:
        rows = list(db.execute(select(CanonicalRecordORM)).scalars())
    snapshot = {str(r.canonical_id): (r.latitude, r.longitude) for r in rows}
    n_with_coords = sum(1 for v in snapshot.values() if v[0] is not None)
    print(f"\nSnapshot taken: {n_with_coords}/{len(snapshot)} records have lat/lng.")

    print("\n[Round A] Wiping coords, running dict-only geocoding...")
    n_dict_only = 0
    distinct_dict = set()
    with get_db() as db:
        for orm in db.execute(select(CanonicalRecordORM)).scalars():
            rec = _orm_to_canonical(orm)
            coords = (
                lookup_locality(rec.locality_canonical)
                or lookup_pin(rec.pin_code)
                or lookup_district(rec.district)
            )
            if coords:
                orm.latitude, orm.longitude = coords
                n_dict_only += 1
                distinct_dict.add((round(coords[0], 4), round(coords[1], 4)))
            else:
                orm.latitude = None
                orm.longitude = None
    print(f"  {n_dict_only} records geocoded by dict.")
    print(f"  Distinct (lat, lng) clusters: {len(distinct_dict)}")

    print("  Retraining...")
    _retrain()
    metrics_a = _eval_pairwise()
    print(f"  Eval (dict-only): {metrics_a}")

    print("\n[Round B] Restoring Nominatim+dict coords from snapshot...")
    n_distinct_from_dict = 0
    distinct_b = set()
    with get_db() as db:
        for orm in db.execute(select(CanonicalRecordORM)).scalars():
            cid = str(orm.canonical_id)
            snap = snapshot.get(cid)
            if snap and snap[0] is not None:
                orm.latitude, orm.longitude = snap
                distinct_b.add((round(snap[0], 4), round(snap[1], 4)))
                rec = _orm_to_canonical(orm)
                dict_coords = (
                    lookup_locality(rec.locality_canonical)
                    or lookup_pin(rec.pin_code)
                    or lookup_district(rec.district)
                )
                if dict_coords and (
                    abs(dict_coords[0] - snap[0]) > 1e-3
                    or abs(dict_coords[1] - snap[1]) > 1e-3
                ):
                    n_distinct_from_dict += 1
    print(f"  Records with Nominatim-distinct coords: {n_distinct_from_dict}")
    print(f"  Distinct (lat, lng) clusters: {len(distinct_b)}")

    print("  Retraining...")
    _retrain()
    metrics_b = _eval_pairwise()
    print(f"  Eval (Nominatim+dict): {metrics_b}")

    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)
    print(f"{'Metric':<32s}  {'Dict-only':>10s}  {'Nominatim':>10s}  {'Delta':>8s}")
    print("-" * 72)
    for k in ("precision", "recall", "f1", "brier", "distinct_geo_distances"):
        a = metrics_a[k]
        b = metrics_b[k]
        delta = b - a
        sign = "+" if delta > 0 else ""
        print(f"{k:<32s}  {a:>10.4f}  {b:>10.4f}  {sign}{delta:>7.4f}")

    print(f"\nDistinct coordinate clusters:")
    print(f"  Dict-only:       {len(distinct_dict)}")
    print(f"  Nominatim+dict:  {len(distinct_b)}")
    diff_clusters = len(distinct_b) - len(distinct_dict)
    print(f"  -> Nominatim adds {diff_clusters} new coord clusters")
    print(f"  -> {n_distinct_from_dict} records now distinguishable from same-locality peers")

    _print_feature_importance()


if __name__ == "__main__":
    main()
