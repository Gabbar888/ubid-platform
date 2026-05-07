"""Wipe ALL ingested data so we can re-ingest from scratch.

Useful for end-to-end tests of pipeline changes. Drops Postgres records,
DuckDB events, OpenSearch index, and Redis cache. Does NOT touch saved
ML model artefacts.

Run:
    docker compose exec ubid-api python /app/scripts/wipe_data.py
"""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import text  # noqa: E402

from ubid.blocking.opensearch_blocker import ensure_index, get_client  # noqa: E402
from ubid.config import get_settings  # noqa: E402
from ubid.storage.duckdb_warehouse import get_conn  # noqa: E402
from ubid.storage.postgres import get_db  # noqa: E402


def main():
    print("Wiping Postgres tables...")
    # Use a separate session per table so a missing-table error doesn't
    # abort the surrounding transaction.
    for table in [
        "activity_verdicts",
        "ubid_source_links",
        "ubid_nodes",
        "reviewer_queue",
        "review_decisions",
        "linkage_constraints",
        "linkage_pairs",
        "quarantine_events",
        "activity_events",
        "canonical_records",
    ]:
        try:
            with get_db() as db:
                db.execute(text(f"DELETE FROM {table}"))
            print(f"  cleared {table}")
        except Exception as e:
            print(f"  skipped {table}: {type(e).__name__}")

    print("\nWiping DuckDB events warehouse...")
    conn = get_conn()
    conn.execute("DROP TABLE IF EXISTS events")
    conn.execute("DROP TABLE IF EXISTS quarantine")
    # Re-create from schema
    from ubid.storage.duckdb_warehouse import _ensure_schema
    _ensure_schema(conn)

    print("\nWiping OpenSearch index...")
    settings = get_settings()
    client = get_client()
    try:
        client.indices.delete(index=settings.opensearch_index)
        print(f"  deleted index {settings.opensearch_index}")
    except Exception as e:
        print(f"  index delete failed (may not exist): {e}")
    ensure_index()
    print(f"  recreated index {settings.opensearch_index}")

    print("\nWiping Redis cache...")
    try:
        from ubid.storage import redis_cache
        redis_cache.get_client().flushdb()
        print("  flushed all keys")
    except Exception as e:
        print(f"  redis flush failed: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
