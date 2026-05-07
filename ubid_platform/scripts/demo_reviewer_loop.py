"""End-to-end demo of the reviewer feedback loop.

Picks the first pending review item, snapshots the UBIDs of the two records,
submits a confirm_match decision, then re-checks the UBIDs to prove they
got merged. Then picks an auto-linked pair (records currently sharing a
UBID), submits a reject decision, and proves the UBID got split.

Run on host:
    python scripts/demo_reviewer_loop.py
"""
from __future__ import annotations
import sys

import httpx

API = "http://localhost:8000"


def get(path: str, **params):
    r = httpx.get(f"{API}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def post(path: str, body: dict):
    r = httpx.post(f"{API}{path}", json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def lookup_ubid(canonical_id: str, source: str | None = None, rid: str | None = None) -> str | None:
    """Resolve a canonical_id to its current UBID via the lookup API."""
    if source and rid:
        try:
            return get("/api/v1/lookup", source=source, id=rid)["ubid"]
        except httpx.HTTPStatusError:
            return None
    return None


def demo_must_link():
    print("\n== DEMO 1: confirm_match merges two UBIDs ======================")
    queue = get("/api/v1/review/queue", limit=20)
    items = queue.get("items") or []
    if not items:
        print("  No pending review items.")
        return

    item = items[0]
    pair_id = item["pair_id"]
    queue_id = item["queue_id"]
    rec_a = item.get("record_a") or {}
    rec_b = item.get("record_b") or {}
    a_id = rec_a.get("canonical_id")
    b_id = rec_b.get("canonical_id")
    src_a, rid_a = rec_a.get("source_system"), rec_a.get("source_record_id")
    src_b, rid_b = rec_b.get("source_system"), rec_b.get("source_record_id")
    if not (a_id and b_id):
        print("  Queue item missing canonical IDs — skipping.")
        return

    print(f"  Pair: {a_id[:8]} -- {b_id[:8]}")
    print(f"  A ({src_a}/{rid_a}): {rec_a.get('name_normalized', '?')[:40]}")
    print(f"  B ({src_b}/{rid_b}): {rec_b.get('name_normalized', '?')[:40]}")

    ubid_a_before = lookup_ubid(a_id, src_a, rid_a)
    ubid_b_before = lookup_ubid(b_id, src_b, rid_b)
    print(f"  Before: A->{ubid_a_before[:8] if ubid_a_before else '?'}  "
          f"B->{ubid_b_before[:8] if ubid_b_before else '?'}  "
          f"same={ubid_a_before == ubid_b_before}")

    print("  Submitting confirm_match...")
    post("/api/v1/review/decide", {
        "pair_id": pair_id,
        "queue_id": queue_id,
        "canonical_id_a": a_id,
        "canonical_id_b": b_id,
        "decision": "confirm_match",
        "reviewer_id": "demo_reviewer",
        "reviewer_tier": "junior",
        "notes": "demo: should merge the UBIDs",
    })

    ubid_a_after = lookup_ubid(a_id, src_a, rid_a)
    ubid_b_after = lookup_ubid(b_id, src_b, rid_b)
    same_after = ubid_a_after == ubid_b_after
    print(f"  After:  A->{ubid_a_after[:8] if ubid_a_after else '?'}  "
          f"B->{ubid_b_after[:8] if ubid_b_after else '?'}  "
          f"same={same_after}")
    print(f"  RESULT: {'PASS — UBIDs merged' if same_after else 'FAIL — UBIDs still separate'}")


def find_currently_merged_pair() -> dict | None:
    """Find any auto-linked pair where both records currently share a UBID."""
    import subprocess
    out = subprocess.check_output([
        "docker", "exec", "ubid_platform-postgres-1", "psql", "-U", "ubid", "-d", "ubid", "-tAc",
        """
        SELECT lp.pair_id, lp.canonical_id_a, lp.canonical_id_b, usl_a.ubid,
               cr_a.source_system, cr_a.source_record_id,
               cr_b.source_system, cr_b.source_record_id
        FROM linkage_pairs lp
        JOIN ubid_source_links usl_a ON usl_a.canonical_id = lp.canonical_id_a
        JOIN ubid_source_links usl_b ON usl_b.canonical_id = lp.canonical_id_b
        JOIN canonical_records cr_a ON cr_a.canonical_id = lp.canonical_id_a
        JOIN canonical_records cr_b ON cr_b.canonical_id = lp.canonical_id_b
        WHERE usl_a.ubid = usl_b.ubid
          AND lp.calibrated_probability >= 0.95
        LIMIT 1
        """,
    ], text=True).strip()
    if not out:
        return None
    parts = out.split("|")
    if len(parts) < 8:
        return None
    return {
        "pair_id": parts[0],
        "canonical_id_a": parts[1],
        "canonical_id_b": parts[2],
        "shared_ubid": parts[3],
        "src_a": parts[4],
        "rid_a": parts[5],
        "src_b": parts[6],
        "rid_b": parts[7],
    }


def demo_cannot_link():
    print("\n== DEMO 2: reject splits a merged UBID ========================─")
    p = find_currently_merged_pair()
    if not p:
        print("  No auto-linked pair currently sharing a UBID — skipping.")
        return

    print(f"  Auto-linked pair sharing UBID {p['shared_ubid'][:8]}:")
    print(f"  A ({p['src_a']}/{p['rid_a']})")
    print(f"  B ({p['src_b']}/{p['rid_b']})")

    print("  Submitting reject (cannot_link)...")
    post("/api/v1/review/decide", {
        "pair_id": p["pair_id"],
        "canonical_id_a": p["canonical_id_a"],
        "canonical_id_b": p["canonical_id_b"],
        "decision": "reject",
        "reviewer_id": "demo_reviewer",
        "reviewer_tier": "senior",
        "notes": "demo: should split the UBID",
    })

    ubid_a = lookup_ubid(p["canonical_id_a"], p["src_a"], p["rid_a"])
    ubid_b = lookup_ubid(p["canonical_id_b"], p["src_b"], p["rid_b"])
    diff = ubid_a != ubid_b
    print(f"  After:  A->{ubid_a[:8] if ubid_a else '?'}  "
          f"B->{ubid_b[:8] if ubid_b else '?'}  "
          f"different={diff}")
    print(f"  RESULT: {'PASS — UBID split' if diff else 'FAIL — still merged'}")


if __name__ == "__main__":
    try:
        demo_must_link()
        demo_cannot_link()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
