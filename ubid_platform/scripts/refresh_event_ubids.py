"""Re-map every event in DuckDB to its current UBID assignment.

After re-clustering, the linkage table in Postgres reflects new UBID
assignments, but the events stored in DuckDB still carry the previous UBIDs
on each row. This script joins each event's (source_system, source_record_id)
back to the latest UBID and rewrites the column.

Run:
    docker compose exec ubid-api python /app/scripts/refresh_event_ubids.py
"""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import text  # noqa: E402

from ubid.storage.duckdb_warehouse import get_conn  # noqa: E402
from ubid.storage.postgres import get_db  # noqa: E402


def main():
    # Build (source_system, source_record_id) -> ubid map from Postgres
    with get_db() as db:
        rows = db.execute(text("""
            SELECT cr.source_system, cr.source_record_id, usl.ubid
            FROM canonical_records cr
            JOIN ubid_source_links usl ON usl.canonical_id = cr.canonical_id
        """)).fetchall()
    mapping = {(src, rid): str(ubid) for src, rid, ubid in rows}
    print(f"Built mapping for {len(mapping)} source records.")

    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    print(f"Events in DuckDB: {total}")

    # DuckDB's UPDATE on a PK-indexed table is unreliable, so rebuild the
    # table from a join with the mapping. Same row count, same primary key,
    # only the ubid column changes.
    import pandas as pd
    mapping_df = pd.DataFrame(
        [(src, rid, ubid) for (src, rid), ubid in mapping.items()],
        columns=["source_system", "source_record_id", "ubid"],
    )
    conn.register("ubid_mapping_df", mapping_df)

    conn.execute("DROP TABLE IF EXISTS events_new")
    conn.execute("""
        CREATE TABLE events_new AS
        SELECT
            e.event_id,
            COALESCE(m.ubid, NULL) AS ubid,
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

    # DuckDB does not allow adding a PK after CREATE TABLE AS, so we rely on
    # a unique index instead — same de-dup guarantee, no syntax error.
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
    print(f"Events with a UBID: {with_ubid}/{total}")
    print(f"Distinct UBIDs with events: {distinct}")


if __name__ == "__main__":
    main()
