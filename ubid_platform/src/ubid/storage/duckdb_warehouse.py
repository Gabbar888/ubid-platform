"""Append-only UBID-keyed event warehouse backed by DuckDB."""
from datetime import date, datetime
from typing import Any, Optional
import os
import logging
import duckdb

from ubid.config import get_settings

logger = logging.getLogger(__name__)

_conn: Optional[duckdb.DuckDBPyConnection] = None


def get_conn() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        settings = get_settings()
        os.makedirs(os.path.dirname(settings.duckdb_path), exist_ok=True)
        _conn = duckdb.connect(settings.duckdb_path)
        _ensure_schema(_conn)
    return _conn


def _ensure_schema(conn: duckdb.DuckDBPyConnection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id        TEXT NOT NULL,
            ubid            TEXT,
            canonical_id    TEXT,
            source_system   TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            event_type      TEXT NOT NULL,
            event_date      DATE NOT NULL,
            ingested_at     TIMESTAMPTZ NOT NULL,
            metadata        JSON NOT NULL DEFAULT '{}',
            PRIMARY KEY (event_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ubid ON events(ubid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quarantine (
            event_id        TEXT NOT NULL PRIMARY KEY,
            source_system   TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            event_type      TEXT NOT NULL,
            event_date      DATE NOT NULL,
            quarantined_at  TIMESTAMPTZ NOT NULL,
            reason          TEXT NOT NULL,
            metadata        JSON NOT NULL DEFAULT '{}',
            retry_count     INTEGER NOT NULL DEFAULT 0,
            resolved        BOOLEAN NOT NULL DEFAULT FALSE,
            resolved_ubid   TEXT,
            resolved_at     TIMESTAMPTZ
        )
    """)


def append_event(
    event_id: str,
    source_system: str,
    source_record_id: str,
    event_type: str,
    event_date: date,
    ingested_at: datetime,
    ubid: Optional[str] = None,
    canonical_id: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    import json
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO events
            (event_id, ubid, canonical_id, source_system, source_record_id,
             event_type, event_date, ingested_at, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        event_id, ubid, canonical_id, source_system, source_record_id,
        event_type, event_date, ingested_at, json.dumps(metadata or {}),
    ])


def get_events_for_ubid(
    ubid: str,
    lookback_days: int = 730,
    reference_date: Optional[date] = None,
) -> list[dict]:
    """Fetch events for a UBID within `lookback_days` of the reference date.

    Reference date defaults to today; pass an explicit value to compute
    decay against a fixed point in time (useful for demos / replay).
    """
    conn = get_conn()
    if reference_date is None:
        rows = conn.execute("""
            SELECT event_id, source_system, event_type, event_date, metadata
            FROM events
            WHERE ubid = ?
              AND event_date >= current_date - INTERVAL (?) DAY
            ORDER BY event_date DESC
        """, [ubid, lookback_days]).fetchall()
    else:
        rows = conn.execute("""
            SELECT event_id, source_system, event_type, event_date, metadata
            FROM events
            WHERE ubid = ?
              AND event_date >= (CAST(? AS DATE) - INTERVAL (?) DAY)
              AND event_date <= CAST(? AS DATE)
            ORDER BY event_date DESC
        """, [ubid, reference_date, lookback_days, reference_date]).fetchall()
    cols = ["event_id", "source_system", "event_type", "event_date", "metadata"]
    return [dict(zip(cols, r)) for r in rows]


def count_events_for_ubid(ubid: str) -> int:
    conn = get_conn()
    result = conn.execute("SELECT COUNT(*) FROM events WHERE ubid = ?", [ubid]).fetchone()
    return result[0] if result else 0


def update_event_ubid(event_id: str, ubid: str):
    """Called during quarantine replay when an event is matched to a UBID."""
    conn = get_conn()
    conn.execute("UPDATE events SET ubid = ? WHERE event_id = ?", [ubid, event_id])


def query_active_ubids(
    verdict: str,
    pin_code: Optional[str] = None,
    sector: Optional[str] = None,
    no_event_type: Optional[str] = None,
    no_event_since_days: Optional[int] = None,
) -> list[str]:
    """Power the analytical query class from the proposal."""
    conn = get_conn()
    params: list[Any] = [verdict]
    sql = """
        SELECT DISTINCT e.ubid
        FROM events e
        JOIN (
            SELECT ubid, verdict FROM activity_verdicts WHERE verdict = ?
        ) v ON e.ubid = v.ubid
        WHERE 1=1
    """
    if pin_code:
        # Join back to canonical_records via ubid_source_links for pin filter
        sql += " AND e.ubid IN (SELECT ubid FROM ubid_pin_view WHERE pin_code = ?)"
        params.append(pin_code)

    if no_event_type and no_event_since_days:
        sql += f"""
            AND e.ubid NOT IN (
                SELECT DISTINCT ubid FROM events
                WHERE event_type = ?
                  AND event_date >= current_date - INTERVAL (?) DAY
                  AND ubid IS NOT NULL
            )
        """
        params.extend([no_event_type, no_event_since_days])

    rows = conn.execute(sql, params).fetchall()
    return [r[0] for r in rows]
