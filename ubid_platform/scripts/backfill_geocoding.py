"""Backfill geocoding for canonical_records that don't yet have latitude/longitude.

Walks every canonical_record without coordinates, runs the geocoder, and
writes lat/lng back to Postgres. Safe to run multiple times — already-geocoded
records are skipped.

Usage (run inside the API container so we share its DuckDB lock + module path):
    docker cp scripts/backfill_geocoding.py ubid_platform-ubid-api-1:/app/scripts/
    docker exec ubid_platform-ubid-api-1 python /app/scripts/backfill_geocoding.py
"""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import select  # noqa: E402

from ubid.api.routers.ingest import _orm_to_canonical  # noqa: E402
from ubid.canonicalize.geocoder import geocode, stats  # noqa: E402
from ubid.storage.postgres import CanonicalRecordORM, get_db  # noqa: E402


def main():
    print("Geocoder dictionary state:", stats())

    with get_db() as db:
        # Pull only records that DON'T already have coordinates
        rows = db.execute(
            select(CanonicalRecordORM).where(
                (CanonicalRecordORM.latitude.is_(None))
                | (CanonicalRecordORM.longitude.is_(None))
            )
        ).scalars().all()

    total = len(rows)
    print(f"\nFound {total} records without coordinates. Backfilling…")

    updated = 0
    by_source = {}
    fail_by_source = {}

    for orm in rows:
        rec = _orm_to_canonical(orm)
        coords = geocode(rec)
        src = orm.source_system
        if coords:
            with get_db() as db:
                db_orm = db.get(CanonicalRecordORM, str(orm.canonical_id))
                if db_orm:
                    db_orm.latitude = coords[0]
                    db_orm.longitude = coords[1]
            updated += 1
            by_source[src] = by_source.get(src, 0) + 1
        else:
            fail_by_source[src] = fail_by_source.get(src, 0) + 1

    print(f"\nDone — {updated}/{total} records geocoded ({100*updated/max(total,1):.1f}%)")
    if by_source:
        print("\nGeocoded by source:")
        for s, n in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"  {s:12s}  {n:5d}")
    if fail_by_source:
        print("\nUngeocoded by source (no locality / pin / district matched):")
        for s, n in sorted(fail_by_source.items(), key=lambda x: -x[1]):
            print(f"  {s:12s}  {n:5d}")


if __name__ == "__main__":
    main()
