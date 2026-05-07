"""Check for duplicate event_ids in the DuckDB events table."""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from ubid.storage.duckdb_warehouse import get_conn


def main():
    conn = get_conn()
    print("Top duplicate event_ids:")
    for row in conn.execute(
        "SELECT event_id, COUNT(*) FROM events GROUP BY event_id HAVING COUNT(*) > 1 ORDER BY 2 DESC LIMIT 10"
    ).fetchall():
        print(" ", row)

    print("\nRows with event_id ed051adb-daa0-4431-b668-1b54ff498abc:")
    for row in conn.execute(
        "SELECT event_id, source_system, source_record_id, ubid FROM events WHERE event_id = ?",
        ["ed051adb-daa0-4431-b668-1b54ff498abc"],
    ).fetchall():
        print(" ", row)

    print("\nUnique event_ids vs row count:")
    print("  rows:", conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
    print("  distinct event_ids:", conn.execute("SELECT COUNT(DISTINCT event_id) FROM events").fetchone()[0])


if __name__ == "__main__":
    main()
