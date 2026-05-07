"""Re-geocode every canonical record, preferring Nominatim over the locality
dict so we get building-level precision wherever possible.
"""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from sqlalchemy import select  # noqa: E402

from ubid.api.routers.ingest import _orm_to_canonical  # noqa: E402
from ubid.canonicalize.geocoder import (  # noqa: E402
    geocode, query_nominatim, _within_karnataka, stats,
)
from ubid.storage.postgres import CanonicalRecordORM, get_db  # noqa: E402


def main():
    print("Geocoder state:", stats())

    with get_db() as db:
        rows = db.execute(select(CanonicalRecordORM)).scalars().all()

    total = len(rows)
    print(f"\nProcessing {total} canonical records...")

    nominatim_hits = 0
    dict_hits = 0
    failed = 0
    distinct = set()

    for i, orm in enumerate(rows):
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{total} processed...")
        rec = _orm_to_canonical(orm)
        rec.latitude = None
        rec.longitude = None

        coords = None
        if rec.address_raw:
            n_coords = query_nominatim(rec.address_raw)
            if n_coords and _within_karnataka(n_coords):
                coords = n_coords
                nominatim_hits += 1

        if not coords:
            coords = geocode(rec)
            if coords:
                dict_hits += 1

        if not coords:
            failed += 1
            continue

        with get_db() as db:
            db_orm = db.get(CanonicalRecordORM, str(orm.canonical_id))
            if db_orm:
                db_orm.latitude = coords[0]
                db_orm.longitude = coords[1]

        distinct.add((round(coords[0], 4), round(coords[1], 4)))

    print(f"\n=== Results ===")
    print(f"Nominatim hits: {nominatim_hits}")
    print(f"Dict fallback hits: {dict_hits}")
    print(f"Failed: {failed}")
    print(f"Distinct coordinate clusters: {len(distinct)}")
    print(f"  (more clusters = better precision; pure-dict was ~25)")


if __name__ == "__main__":
    main()
