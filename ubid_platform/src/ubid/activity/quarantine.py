"""Quarantine management for events that cannot be joined to a UBID.

Events go here when:
- The source record has not been ingested yet.
- The linkage was below auto-link threshold.
- BESCOM sub-identifiers (RR number) not yet attached.

Quarantined events are replayed whenever the linkage table updates.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

from ubid.schema.events import ActivityEvent, QuarantinedEvent
from ubid.storage import redis_cache
from ubid.storage.postgres import get_db, QuarantineEventORM, ActivityEventORM
from ubid.storage.duckdb_warehouse import append_event

logger = logging.getLogger(__name__)


def quarantine(event: ActivityEvent, reason: str):
    """Store event in quarantine when it can't be joined."""
    with get_db() as db:
        existing = db.get(QuarantineEventORM, str(event.event_id))
        if existing:
            return  # already quarantined
        row = QuarantineEventORM(
            event_id=str(event.event_id),
            source_system=event.source_system,
            source_record_id=event.source_record_id,
            event_type=event.event_type,
            event_date=event.event_date,
            quarantined_at=datetime.now(timezone.utc),
            reason=reason,
            metadata=event.metadata,
        )
        db.add(row)
    logger.debug("Quarantined event %s: %s", event.event_id, reason)


def try_resolve(source_system: str, source_record_id: str) -> int:
    """Attempt to resolve all quarantined events for a source record.

    Called after the linkage table is updated. Returns count resolved.
    """
    ubid = redis_cache.get_ubid_for_source(source_system, source_record_id)
    if not ubid:
        with get_db() as db:
            from sqlalchemy import text
            row = db.execute(text("""
                SELECT u.ubid FROM ubid_source_links usl
                JOIN ubid_nodes u ON usl.ubid = u.ubid
                JOIN canonical_records cr ON usl.canonical_id = cr.canonical_id
                WHERE cr.source_system = :sys AND cr.source_record_id = :rid
                LIMIT 1
            """), {"sys": source_system, "rid": source_record_id}).first()
            if row:
                ubid = str(row.ubid)

    if not ubid:
        return 0

    resolved_count = 0
    with get_db() as db:
        from sqlalchemy import select, and_
        pending = db.execute(
            select(QuarantineEventORM).where(
                and_(
                    QuarantineEventORM.source_system == source_system,
                    QuarantineEventORM.source_record_id == source_record_id,
                    QuarantineEventORM.resolved == False,
                )
            )
        ).scalars().all()

        for qe in pending:
            append_event(
                event_id=qe.event_id,
                source_system=qe.source_system,
                source_record_id=qe.source_record_id,
                event_type=qe.event_type,
                event_date=qe.event_date,
                ingested_at=datetime.now(timezone.utc),
                ubid=ubid,
                metadata=qe.event_metadata,
            )
            qe.resolved = True
            qe.resolved_ubid = ubid
            qe.resolved_at = datetime.now(timezone.utc)
            resolved_count += 1

    if resolved_count:
        logger.info("Resolved %d quarantined events for %s:%s → %s",
                    resolved_count, source_system, source_record_id, ubid)
    return resolved_count


def get_quarantine_stats() -> dict:
    with get_db() as db:
        from sqlalchemy import func, select
        total = db.execute(
            select(func.count()).select_from(QuarantineEventORM)
        ).scalar()
        unresolved = db.execute(
            select(func.count()).select_from(QuarantineEventORM)
            .where(QuarantineEventORM.resolved == False)
        ).scalar()
        return {"total": total, "unresolved": unresolved, "resolved": total - unresolved}
