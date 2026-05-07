"""Generate synthetic BWSSB (water supply) records and events.

Samples 25 existing UBIDs from Postgres and creates 1-2 BWSSB water
connections at each one's address — mimicking the real-world case where a
business has both electricity (BESCOM) and water (BWSSB) connections.

Then generates ~250 monthly bill events spanning Jan 2024 → Apr 2025.

Outputs:
  data/synthetic/bwssb_records.csv    — 25-30 connections
  data/synthetic/bwssb_events.jsonl   — ~250 events
"""
from __future__ import annotations
import csv
import json
import random
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import select  # noqa: E402

from ubid.storage.postgres import CanonicalRecordORM, get_db  # noqa: E402

OUT_CSV   = _REPO / "data" / "synthetic" / "bwssb_records.csv"
OUT_EVTS  = _REPO / "data" / "synthetic" / "bwssb_events.jsonl"


def _make_connection_size_for_business():
    return random.choices([15, 20, 25, 50, 100], weights=[1, 2, 4, 3, 1])[0]


def _knca() -> str:
    prefix = random.choice(["W", "BW", "K"])
    digits = "".join(str(random.randint(0, 9)) for _ in range(8))
    return f"{prefix}{digits}"


def _maybe_landlord_name(business_name: str) -> str:
    if random.random() < 0.30:
        first = ["Rajesh", "Lakshmi", "Mahesh", "Suresh", "Ramesh",
                  "Anand", "Geetha", "Naidu", "Patel", "Iyer"]
        last = ["Kumar", "Rao", "Reddy", "Sharma", "Naidu",
                 "Hegde", "Shetty", "Gowda", "Bhat", "Murthy"]
        return f"{random.choice(first)} {random.choice(last)}"
    return business_name


def main():
    random.seed(7)

    with get_db() as db:
        candidates = list(db.execute(
            select(CanonicalRecordORM).where(
                CanonicalRecordORM.source_system.in_(["ekarmika", "fbis", "kspcb"]),
                CanonicalRecordORM.address_raw.isnot(None),
            )
        ).scalars())

    print(f"Found {len(candidates)} canonical records to sample addresses from")
    if not candidates:
        print("ERROR: no source records to seed BWSSB data from. Re-ingest first.")
        return

    sampled = random.sample(candidates, min(25, len(candidates)))

    rows = []
    for src in sampled:
        n_connections = random.choices([1, 2], weights=[7, 3])[0]
        for k in range(n_connections):
            knca = _knca()
            consumer = _maybe_landlord_name(src.name_raw or "")
            size = _make_connection_size_for_business()
            tariff = "domestic" if size == 15 else (
                "commercial" if size in (20, 25) else "industrial")
            phone = (
                f"9{random.randint(100_000_000, 999_999_999)}"
                if random.random() < 0.4 else ""
            )
            rows.append({
                "knca_number": knca,
                "account_id": f"BWS{random.randint(100000, 999999)}",
                "consumer_number": str(random.randint(10000000, 99999999)),
                "consumer_name": consumer,
                "service_address": src.address_raw or "",
                "tariff_category": tariff,
                "connection_size_mm": size,
                "phone": phone,
            })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "knca_number", "account_id", "consumer_number", "consumer_name",
            "service_address", "tariff_category", "connection_size_mm", "phone",
        ])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"Wrote {len(rows)} BWSSB records -> {OUT_CSV.name}")

    events = []
    for r in rows:
        if random.random() < 0.80:
            d = date(2024, 1, 5)
            while d <= date(2025, 4, 30):
                events.append({
                    "event_id": str(uuid.uuid4()),
                    "source_system": "bwssb",
                    "source_record_id": r["knca_number"],
                    "event_type": "bwssb_bill_generated",
                    "event_date": str(d),
                    "metadata": {"amount": round(random.uniform(150, 8000), 2)},
                })
                if random.random() < 0.90:
                    paid_d = d + timedelta(days=random.randint(7, 25))
                    if paid_d <= date(2025, 4, 30):
                        events.append({
                            "event_id": str(uuid.uuid4()),
                            "source_system": "bwssb",
                            "source_record_id": r["knca_number"],
                            "event_type": "bwssb_bill_paid",
                            "event_date": str(paid_d),
                            "metadata": {},
                        })
                d = (d.replace(day=28) + timedelta(days=10)).replace(day=5)

        if random.random() < 0.10:
            disc = date(2024, random.randint(3, 12), random.randint(1, 28))
            events.append({
                "event_id": str(uuid.uuid4()),
                "source_system": "bwssb",
                "source_record_id": r["knca_number"],
                "event_type": "bwssb_disconnect",
                "event_date": str(disc),
                "metadata": {},
            })
            if random.random() < 0.70:
                rec = disc + timedelta(days=random.randint(15, 90))
                events.append({
                    "event_id": str(uuid.uuid4()),
                    "source_system": "bwssb",
                    "source_record_id": r["knca_number"],
                    "event_type": "bwssb_reconnect",
                    "event_date": str(rec),
                    "metadata": {},
                })

    events.sort(key=lambda e: e["event_date"])

    with open(OUT_EVTS, "w", encoding="utf-8") as f:
        for evt in events:
            f.write(json.dumps(evt) + "\n")
    print(f"Wrote {len(events)} BWSSB events -> {OUT_EVTS.name}")


if __name__ == "__main__":
    main()
