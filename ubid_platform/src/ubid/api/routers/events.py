"""Activity events ingestion API.

Bypasses Kafka for synchronous request/response. Joins each event to a UBID
via the linkage table, appends it to the DuckDB warehouse, and quarantines
events that cannot be joined.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ubid.activity.quarantine import quarantine
from ubid.schema.canonical import SourceSystem
from ubid.schema.events import ActivityEvent, EventType
from ubid.storage import redis_cache
from ubid.storage.duckdb_warehouse import append_event, count_events_for_ubid, get_events_for_ubid, get_conn
from ubid.storage.postgres import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


class EventBatch(BaseModel):
    events: list[dict[str, Any]] = Field(..., description="Activity event dicts")


class EventBatchResponse(BaseModel):
    accepted: int
    joined: int
    quarantined: int
    errors: int


def _resolve_ubid(source_system: str, source_record_id: str) -> str | None:
    cached = redis_cache.get_ubid_for_source(source_system, source_record_id)
    if cached:
        return cached
    with get_db() as db:
        row = db.execute(text("""
            SELECT u.ubid FROM ubid_source_links usl
            JOIN ubid_nodes u ON usl.ubid = u.ubid
            JOIN canonical_records cr ON usl.canonical_id = cr.canonical_id
            WHERE cr.source_system = :sys AND cr.source_record_id = :rid
            LIMIT 1
        """), {"sys": source_system, "rid": source_record_id}).first()
        if row:
            ubid = str(row.ubid)
            redis_cache.set_ubid_for_source(source_system, source_record_id, ubid)
            return ubid
    return None


@router.post("", response_model=EventBatchResponse)
def ingest_events(body: EventBatch):
    """Ingest a batch of activity events synchronously."""
    joined = 0
    quarantined = 0
    errors = 0

    for raw in body.events:
        try:
            event = ActivityEvent(**raw)
        except Exception as e:
            errors += 1
            if errors <= 5:
                logger.warning("Bad event payload: %s — %s", e, raw)
            continue

        ubid = _resolve_ubid(event.source_system, event.source_record_id)

        if ubid:
            try:
                append_event(
                    event_id=str(event.event_id),
                    source_system=event.source_system,
                    source_record_id=event.source_record_id,
                    event_type=event.event_type,
                    event_date=event.event_date,
                    ingested_at=datetime.now(timezone.utc),
                    ubid=ubid,
                    metadata=event.metadata,
                )
                redis_cache.invalidate_verdict(ubid)
                joined += 1
            except Exception as e:
                errors += 1
                logger.exception("Failed to append event %s: %s", event.event_id, e)
        else:
            try:
                quarantine(event, reason="No UBID found for source record")
                quarantined += 1
            except Exception as e:
                errors += 1
                logger.exception("Quarantine failed for %s: %s", event.event_id, e)

    return EventBatchResponse(
        accepted=len(body.events),
        joined=joined,
        quarantined=quarantined,
        errors=errors,
    )


@router.get("/quarantine")
def list_quarantined_events(
    resolved: str = "no",  # "no" | "yes" | "all"
    limit: int = 50,
    offset: int = 0,
):
    """Paginated list of quarantined events with resolution status."""
    from sqlalchemy import text
    where = {
        "no": "WHERE q.resolved = FALSE",
        "yes": "WHERE q.resolved = TRUE",
        "all": "",
    }.get(resolved, "WHERE q.resolved = FALSE")

    with get_db() as db:
        total = db.execute(text(
            f"SELECT COUNT(*) FROM quarantine_events q {where}"
        )).scalar() or 0
        rows = db.execute(text(f"""
            SELECT event_id, source_system, source_record_id, event_type,
                   event_date, quarantined_at, reason, retry_count,
                   resolved, resolved_ubid, resolved_at, last_retry_at
            FROM quarantine_events q
            {where}
            ORDER BY quarantined_at DESC
            LIMIT :limit OFFSET :offset
        """), {"limit": limit, "offset": offset}).fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "event_id": str(r.event_id),
                "source_system": r.source_system,
                "source_record_id": r.source_record_id,
                "event_type": r.event_type,
                "event_date": str(r.event_date),
                "quarantined_at": str(r.quarantined_at),
                "reason": r.reason,
                "retry_count": r.retry_count,
                "resolved": r.resolved,
                "resolved_ubid": str(r.resolved_ubid) if r.resolved_ubid else None,
                "resolved_at": str(r.resolved_at) if r.resolved_at else None,
                "last_retry_at": str(r.last_retry_at) if r.last_retry_at else None,
            }
            for r in rows
        ],
    }


@router.post("/quarantine/retry-all")
def retry_all_quarantine():
    """Try to resolve every unresolved quarantined event by re-checking the
    linkage table. Useful after a re-cluster or new ingestion."""
    from ubid.activity.quarantine import try_resolve
    from sqlalchemy import text

    with get_db() as db:
        rows = db.execute(text("""
            SELECT DISTINCT source_system, source_record_id
            FROM quarantine_events
            WHERE resolved = FALSE
        """)).fetchall()

    resolved_total = 0
    attempts = 0
    for src, rid in rows:
        attempts += 1
        try:
            resolved_total += try_resolve(src, rid)
        except Exception:
            pass

    # Bump retry_count for everything we touched
    if rows:
        with get_db() as db:
            db.execute(text("""
                UPDATE quarantine_events
                SET retry_count = retry_count + 1,
                    last_retry_at = NOW()
                WHERE resolved = FALSE
            """))

    return {
        "source_records_attempted": attempts,
        "events_resolved": resolved_total,
    }


@router.post("/quarantine/{event_id}/retry")
def retry_quarantine_event(event_id: str):
    """Retry a single quarantined event."""
    from ubid.activity.quarantine import try_resolve
    from sqlalchemy import text

    with get_db() as db:
        row = db.execute(text("""
            SELECT source_system, source_record_id FROM quarantine_events
            WHERE event_id = :id
        """), {"id": event_id}).first()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(404, f"No quarantined event {event_id}")

        db.execute(text("""
            UPDATE quarantine_events
            SET retry_count = retry_count + 1, last_retry_at = NOW()
            WHERE event_id = :id
        """), {"id": event_id})

    resolved = try_resolve(row.source_system, row.source_record_id)
    return {"event_id": event_id, "resolved_count_for_record": resolved}


@router.get("/debug/summary")
def debug_summary():
    """Quick stats on the DuckDB event warehouse."""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    with_ubid = conn.execute("SELECT COUNT(*) FROM events WHERE ubid IS NOT NULL").fetchone()[0]
    distinct_ubids = conn.execute("SELECT COUNT(DISTINCT ubid) FROM events WHERE ubid IS NOT NULL").fetchone()[0]
    date_range = conn.execute("SELECT MIN(event_date), MAX(event_date) FROM events").fetchone()
    by_type = conn.execute(
        "SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY 2 DESC"
    ).fetchall()
    sample_ubid_with_events = conn.execute(
        "SELECT ubid, COUNT(*) FROM events WHERE ubid IS NOT NULL GROUP BY ubid ORDER BY 2 DESC LIMIT 1"
    ).fetchone()
    return {
        "total_events": total,
        "with_ubid": with_ubid,
        "distinct_ubids": distinct_ubids,
        "min_date": str(date_range[0]) if date_range[0] else None,
        "max_date": str(date_range[1]) if date_range[1] else None,
        "by_event_type": dict(by_type),
        "top_ubid": {"ubid": sample_ubid_with_events[0], "count": sample_ubid_with_events[1]} if sample_ubid_with_events else None,
    }


@router.post("/admin/refresh-ubids")
def admin_refresh_event_ubids():
    """Re-map every DuckDB event to the current UBID assignment.

    Needed after re-clustering: the linkage table has new UBIDs but the
    DuckDB events still carry old ones. Rebuilds the events table using a
    JOIN with the current source_record → ubid mapping.
    """
    import pandas as pd
    from sqlalchemy import text

    with get_db() as db:
        rows = db.execute(text("""
            SELECT cr.source_system, cr.source_record_id, usl.ubid
            FROM canonical_records cr
            JOIN ubid_source_links usl ON usl.canonical_id = cr.canonical_id
        """)).fetchall()

    mapping_df = pd.DataFrame(
        [(src, rid, str(ubid)) for src, rid, ubid in rows],
        columns=["source_system", "source_record_id", "ubid"],
    )

    conn = get_conn()
    total_before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.register("ubid_mapping_df", mapping_df)
    conn.execute("DROP TABLE IF EXISTS events_new")
    conn.execute("""
        CREATE TABLE events_new AS
        SELECT
            e.event_id,
            m.ubid AS ubid,
            e.canonical_id,
            e.source_system,
            e.source_record_id,
            e.event_type,
            e.event_date,
            e.ingested_at,
            e.metadata
        FROM events e
        LEFT JOIN ubid_mapping_df m
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

    distinct = conn.execute(
        "SELECT COUNT(DISTINCT ubid) FROM events WHERE ubid IS NOT NULL"
    ).fetchone()[0]
    with_ubid = conn.execute(
        "SELECT COUNT(*) FROM events WHERE ubid IS NOT NULL"
    ).fetchone()[0]

    return {
        "events_total": total_before,
        "events_with_ubid": with_ubid,
        "distinct_ubids_with_events": distinct,
        "mapping_size": len(mapping_df),
    }


@router.post("/admin/wipe-events")
def admin_wipe_events():
    """Drop and recreate the DuckDB events table — useful for clean re-ingest."""
    conn = get_conn()
    conn.execute("DROP TABLE IF EXISTS events")
    conn.execute("DROP TABLE IF EXISTS quarantine")
    from ubid.storage.duckdb_warehouse import _ensure_schema
    _ensure_schema(conn)
    return {"status": "events warehouse wiped"}


@router.get("/debug/ubid/{ubid}")
def debug_ubid_events(ubid: str):
    """Inspect what events DuckDB has for a UBID."""
    cnt = count_events_for_ubid(ubid)
    sample = get_events_for_ubid(ubid, lookback_days=10000)
    return {
        "ubid": ubid,
        "event_count": cnt,
        "events_within_lookback": len(sample),
        "sample_events": [
            {
                "event_id": e["event_id"],
                "source_system": e["source_system"],
                "event_type": e["event_type"],
                "event_date": str(e["event_date"]),
            }
            for e in sample[:10]
        ],
    }
