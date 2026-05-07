"""Reviewer feedback processing.

Decision types:
  confirm_match  → must-link constraint + training label (is_match=True)
  reject         → cannot-link constraint + training label (is_match=False)
  defer          → escalate to senior tier
  flag_quality   → mark source record for data-quality review

Every decision is versioned and reviewer-attributed.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ubid.storage.postgres import (
    get_db, ReviewerQueueORM, ReviewerDecisionORM,
    LinkagePairORM, LinkageConstraintORM, TrainingLabelORM
)
from ubid.storage import redis_cache

logger = logging.getLogger(__name__)


def apply_decision(payload: dict[str, Any]):
    """Process a reviewer decision. Called from Kafka consumer or API."""
    queue_id = payload.get("queue_id")
    pair_id = payload["pair_id"]
    canonical_id_a = payload["canonical_id_a"]
    canonical_id_b = payload["canonical_id_b"]
    decision = payload["decision"]
    reviewer_id = payload["reviewer_id"]
    reviewer_tier = payload.get("reviewer_tier", "junior")
    notes = payload.get("notes")

    with get_db() as db:
        # Log decision
        dec = ReviewerDecisionORM(
            decision_id=str(uuid.uuid4()),
            queue_id=queue_id,
            pair_id=pair_id,
            canonical_id_a=canonical_id_a,
            canonical_id_b=canonical_id_b,
            decision=decision,
            reviewer_id=reviewer_id,
            reviewer_tier=reviewer_tier,
            notes=notes,
            decided_at=datetime.now(timezone.utc),
            is_training_label=(decision in ("confirm_match", "reject")),
        )
        db.add(dec)

        # Update queue item status
        if queue_id:
            q = db.get(ReviewerQueueORM, queue_id)
            if q:
                q.status = "deferred" if decision == "defer" else "decided"
                q.updated_at = datetime.now(timezone.utc)

        # Update pair decision
        pair = db.get(LinkagePairORM, pair_id)
        if pair:
            pair.decision = decision
            pair.decided_at = datetime.now(timezone.utc)
            pair.decided_by = reviewer_id

        if decision == "confirm_match":
            _write_constraint(db, canonical_id_a, canonical_id_b, "must_link", reviewer_id, notes)
            _write_training_label(db, canonical_id_a, canonical_id_b, True)
            _trigger_relink(canonical_id_a, canonical_id_b)

        elif decision == "reject":
            _write_constraint(db, canonical_id_a, canonical_id_b, "cannot_link", reviewer_id, notes)
            _write_training_label(db, canonical_id_a, canonical_id_b, False)
            _trigger_unlink_if_merged(db, canonical_id_a, canonical_id_b, reviewer_id)

        elif decision == "defer" and reviewer_tier == "junior":
            # Re-enqueue at higher priority for senior review
            if queue_id:
                q = db.get(ReviewerQueueORM, queue_id)
                if q:
                    q.status = "pending"
                    q.priority_score = min(q.priority_score + 0.3, 1.0)
                    q.updated_at = datetime.now(timezone.utc)


def _write_constraint(db, id_a: str, id_b: str, ctype: str, reviewer: str, notes: Any):
    # Normalize ordering to avoid duplicate constraint with reversed IDs
    a, b = sorted([id_a, id_b])
    existing = db.execute(
        select(LinkageConstraintORM).where(
            LinkageConstraintORM.canonical_id_a == a,
            LinkageConstraintORM.canonical_id_b == b,
        )
    ).scalar_one_or_none()

    if existing:
        existing.constraint_type = ctype  # senior can override junior
        existing.created_by = reviewer
        existing.notes = notes
    else:
        db.add(LinkageConstraintORM(
            constraint_id=str(uuid.uuid4()),
            canonical_id_a=a,
            canonical_id_b=b,
            constraint_type=ctype,
            created_by=reviewer,
            created_at=datetime.now(timezone.utc),
            notes=notes,
        ))


def _write_training_label(db, id_a: str, id_b: str, is_match: bool):
    a, b = sorted([id_a, id_b])
    existing = db.execute(
        select(TrainingLabelORM).where(
            TrainingLabelORM.canonical_id_a == a,
            TrainingLabelORM.canonical_id_b == b,
        )
    ).scalar_one_or_none()
    if existing:
        existing.is_match = is_match
    else:
        db.add(TrainingLabelORM(
            label_id=str(uuid.uuid4()),
            canonical_id_a=a,
            canonical_id_b=b,
            is_match=is_match,
            source="reviewer",
            created_at=datetime.now(timezone.utc),
        ))


def _trigger_relink(id_a: str, id_b: str):
    """Apply a must-link decision by merging the two records into one UBID.

    If only one side has a UBID, the other gets attached to it. If both have
    different UBIDs we merge them (lower-uuid wins as canonical, all source
    links re-pointed). If neither has a UBID, mint one.
    """
    from sqlalchemy import text
    from ubid.storage.postgres import (
        get_db, UBIDNodeORM, UBIDSourceLinkORM, CanonicalRecordORM,
    )

    with get_db() as db:
        rows = db.execute(text("""
            SELECT canonical_id, ubid FROM ubid_source_links
            WHERE canonical_id IN (:a, :b)
        """), {"a": id_a, "b": id_b}).fetchall()
        link_map = {str(c): str(u) for c, u in rows}

        ubid_a = link_map.get(id_a)
        ubid_b = link_map.get(id_b)
        now = datetime.now(timezone.utc)

        def _attach(canonical_id: str, target_ubid: str):
            db.add(UBIDSourceLinkORM(
                link_id=str(uuid.uuid4()),
                ubid=target_ubid,
                canonical_id=canonical_id,
                linked_at=now,
                linked_by="reviewer:must_link",
                confidence=1.0,
            ))
            cr = db.get(CanonicalRecordORM, canonical_id)
            if cr is not None:
                redis_cache.set_ubid_for_source(cr.source_system, cr.source_record_id, target_ubid)

        if ubid_a and ubid_b and ubid_a != ubid_b:
            target = sorted([ubid_a, ubid_b])[0]
            old = ubid_b if target == ubid_a else ubid_a
            db.execute(text("UPDATE ubid_source_links SET ubid = :t WHERE ubid = :o"),
                       {"t": target, "o": old})
            db.execute(text("DELETE FROM activity_verdicts WHERE ubid = :o"), {"o": old})
            db.execute(text("DELETE FROM ubid_nodes WHERE ubid = :o"), {"o": old})
            redis_cache.invalidate_verdict(old)
            redis_cache.invalidate_verdict(target)
            # Refresh redis mapping for everything that was on the old UBID
            for cid_row in db.execute(text("""
                SELECT cr.source_system, cr.source_record_id
                FROM canonical_records cr
                JOIN ubid_source_links usl ON usl.canonical_id = cr.canonical_id
                WHERE usl.ubid = :t
            """), {"t": target}).fetchall():
                redis_cache.set_ubid_for_source(cid_row[0], cid_row[1], target)
            logger.info("Reviewer must-link merged UBID %s → %s", old, target)
        elif ubid_a and not ubid_b:
            _attach(id_b, ubid_a)
            redis_cache.invalidate_verdict(ubid_a)
        elif ubid_b and not ubid_a:
            _attach(id_a, ubid_b)
            redis_cache.invalidate_verdict(ubid_b)
        elif not ubid_a and not ubid_b:
            new_ubid = str(uuid.uuid4())
            rep = db.get(CanonicalRecordORM, id_a)
            db.add(UBIDNodeORM(
                ubid=new_ubid,
                pin_code=rep.pin_code if rep else None,
                district=rep.district if rep else None,
                sector_canonical=(rep.nic_code or rep.sector_raw) if rep else None,
                created_at=now,
                updated_at=now,
            ))
            db.flush()
            _attach(id_a, new_ubid)
            _attach(id_b, new_ubid)


def _trigger_unlink_if_merged(db, id_a: str, id_b: str, reviewer_id: str):
    """Apply a cannot-link decision: if the two records currently share a
    UBID, peel record B off into a fresh UBID and invalidate verdicts.
    """
    from sqlalchemy import text
    from ubid.storage.postgres import UBIDNodeORM, UBIDSourceLinkORM, CanonicalRecordORM

    row = db.execute(text("""
        SELECT a_links.ubid AS ubid
        FROM ubid_source_links a_links
        JOIN ubid_source_links b_links ON a_links.ubid = b_links.ubid
        WHERE a_links.canonical_id = :a AND b_links.canonical_id = :b
        LIMIT 1
    """), {"a": id_a, "b": id_b}).first()

    if not row:
        return  # Already separate, nothing to do

    shared_ubid = str(row.ubid)
    now = datetime.now(timezone.utc)

    # Peel id_b onto a brand-new UBID
    new_ubid = str(uuid.uuid4())
    rep = db.get(CanonicalRecordORM, id_b)
    db.add(UBIDNodeORM(
        ubid=new_ubid,
        pin_code=rep.pin_code if rep else None,
        district=rep.district if rep else None,
        sector_canonical=(rep.nic_code or rep.sector_raw) if rep else None,
        created_at=now,
        updated_at=now,
    ))
    # Flush so the new UBID node satisfies the FK on ubid_source_links
    db.flush()
    db.execute(text("""
        UPDATE ubid_source_links SET ubid = :n, linked_by = 'reviewer:cannot_link',
                                       linked_at = :t
        WHERE canonical_id = :b
    """), {"n": new_ubid, "b": id_b, "t": now})

    if rep is not None:
        redis_cache.set_ubid_for_source(rep.source_system, rep.source_record_id, new_ubid)
    redis_cache.invalidate_verdict(shared_ubid)
    redis_cache.invalidate_verdict(new_ubid)
    db.execute(text("DELETE FROM activity_verdicts WHERE ubid IN (:a, :b)"),
               {"a": shared_ubid, "b": new_ubid})
    logger.info("Reviewer cannot-link split UBID %s → %s peeled off (record %s)",
                shared_ubid, new_ubid, id_b)
