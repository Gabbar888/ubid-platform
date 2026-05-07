"""Trigger activity verdict computation for every UBID in the system.

The verdict endpoint computes lazily on first request, so we hit /status
on every UBID once to materialise the activity_verdicts table.
"""
from __future__ import annotations
import subprocess
import sys

import httpx

API_BASE = "http://localhost:8000"
PG_CONTAINER = "ubid_platform-postgres-1"

# Synthetic events span 2023-11 to 2025-04. Treat "today" as just after the
# data ends so decay computation is meaningful for the demo.
REFERENCE_DATE = "2025-05-01"


def list_all_ubids() -> list[str]:
    """Fetch all UBIDs by shelling into the postgres container."""
    out = subprocess.check_output(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", "ubid", "-d", "ubid", "-tAc",
         "SELECT ubid FROM ubid_nodes;"],
        text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def main():
    ubids = list_all_ubids()
    print(f"Found {len(ubids)} UBIDs. Triggering verdict computation...")

    counts: dict[str, int] = {}
    failed = 0

    with httpx.Client(timeout=30) as client:
        for i, ubid in enumerate(ubids, 1):
            try:
                r = client.get(
                    f"{API_BASE}/api/v1/ubid/{ubid}/status",
                    params={
                        "force_recompute": "true",
                        "reference_date": REFERENCE_DATE,
                    },
                )
                if r.status_code < 400:
                    verdict = r.json().get("verdict", "unknown")
                    counts[verdict] = counts.get(verdict, 0) + 1
                else:
                    failed += 1
                    if failed <= 3:
                        print(f"  HTTP {r.status_code} for {ubid}: {r.text[:200]}")
            except Exception as e:
                failed += 1
                if failed <= 3:
                    print(f"  Error for {ubid}: {e}")

            if i % 50 == 0:
                print(f"  ...{i}/{len(ubids)}")

    print(f"\nDone — {sum(counts.values())}/{len(ubids)} verdicts computed (failed {failed})")
    for v, n in sorted(counts.items()):
        print(f"  {v}: {n}")


if __name__ == "__main__":
    main()
