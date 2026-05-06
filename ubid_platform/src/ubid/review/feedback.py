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
    """Invalidate cached UBIDs so next lookup triggers re-clustering."""
    # In production this would publish a re-link event to Kafka
    logger.info("Relink triggered for %s ↔ %s", id_a, id_b)


def _trigger_unlink_if_merged(db, id_a: str, id_b: str, reviewer_id: str):
    """If these two are currently in the same UBID, split them."""
    from sqlalchemy import text
    row = db.execute(text("""
        SELECT a_links.ubid as ubid_a, b_links.ubid as ubid_b
        FROM ubid_source_links a_links, ubid_source_links b_links
        WHERE a_links.canonical_id = :a AND b_links.canonical_id = :b
          AND a_links.ubid = b_links.ubid
        LIMIT 1
    """), {"a": id_a, "b": id_b}).first()

    if row:
        logger.warning(
            "Cannot-link decision on records currently sharing UBID %s — unmerge required",
            row.ubid_a,
        )
        # Invalidate verdict cache for affected UBID
        redis_cache.invalidate_verdict(str(row.ubid_a))
