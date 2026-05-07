"""Train the LightGBM pairwise scorer using ground_truth_links.csv.

Builds positive pairs (records belonging to the same entity) and negative
pairs (records from different entities), computes the 25-d feature vector
for each, fits LightGBM, calibrates with isotonic regression, and saves the
artefacts to MODEL_DIR.

Run:
    docker compose exec ubid-api python /app/scripts/train_scorer.py
"""
from __future__ import annotations
import csv
import random
import sys
from pathlib import Path

# Ensure src/ is on the path when run via `docker exec`
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import select  # noqa: E402

from ubid.api.routers.ingest import _orm_to_canonical  # noqa: E402
from ubid.scoring import features as feat_module  # noqa: E402
from ubid.scoring.lgbm_scorer import get_scorer  # noqa: E402
from ubid.storage.postgres import CanonicalRecordORM, get_db  # noqa: E402

GROUND_TRUTH = _REPO / "data" / "synthetic" / "ground_truth_links.csv"

# Negative pair sampling — keep training balanced.
NEG_PER_POS = 3
RANDOM_SEED = 42


def parse_record_ids(field: str) -> list[str]:
    if not field:
        return []
    return [x.strip() for x in field.split(";") if x.strip()]


def load_entities() -> list[dict]:
    """Read ground truth and return list of entities with (source, record_id) tuples."""
    entities = []
    with open(GROUND_TRUTH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            members = []
            for src, col in [
                ("ekarmika", "ekarmika_record_id"),
                ("fbis", "fbis_record_id"),
                ("kspcb", "kspcb_record_id"),
                ("bescom", "bescom_record_id"),
            ]:
                for rid in parse_record_ids(row.get(col, "")):
                    members.append((src, rid))
            entities.append({"entity_id": row["entity_id"], "members": members})
    return entities


def fetch_canonical_map(entities: list[dict]) -> dict[tuple[str, str], object]:
    """Fetch CanonicalRecord objects for every (source, record_id) we need."""
    needed: set[tuple[str, str]] = set()
    for e in entities:
        for m in e["members"]:
            needed.add(m)

    out: dict[tuple[str, str], object] = {}
    with get_db() as db:
        for src, rid in needed:
            orm = db.execute(
                select(CanonicalRecordORM).where(
                    CanonicalRecordORM.source_system == src,
                    CanonicalRecordORM.source_record_id == rid,
                )
            ).scalar_one_or_none()
            if orm is not None:
                out[(src, rid)] = _orm_to_canonical(orm)
    return out


def build_pairs(entities: list[dict], canon: dict) -> tuple[list, list]:
    """Return (X, y) — feature vectors and 0/1 labels."""
    rng = random.Random(RANDOM_SEED)

    # Positive pairs: every unordered combination within an entity
    positive_pairs: list[tuple] = []
    for e in entities:
        present = [m for m in e["members"] if m in canon]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                positive_pairs.append((present[i], present[j]))

    # Negative pairs: random pairs from different entities
    all_members = [(e["entity_id"], m) for e in entities for m in e["members"] if m in canon]
    negative_pairs: list[tuple] = []
    target_neg = NEG_PER_POS * len(positive_pairs)
    seen: set = set()
    attempts = 0
    while len(negative_pairs) < target_neg and attempts < target_neg * 10:
        attempts += 1
        a = rng.choice(all_members)
        b = rng.choice(all_members)
        if a[0] == b[0]:
            continue  # same entity — skip
        key = tuple(sorted([a[1], b[1]]))
        if key in seen:
            continue
        seen.add(key)
        negative_pairs.append((a[1], b[1]))

    print(f"Positive pairs: {len(positive_pairs)}")
    print(f"Negative pairs: {len(negative_pairs)}")

    X: list[list[float]] = []
    y: list[int] = []

    for a, b in positive_pairs:
        ra, rb = canon[a], canon[b]
        fv = feat_module.compute(ra, rb)
        X.append(feat_module.to_vector(fv))
        y.append(1)

    for a, b in negative_pairs:
        ra, rb = canon[a], canon[b]
        fv = feat_module.compute(ra, rb)
        X.append(feat_module.to_vector(fv))
        y.append(0)

    return X, y


def main():
    if not GROUND_TRUTH.exists():
        print(f"Ground truth file not found: {GROUND_TRUTH}", file=sys.stderr)
        sys.exit(1)

    entities = load_entities()
    print(f"Loaded {len(entities)} entities from ground truth")

    canon = fetch_canonical_map(entities)
    print(f"Resolved {len(canon)} canonical records out of "
          f"{sum(len(e['members']) for e in entities)} expected")

    X, y = build_pairs(entities, canon)
    print(f"Total training pairs: {len(X)} ({sum(y)} pos / {len(y) - sum(y)} neg)")

    scorer = get_scorer()
    scorer.train(X, y)
    print("LightGBM scorer trained and saved.")


if __name__ == "__main__":
    main()
