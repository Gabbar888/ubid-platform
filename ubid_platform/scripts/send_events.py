"""Send activity events from events_stream.jsonl to the running UBID API.

Uses the dedicated /api/v1/events endpoint (synchronous, joins to UBID,
writes to DuckDB warehouse, quarantines unjoined events).
"""
import json
import sys
from pathlib import Path

import httpx

EVENTS_FILE = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "events_stream.jsonl"
API_BASE = "http://localhost:8000"
BATCH = 100


def main():
    if not EVENTS_FILE.exists():
        print(f"Events file not found: {EVENTS_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(EVENTS_FILE, encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(events)} events from {EVENTS_FILE.name}")

    totals = {"accepted": 0, "joined": 0, "quarantined": 0, "errors": 0}

    with httpx.Client(timeout=60) as client:
        for i in range(0, len(events), BATCH):
            chunk = events[i : i + BATCH]
            try:
                r = client.post(
                    f"{API_BASE}/api/v1/events",
                    json={"events": chunk},
                )
                r.raise_for_status()
                resp = r.json()
                for k in totals:
                    totals[k] += resp.get(k, 0)
            except Exception as e:
                print(f"  Batch {i}-{i+len(chunk)} failed: {e}")
                totals["errors"] += len(chunk)
            print(f"  ...{min(i + BATCH, len(events))}/{len(events)}")

    print("\nDone.")
    for k, v in totals.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
