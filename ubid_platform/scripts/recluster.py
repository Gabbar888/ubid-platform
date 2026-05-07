"""Re-cluster all canonical records using the existing scored linkage pairs.

The original ingest pipeline writes linkage_pairs but never actually merges
records into shared UBIDs — every record gets its own UBID. This script
fixes that retroactively:

  1. Load every CanonicalRecord and every LinkagePair from Postgres.
  2. Pull any reviewer-issued must-link / cannot-link constraints.
  3. Run greedy correlation clustering (correlation_cluster.cluster).
  4. Wipe the existing UBID assignments and rebuild from the cluster result.
  5. Invalidate Redis caches.

After running, the verdicts script should be re-run so each newly-merged
UBID gets its evidence aggregated.

Run:
    docker compose exec ubid-api python /app/scripts/recluster.py
"""
from __future__ import annotations
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import select, text  # noqa: E402

from ubid.clustering.correlation_cluster import cluster  # noqa: E402
from ubid.schema.canonical import ScoredPair, ConstraintType  # noqa: E402
from ubid.storage import redis_cache  # noqa: E402
from ubid.storage.postgres import (  # noqa: E402
    CanonicalRecordORM,
    LinkagePairORM,
    UBIDNodeORM,
    UBIDSourceLinkORM,
    ActivityVerdictORM,
    get_db,
)


def main():
    with get_db() as db:
        canon_rows = list(db.execute(select(CanonicalRecordORM)).scalars())
        print(f"Canonical records: {len(canon_rows)}")

        # Build scored pairs from DB
        pair_rows = list(db.execute(select(LinkagePairORM)).scalars())
        print(f"Linkage pairs: {len(pair_rows)}")
        scored_pairs = [
            ScoredPair(
                canonical_id_a=str(p.canonical_id_a),
                canonical_id_b=str(p.canonical_id_b),
                raw_score=p.raw_score,
                calibrated_probability=p.calibrated_probability,
                deterministic_tier_fired=p.deterministic_tier_fired,
                deterministic_result=p.deterministic_result,
                feature_vector=p.feature_vector or {},
                shap_contributions=p.shap_contributions or {},
                shared_blocks=p.shared_blocks or [],
            )
            for p in pair_rows
        ]

        # Reviewer constraints (must-link / cannot-link) — optional, may not exist yet
        constraints: list[tuple[str, str, ConstraintType]] = []
        try:
            crows = db.execute(text("""
                SELECT canonical_id_a, canonical_id_b, constraint_type
                FROM linkage_constraints
            """)).fetchall()
            for ca, cb, ctype in crows:
                ct = ConstraintType.MUST_LINK if str(ctype).lower().startswith("must") else ConstraintType.CANNOT_LINK
                constraints.append((str(ca), str(cb), ct))
        except Exception:
            pass
        print(f"Constraints: {len(constraints)}")

    result = cluster(scored_pairs, constraints)

    print(f"\nClustering produced {len(result.ubid_to_canonical)} UBIDs")
    sizes = sorted([len(v) for v in result.ubid_to_canonical.values()], reverse=True)
    print(f"Cluster size distribution: top10={sizes[:10]} ... singletons={sizes.count(1)}")

    # Make sure every canonical_id has a UBID — singletons may be missing
    # because the clustering only emits clusters with positive edges.
    seen = set(result.canonical_to_ubid.keys())
    for orm in canon_rows:
        cid = str(orm.canonical_id)
        if cid not in seen:
            ubid = str(uuid.uuid4())
            result.canonical_to_ubid[cid] = ubid
            result.ubid_to_canonical.setdefault(ubid, []).append(cid)

    print(f"After singletons: {len(result.ubid_to_canonical)} UBIDs covering "
          f"{len(result.canonical_to_ubid)} canonical records")

    # ── Persist new assignments ────────────────────────────────────────────────
    canon_by_id = {str(c.canonical_id): c for c in canon_rows}
    now = datetime.now(timezone.utc)

    with get_db() as db:
        # Wipe existing assignments
        db.execute(text("DELETE FROM activity_verdicts"))
        db.execute(text("DELETE FROM ubid_source_links"))
        db.execute(text("DELETE FROM ubid_nodes"))

        for ubid, members in result.ubid_to_canonical.items():
            # Pick a representative for UBID-level fields (pin/district/sector)
            rep = canon_by_id.get(members[0])
            db.add(UBIDNodeORM(
                ubid=ubid,
                pin_code=rep.pin_code if rep else None,
                district=rep.district if rep else None,
                sector_canonical=(rep.nic_code or rep.sector_raw) if rep else None,
                created_at=now,
                updated_at=now,
            ))
            for cid in members:
                db.add(UBIDSourceLinkORM(
                    link_id=str(uuid.uuid4()),
                    ubid=ubid,
                    canonical_id=cid,
                    linked_at=now,
                    linked_by="recluster",
                    confidence=1.0,
                ))

    # Refresh Redis cache from scratch
    with get_db() as db:
        rows = db.execute(text("""
            SELECT cr.source_system, cr.source_record_id, usl.ubid
            FROM canonical_records cr
            JOIN ubid_source_links usl ON usl.canonical_id = cr.canonical_id
        """)).fetchall()
        for src, rid, ubid in rows:
            redis_cache.set_ubid_for_source(src, rid, str(ubid))
            redis_cache.invalidate_verdict(str(ubid))

    print(f"\nRedis cache refreshed for {len(rows)} source records")
    print("Done. Run compute_verdicts.py next to recompute activity verdicts.")


if __name__ == "__main__":
    main()
