"""Lookup API — resolve any identifier to a UBID."""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text, select

from ubid.storage.postgres import get_db, CanonicalRecordORM, UBIDSourceLinkORM
from ubid.storage import redis_cache
from ubid.graph import neo4j_graph

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
def lookup_ubid(
    source: Optional[str] = Query(None, description="Source system (ekarmika/fbis/kspcb/bescom)"),
    id: Optional[str] = Query(None, description="Source record ID"),
    pan: Optional[str] = Query(None, description="PAN of the legal entity"),
    name: Optional[str] = Query(None, description="Business name (fuzzy)"),
    pin: Optional[str] = Query(None, description="Pin code"),
):
    """Resolve any department record ID, PAN, or name+pin to a UBID."""

    # ── By source + record ID ──────────────────────────────────────────────
    if source and id:
        ubid = redis_cache.get_ubid_for_source(source, id)
        if ubid:
            return {"ubid": ubid, "resolved_via": "cache"}

        with get_db() as db:
            row = db.execute(text("""
                SELECT u.ubid
                FROM ubid_source_links usl
                JOIN ubid_nodes u ON usl.ubid = u.ubid
                JOIN canonical_records cr ON usl.canonical_id = cr.canonical_id
                WHERE cr.source_system = :sys AND cr.source_record_id = :rid
                LIMIT 1
            """), {"sys": source, "rid": id}).first()

        if row:
            redis_cache.set_ubid_for_source(source, id, str(row.ubid))
            return {"ubid": str(row.ubid), "resolved_via": "database"}

        raise HTTPException(404, f"No UBID found for {source}:{id}")

    # ── By PAN ────────────────────────────────────────────────────────────
    if pan:
        ubids = neo4j_graph.find_ubids_by_pan(pan.upper())
        if ubids:
            return {"ubids": ubids, "resolved_via": "pan_lookup"}

        with get_db() as db:
            rows = db.execute(text("""
                SELECT DISTINCT u.ubid
                FROM ubid_source_links usl
                JOIN ubid_nodes u ON usl.ubid = u.ubid
                JOIN canonical_records cr ON usl.canonical_id = cr.canonical_id
                WHERE cr.pan = :pan OR cr.legal_entity_pan = :pan
            """), {"pan": pan.upper()}).fetchall()

        if rows:
            return {"ubids": [str(r.ubid) for r in rows], "resolved_via": "pan_lookup"}

        raise HTTPException(404, f"No UBID found for PAN {pan}")

    # ── By name + pin (fuzzy) ─────────────────────────────────────────────
    if name and pin:
        from ubid.canonicalize import name_normalizer
        norm, _, _ = name_normalizer.normalize(name)
        prefix4 = name_normalizer.name_prefix4(norm)
        blocking_key = f"{pin}|{prefix4}"

        with get_db() as db:
            rows = db.execute(text("""
                SELECT DISTINCT u.ubid, cr.name_raw, cr.source_system
                FROM ubid_source_links usl
                JOIN ubid_nodes u ON usl.ubid = u.ubid
                JOIN canonical_records cr ON usl.canonical_id = cr.canonical_id
                WHERE cr.blocking_pin_name = :key
                LIMIT 10
            """), {"key": blocking_key}).fetchall()

        if rows:
            return {
                "candidates": [
                    {"ubid": str(r.ubid), "name": r.name_raw, "source": r.source_system}
                    for r in rows
                ],
                "resolved_via": "fuzzy_name_pin",
            }

        raise HTTPException(404, "No candidates found for name+pin combination")

    raise HTTPException(400, "Provide source+id, pan, or name+pin")
