"""Inspect why ground-truth Dormant entities are being classified as Closed.

For each ground-truth dormant entity, find its UBID, fetch its continuity
score, count of events, latest event date, and current verdict — then print
a histogram of scores so we can pick a sensible dormant threshold.
"""
from __future__ import annotations
import csv
import sys
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import text  # noqa: E402

from ubid.storage.duckdb_warehouse import count_events_for_ubid  # noqa: E402
from ubid.storage.postgres import get_db  # noqa: E402

GROUND_TRUTH = _REPO / "data" / "synthetic" / "ground_truth_links.csv"


def parse_record_ids(field: str) -> list[str]:
    return [x.strip() for x in (field or "").split(";") if x.strip()]


def main():
    record_to_entity: dict[tuple[str, str], str] = {}
    entity_to_status: dict[str, str] = {}
    with open(GROUND_TRUTH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            entity_to_status[row["entity_id"]] = row.get("ground_truth_status", "").lower()
            for src, col in [("ekarmika", "ekarmika_record_id"), ("fbis", "fbis_record_id"),
                             ("kspcb", "kspcb_record_id"), ("bescom", "bescom_record_id")]:
                for rid in parse_record_ids(row.get(col, "")):
                    record_to_entity[(src, rid)] = row["entity_id"]

    entity_to_ubids: dict[str, set] = defaultdict(set)
    with get_db() as db:
        rows = db.execute(text("""
            SELECT cr.source_system, cr.source_record_id, usl.ubid
            FROM canonical_records cr
            JOIN ubid_source_links usl ON usl.canonical_id = cr.canonical_id
        """)).fetchall()
        for src, rid, ubid in rows:
            eid = record_to_entity.get((src, rid))
            if eid:
                entity_to_ubids[eid].add(str(ubid))

        verdict_rows = db.execute(text("""
            SELECT ubid, verdict, continuity_score
            FROM activity_verdicts
        """)).fetchall()
        verdict_map = {str(u): (str(v), float(s)) for u, v, s in verdict_rows}

    # Look at every dormant entity
    print(f"{'entity':<6}  {'#ubid':>5}  {'verdict':<20}  {'score':>6}  {'#events':>7}")
    print("-" * 60)
    score_buckets: dict[str, int] = defaultdict(int)
    for eid, gt in entity_to_status.items():
        if gt != "dormant":
            continue
        for u in entity_to_ubids.get(eid, set()):
            v, s = verdict_map.get(u, ("?", 0.0))
            n = count_events_for_ubid(u)
            print(f"{eid:<6}  {u[:8]:<5}  {v:<20}  {s:>6.3f}  {n:>7}")
            if s < 0.05: bucket = "<0.05"
            elif s < 0.1: bucket = "0.05–0.1"
            elif s < 0.2: bucket = "0.1–0.2"
            elif s < 0.4: bucket = "0.2–0.4"
            else: bucket = ">=0.4"
            score_buckets[bucket] += 1

    print("\nDormant-entity score distribution:")
    for bucket in ["<0.05", "0.05–0.1", "0.1–0.2", "0.2–0.4", ">=0.4"]:
        print(f"  {bucket:<10}  {score_buckets.get(bucket, 0)}")


if __name__ == "__main__":
    main()
