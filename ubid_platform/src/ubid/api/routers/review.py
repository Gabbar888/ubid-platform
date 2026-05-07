"""Reviewer console API."""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ubid.review.queue import get_pending_items, queue_stats
from ubid.review.feedback import apply_decision
from ubid.activity.quarantine import get_quarantine_stats
from ubid.canonicalize.locality_normalizer import add_synonym

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/queue")
def get_review_queue(limit: int = 20, reviewer_tier: str = "junior"):
    """Get top-priority items pending review.

    Senior reviewers see escalated items first (deferred decisions get a
    priority boost in feedback._trigger_relink/defer logic).
    """
    return {
        "items": get_pending_items(limit=limit, reviewer_tier=reviewer_tier),
        "stats": queue_stats(),
        "reviewer_tier": reviewer_tier,
    }


@router.get("/stats")
def get_stats():
    return {
        "queue": queue_stats(),
        "quarantine": get_quarantine_stats(),
    }


@router.get("/activity")
def get_reviewer_activity(
    reviewer_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List recent reviewer decisions, optionally filtered by reviewer.
    Returns the decision plus the records involved for context.
    """
    from sqlalchemy import text
    from ubid.storage.postgres import get_db

    where = "WHERE 1=1"
    params: dict = {"limit": limit, "offset": offset}
    if reviewer_id:
        where += " AND rd.reviewer_id = :reviewer_id"
        params["reviewer_id"] = reviewer_id

    with get_db() as db:
        total = db.execute(text(f"""
            SELECT COUNT(*) FROM reviewer_decisions rd {where}
        """), params).scalar() or 0

        rows = db.execute(text(f"""
            SELECT rd.decision_id, rd.pair_id, rd.canonical_id_a, rd.canonical_id_b,
                   rd.decision, rd.reviewer_id, rd.reviewer_tier, rd.notes, rd.decided_at,
                   ca.name_raw AS name_a, ca.source_system AS src_a, ca.source_record_id AS rid_a,
                   cb.name_raw AS name_b, cb.source_system AS src_b, cb.source_record_id AS rid_b,
                   lp.calibrated_probability
            FROM reviewer_decisions rd
            LEFT JOIN canonical_records ca ON ca.canonical_id = rd.canonical_id_a
            LEFT JOIN canonical_records cb ON cb.canonical_id = rd.canonical_id_b
            LEFT JOIN linkage_pairs lp ON lp.pair_id = rd.pair_id
            {where}
            ORDER BY rd.decided_at DESC
            LIMIT :limit OFFSET :offset
        """), params).fetchall()

        # Per-reviewer summary
        summary_rows = db.execute(text("""
            SELECT reviewer_id, reviewer_tier, decision, COUNT(*) as n
            FROM reviewer_decisions
            GROUP BY reviewer_id, reviewer_tier, decision
            ORDER BY reviewer_id, decision
        """)).fetchall()

    by_reviewer: dict[str, dict] = {}
    for s in summary_rows:
        rid = s.reviewer_id
        if rid not in by_reviewer:
            by_reviewer[rid] = {"tier": s.reviewer_tier, "counts": {}, "total": 0}
        by_reviewer[rid]["counts"][s.decision] = s.n
        by_reviewer[rid]["total"] += s.n

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "decision_id": str(r.decision_id),
                "pair_id": str(r.pair_id),
                "decision": r.decision,
                "reviewer_id": r.reviewer_id,
                "reviewer_tier": r.reviewer_tier,
                "notes": r.notes,
                "decided_at": str(r.decided_at) if r.decided_at else None,
                "calibrated_probability": (
                    float(r.calibrated_probability) if r.calibrated_probability is not None else None
                ),
                "record_a": {
                    "canonical_id": str(r.canonical_id_a),
                    "source_system": r.src_a,
                    "source_record_id": r.rid_a,
                    "name_raw": r.name_a,
                },
                "record_b": {
                    "canonical_id": str(r.canonical_id_b),
                    "source_system": r.src_b,
                    "source_record_id": r.rid_b,
                    "name_raw": r.name_b,
                },
            }
            for r in rows
        ],
        "by_reviewer": by_reviewer,
    }


class DecisionRequest(BaseModel):
    queue_id: Optional[str] = None
    pair_id: str
    canonical_id_a: str
    canonical_id_b: str
    decision: str  # confirm_match | reject | defer | flag_quality
    reviewer_id: str
    reviewer_tier: str = "junior"
    notes: Optional[str] = None


@router.post("/decide")
def submit_decision(body: DecisionRequest):
    valid = {"confirm_match", "reject", "defer", "flag_quality"}
    if body.decision not in valid:
        raise HTTPException(400, f"Decision must be one of {valid}")

    apply_decision(body.model_dump())

    # Publish to Kafka for async processing
    try:
        from ubid.kafka.producer import publish_review_decision
        publish_review_decision(body.model_dump())
    except Exception as e:
        logger.warning("Kafka publish skipped: %s", e)

    return {"status": "accepted", "decision": body.decision}


class SynonymRequest(BaseModel):
    variant: str
    canonical: str
    reviewer_id: str


class UnmergeRequest(BaseModel):
    canonical_id_a: str
    canonical_id_b: str
    reviewer_id: str
    reviewer_tier: str = "junior"
    notes: Optional[str] = None


class ApproveUBIDRequest(BaseModel):
    ubid: str
    reviewer_id: str
    reviewer_tier: str = "junior"
    notes: Optional[str] = None


@router.post("/approve-ubid")
def approve_ubid(body: ApproveUBIDRequest):
    """Confirm that every record currently in this UBID is correctly merged.

    Writes a must-link constraint between every pair of members so future
    re-clusterings or model retrainings won't accidentally split them. Also
    creates a synthetic linkage_pair (when needed) and a reviewer_decision
    per pair so the audit trail is complete.
    """
    import uuid as _uuid
    from datetime import datetime, timezone
    from sqlalchemy import select, text
    from ubid.storage.postgres import (
        get_db, LinkagePairORM, LinkageConstraintORM,
        ReviewerDecisionORM, TrainingLabelORM, UBIDNodeORM,
    )

    with get_db() as db:
        node = db.get(UBIDNodeORM, body.ubid)
        if not node:
            raise HTTPException(404, f"UBID {body.ubid} not found")

        members = db.execute(text("""
            SELECT canonical_id FROM ubid_source_links WHERE ubid = :u
            ORDER BY canonical_id
        """), {"u": body.ubid}).fetchall()
        member_ids = [str(m.canonical_id) for m in members]

    if len(member_ids) < 2:
        return {
            "status": "no-op",
            "ubid": body.ubid,
            "members": len(member_ids),
            "constraints_added": 0,
            "decisions_logged": 0,
            "message": "Single-record UBID — nothing to approve",
        }

    constraints_added = 0
    decisions_logged = 0
    now = datetime.now(timezone.utc)

    with get_db() as db:
        for i in range(len(member_ids)):
            for j in range(i + 1, len(member_ids)):
                a, b = sorted([member_ids[i], member_ids[j]])

                # 1. Find or create a linkage_pair so the FK is valid
                pair = db.execute(
                    select(LinkagePairORM).where(
                        LinkagePairORM.canonical_id_a == a,
                        LinkagePairORM.canonical_id_b == b,
                    )
                ).scalar_one_or_none()
                if not pair:
                    pair = LinkagePairORM(
                        pair_id=str(_uuid.uuid4()),
                        canonical_id_a=a,
                        canonical_id_b=b,
                        raw_score=1.0,
                        calibrated_probability=1.0,
                        deterministic_tier_fired=False,
                        deterministic_result=None,
                        feature_vector={},
                        shap_contributions={},
                        shared_blocks=[],
                        scored_at=now,
                    )
                    db.add(pair)
                    db.flush()

                # 2. Add a must_link constraint (idempotent)
                existing_c = db.execute(
                    select(LinkageConstraintORM).where(
                        LinkageConstraintORM.canonical_id_a == a,
                        LinkageConstraintORM.canonical_id_b == b,
                    )
                ).scalar_one_or_none()
                if existing_c:
                    if existing_c.constraint_type != "must_link":
                        existing_c.constraint_type = "must_link"
                        existing_c.created_by = body.reviewer_id
                        existing_c.notes = body.notes
                else:
                    db.add(LinkageConstraintORM(
                        constraint_id=str(_uuid.uuid4()),
                        canonical_id_a=a,
                        canonical_id_b=b,
                        constraint_type="must_link",
                        created_by=body.reviewer_id,
                        created_at=now,
                        notes=body.notes,
                    ))
                    constraints_added += 1

                # 3. Add a training label (idempotent)
                existing_l = db.execute(
                    select(TrainingLabelORM).where(
                        TrainingLabelORM.canonical_id_a == a,
                        TrainingLabelORM.canonical_id_b == b,
                    )
                ).scalar_one_or_none()
                if existing_l:
                    existing_l.is_match = True
                else:
                    db.add(TrainingLabelORM(
                        label_id=str(_uuid.uuid4()),
                        canonical_id_a=a,
                        canonical_id_b=b,
                        is_match=True,
                        source="reviewer_audit",
                        created_at=now,
                    ))

                # 4. Log a reviewer_decision row for the audit trail
                db.add(ReviewerDecisionORM(
                    decision_id=str(_uuid.uuid4()),
                    queue_id=None,
                    pair_id=str(pair.pair_id),
                    canonical_id_a=a,
                    canonical_id_b=b,
                    decision="confirm_match",
                    reviewer_id=body.reviewer_id,
                    reviewer_tier=body.reviewer_tier,
                    notes=body.notes or "ubid-audit approval",
                    decided_at=now,
                    is_training_label=True,
                ))
                decisions_logged += 1

    return {
        "status": "approved",
        "ubid": body.ubid,
        "members": len(member_ids),
        "pairs_processed": decisions_logged,
        "new_constraints": constraints_added,
        "decisions_logged": decisions_logged,
    }


@router.post("/unmerge")
def unmerge_pair(body: UnmergeRequest):
    """Split two records that are currently sharing a UBID.

    Works whether the merge came from auto-linking, a previous reviewer
    must-link, or from the same record being clustered transitively. The
    operation:
      1. Locates or creates a linkage_pair row for these two canonical_ids
         (so the decision has a valid foreign key).
      2. Submits a 'reject' decision through the standard feedback path,
         which writes a cannot_link constraint, peels one record into a
         fresh UBID, and invalidates affected verdict caches.
    """
    import uuid as _uuid
    from datetime import datetime, timezone
    from sqlalchemy import select, text
    from ubid.storage.postgres import get_db, LinkagePairORM

    a, b = sorted([body.canonical_id_a, body.canonical_id_b])

    with get_db() as db:
        # Confirm both records exist
        row = db.execute(text("""
            SELECT
              (SELECT 1 FROM canonical_records WHERE canonical_id = :a) AS a_exists,
              (SELECT 1 FROM canonical_records WHERE canonical_id = :b) AS b_exists,
              (SELECT u1.ubid FROM ubid_source_links u1
                 JOIN ubid_source_links u2 ON u1.ubid = u2.ubid
                 WHERE u1.canonical_id = :a AND u2.canonical_id = :b LIMIT 1) AS shared_ubid
        """), {"a": a, "b": b}).first()

        if not (row and row.a_exists and row.b_exists):
            raise HTTPException(404, "One or both canonical_ids not found")
        if not row.shared_ubid:
            raise HTTPException(409, "These two records are not currently in the same UBID")

        # Find or create a linkage_pair so the decision FK is valid
        pair = db.execute(
            select(LinkagePairORM).where(
                LinkagePairORM.canonical_id_a == a,
                LinkagePairORM.canonical_id_b == b,
            )
        ).scalar_one_or_none()

        if not pair:
            pair = LinkagePairORM(
                pair_id=str(_uuid.uuid4()),
                canonical_id_a=a,
                canonical_id_b=b,
                raw_score=1.0,
                calibrated_probability=1.0,
                deterministic_tier_fired=False,
                deterministic_result=None,
                feature_vector={},
                shap_contributions={},
                shared_blocks=[],
                scored_at=datetime.now(timezone.utc),
            )
            db.add(pair)
            db.flush()

        pair_id = str(pair.pair_id)

    apply_decision({
        "queue_id": None,
        "pair_id": pair_id,
        "canonical_id_a": a,
        "canonical_id_b": b,
        "decision": "reject",
        "reviewer_id": body.reviewer_id,
        "reviewer_tier": body.reviewer_tier,
        "notes": body.notes or "manual unmerge from Activity Status",
    })

    return {
        "status": "unmerged",
        "previous_shared_ubid": str(row.shared_ubid),
        "canonical_id_a": a,
        "canonical_id_b": b,
        "pair_id": pair_id,
    }


class RegroupRequest(BaseModel):
    ubid: str
    groupings: dict[str, str]   # canonical_id -> group label (or "Solo")
    reviewer_id: str
    reviewer_tier: str = "junior"
    notes: Optional[str] = None


@router.post("/regroup")
def regroup_ubid(body: RegroupRequest):
    """Atomically split a UBID into N sub-clusters according to reviewer-assigned groups.

    For each group with ≥2 members, a single UBID holds all of them, and a
    must-link constraint is written between every pair of members.

    For each `Solo`-labelled record, a brand-new UBID is created and a
    cannot-link constraint is written against every other record in the
    cluster.

    Cross-group pairs always get cannot-link constraints regardless of size.

    Every constraint is also written as a `training_labels` row and a
    `reviewer_decisions` row, so the next `/admin/retrain` consumes them.
    """
    import uuid as _uuid
    from datetime import datetime, timezone
    from sqlalchemy import select, text
    from ubid.storage.postgres import (
        get_db, LinkagePairORM, LinkageConstraintORM,
        ReviewerDecisionORM, TrainingLabelORM, UBIDNodeORM,
        CanonicalRecordORM,
    )
    from ubid.storage import redis_cache

    if not body.groupings:
        raise HTTPException(400, "groupings is empty")

    # ── Validate ─────────────────────────────────────────────────────────────
    with get_db() as db:
        node = db.get(UBIDNodeORM, body.ubid)
        if not node:
            raise HTTPException(404, f"UBID {body.ubid} not found")

        members = db.execute(text("""
            SELECT canonical_id FROM ubid_source_links WHERE ubid = :u
        """), {"u": body.ubid}).fetchall()
        actual_ids = {str(m.canonical_id) for m in members}

    provided_ids = set(body.groupings.keys())
    if provided_ids != actual_ids:
        missing = sorted(actual_ids - provided_ids)
        extra = sorted(provided_ids - actual_ids)
        raise HTTPException(
            400,
            f"Groupings must contain exactly the UBID's current members. "
            f"Missing: {missing[:3]}{' ...' if len(missing) > 3 else ''}. "
            f"Extra: {extra[:3]}{' ...' if len(extra) > 3 else ''}"
        )

    # ── Build group → [canonical_ids] map. Each "Solo" gets its own bucket ───
    groups: dict[str, list[str]] = {}
    for cid, label in body.groupings.items():
        norm = (label or "").strip()
        if norm.lower() in ("solo", "isolate", "+ new group"):
            groups[f"__solo_{cid}"] = [cid]
        else:
            groups.setdefault(norm or "Group 1", []).append(cid)

    # If everyone is in one group, this is identical to approve_ubid
    if len(groups) == 1 and "__solo_" not in next(iter(groups)):
        return approve_ubid(ApproveUBIDRequest(
            ubid=body.ubid,
            reviewer_id=body.reviewer_id,
            reviewer_tier=body.reviewer_tier,
            notes=body.notes or "regroup → all same group",
        ))

    # Pick "keeper" group — largest, alphabetical tiebreak
    keeper_label = max(
        groups.keys(),
        key=lambda k: (len(groups[k]), -ord(k[0]) if k else 0),
    )

    new_ubids_created = 0
    moved_count = 0
    must_links_added = 0
    cannot_links_added = 0
    decisions_logged = 0
    now = datetime.now(timezone.utc)

    with get_db() as db:
        # ── Phase 1: assign every member to a target UBID ────────────────────
        cid_to_target: dict[str, str] = {}
        for label, members_in_group in groups.items():
            if label == keeper_label:
                target = body.ubid
            else:
                new_ubid = str(_uuid.uuid4())
                rep_id = members_in_group[0]
                rep = db.get(CanonicalRecordORM, rep_id)
                db.add(UBIDNodeORM(
                    ubid=new_ubid,
                    pin_code=rep.pin_code if rep else None,
                    district=rep.district if rep else None,
                    sector_canonical=(rep.nic_code or rep.sector_raw) if rep else None,
                    created_at=now,
                    updated_at=now,
                ))
                new_ubids_created += 1
                target = new_ubid
            for m in members_in_group:
                cid_to_target[m] = target

        db.flush()

        # ── Phase 2: move source links for non-keepers ───────────────────────
        for cid, target in cid_to_target.items():
            if target == body.ubid:
                continue
            db.execute(text("""
                UPDATE ubid_source_links
                SET ubid = :new, linked_by = 'reviewer:regroup', linked_at = :t
                WHERE canonical_id = :cid
            """), {"new": target, "cid": cid, "t": now})
            moved_count += 1
            cr = db.get(CanonicalRecordORM, cid)
            if cr:
                redis_cache.set_ubid_for_source(cr.source_system, cr.source_record_id, target)

        # ── Phase 3: write constraints + training labels + decisions ─────────
        all_cids = list(body.groupings.keys())
        for i in range(len(all_cids)):
            for j in range(i + 1, len(all_cids)):
                a, b = sorted([all_cids[i], all_cids[j]])
                same_group = (cid_to_target[a] == cid_to_target[b])
                ctype = "must_link" if same_group else "cannot_link"

                # Find or create linkage_pair (FK requirement for decisions)
                pair = db.execute(
                    select(LinkagePairORM).where(
                        LinkagePairORM.canonical_id_a == a,
                        LinkagePairORM.canonical_id_b == b,
                    )
                ).scalar_one_or_none()
                if not pair:
                    pair = LinkagePairORM(
                        pair_id=str(_uuid.uuid4()),
                        canonical_id_a=a, canonical_id_b=b,
                        raw_score=1.0 if same_group else 0.0,
                        calibrated_probability=1.0 if same_group else 0.0,
                        deterministic_tier_fired=False,
                        deterministic_result=None,
                        feature_vector={},
                        shap_contributions={},
                        shared_blocks=[],
                        scored_at=now,
                    )
                    db.add(pair)
                    db.flush()

                # Constraint (idempotent — replaces opposite if it existed)
                existing_c = db.execute(
                    select(LinkageConstraintORM).where(
                        LinkageConstraintORM.canonical_id_a == a,
                        LinkageConstraintORM.canonical_id_b == b,
                    )
                ).scalar_one_or_none()
                if existing_c:
                    if existing_c.constraint_type != ctype:
                        existing_c.constraint_type = ctype
                        existing_c.created_by = body.reviewer_id
                        existing_c.notes = body.notes
                else:
                    db.add(LinkageConstraintORM(
                        constraint_id=str(_uuid.uuid4()),
                        canonical_id_a=a, canonical_id_b=b,
                        constraint_type=ctype,
                        created_by=body.reviewer_id,
                        created_at=now,
                        notes=body.notes,
                    ))
                if same_group:
                    must_links_added += 1
                else:
                    cannot_links_added += 1

                # Training label (idempotent)
                existing_l = db.execute(
                    select(TrainingLabelORM).where(
                        TrainingLabelORM.canonical_id_a == a,
                        TrainingLabelORM.canonical_id_b == b,
                    )
                ).scalar_one_or_none()
                if existing_l:
                    existing_l.is_match = same_group
                else:
                    db.add(TrainingLabelORM(
                        label_id=str(_uuid.uuid4()),
                        canonical_id_a=a, canonical_id_b=b,
                        is_match=same_group,
                        source="reviewer_regroup",
                        created_at=now,
                    ))

                # Reviewer decision row for the audit trail
                db.add(ReviewerDecisionORM(
                    decision_id=str(_uuid.uuid4()),
                    queue_id=None,
                    pair_id=str(pair.pair_id),
                    canonical_id_a=a, canonical_id_b=b,
                    decision="confirm_match" if same_group else "reject",
                    reviewer_id=body.reviewer_id,
                    reviewer_tier=body.reviewer_tier,
                    notes=body.notes or "regroup",
                    decided_at=now,
                    is_training_label=True,
                ))
                decisions_logged += 1

        # Invalidate verdict caches for every affected UBID
        for u in set(cid_to_target.values()):
            redis_cache.invalidate_verdict(u)

    # Refresh DuckDB events to point at new UBIDs (best-effort, in-process)
    try:
        import pandas as _pd
        from sqlalchemy import text as _text
        from ubid.storage.duckdb_warehouse import get_conn as _get_conn

        with get_db() as db:
            rows = db.execute(_text("""
                SELECT cr.source_system, cr.source_record_id, usl.ubid
                FROM canonical_records cr
                JOIN ubid_source_links usl ON usl.canonical_id = cr.canonical_id
            """)).fetchall()
        mapping_df = _pd.DataFrame(
            [(s, r, str(u)) for s, r, u in rows],
            columns=["source_system", "source_record_id", "ubid"],
        )
        conn = _get_conn()
        conn.register("ubid_mapping_df", mapping_df)
        conn.execute("DROP TABLE IF EXISTS events_new")
        conn.execute("""
            CREATE TABLE events_new AS
            SELECT e.event_id, m.ubid AS ubid, e.canonical_id, e.source_system,
                   e.source_record_id, e.event_type, e.event_date,
                   e.ingested_at, e.metadata
            FROM events e LEFT JOIN ubid_mapping_df m
              ON m.source_system = e.source_system
             AND m.source_record_id = e.source_record_id
        """)
        conn.execute("DROP TABLE events")
        conn.execute("ALTER TABLE events_new RENAME TO events")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_events_pk ON events(event_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ubid ON events(ubid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
        conn.unregister("ubid_mapping_df")
    except Exception as e:
        logger.warning("DuckDB event-remapping skipped after regroup: %s", e)

    return {
        "status": "regrouped",
        "source_ubid": body.ubid,
        "n_groups": len(groups),
        "new_ubids_created": new_ubids_created,
        "records_moved": moved_count,
        "must_links_added": must_links_added,
        "cannot_links_added": cannot_links_added,
        "decisions_logged": decisions_logged,
        "training_labels_written": decisions_logged,
        "feeds_next_retrain": True,
    }


@router.post("/synonyms")
def add_locality_synonym(body: SynonymRequest):
    """Add a locality synonym discovered during review."""
    add_synonym(body.variant, body.canonical)
    return {"status": "added", "variant": body.variant, "canonical": body.canonical}
