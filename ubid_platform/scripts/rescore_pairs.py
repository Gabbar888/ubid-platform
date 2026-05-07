"""Re-score every linkage pair with the currently-loaded LightGBM model.

Pairs were originally scored when the model was untrained (heuristic mode).
After training, the calibrated probabilities and feature vectors should be
recomputed so clustering uses the model's confidence.

Run:
    docker compose exec ubid-api python /app/scripts/rescore_pairs.py
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import select  # noqa: E402

from ubid.api.routers.ingest import _orm_to_canonical  # noqa: E402
from ubid.scoring.lgbm_scorer import get_scorer  # noqa: E402
from ubid.storage.postgres import (  # noqa: E402
    CanonicalRecordORM,
    LinkagePairORM,
    get_db,
)


def main():
    scorer = get_scorer()
    if not scorer._trained:
        print("Scorer is not trained — train_scorer.py must run first.")
        sys.exit(1)

    with get_db() as db:
        canon_by_id = {
            str(c.canonical_id): _orm_to_canonical(c)
            for c in db.execute(select(CanonicalRecordORM)).scalars()
        }
        pairs = list(db.execute(select(LinkagePairORM)).scalars())
        print(f"Re-scoring {len(pairs)} pairs against {len(canon_by_id)} canonical records...")

        updated = 0
        skipped = 0
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
            if updated % 100 == 0:
                print(f"  ...{updated}/{len(pairs)}")

        print(f"\nUpdated {updated} pairs, skipped {skipped}")


if __name__ == "__main__":
    main()
