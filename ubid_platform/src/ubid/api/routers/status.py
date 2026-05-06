"""UBID status API — activity verdict + evidence timeline."""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text, select

from ubid.activity.verdict import compute_verdict, VerdictResult
from ubid.schema.events import ActivityEvent, EventType
from ubid.schema.canonical import SourceSystem
from ubid.storage.postgres import get_db, UBIDNodeORM, ActivityVerdictORM
from ubid.storage import redis_cache
from ubid.storage.duckdb_warehouse import get_events_for_ubid
from ubid.graph import neo4j_graph

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{ubid}")
def get_ubid_detail(ubid: str):
    """Full UBID details: legal entity, all linked source records, current verdict."""
    with get_db() as db:
        node = db.get(UBIDNodeORM, ubid)
        if not node:
            raise HTTPException(404, f"UBID {ubid} not found")

    graph_data = neo4j_graph.get_ubid_details(ubid)
    verdict_cached = redis_cache.get_verdict_cache(ubid)

    return {
        "ubid": ubid,
        "pin_code": node.pin_code,
        "district": node.district,
        "sector": node.sector_canonical,
        "created_at": node.created_at,
        "legal_entity": graph_data.get("legal_entity"),
        "source_records": graph_data.get("source_records", []),
        "verdict": verdict_cached,
    }


@router.get("/{ubid}/status")
def get_ubid_status(
    ubid: str,
    force_recompute: bool = Query(False, description="Bypass cache and recompute verdict"),
):
    """Activity verdict with full evidence timeline."""

    # Serve from cache unless forced
    if not force_recompute:
        cached = redis_cache.get_verdict_cache(ubid)
        if cached:
            return cached

    with get_db() as db:
        node = db.get(UBIDNodeORM, ubid)
        if not node:
            raise HTTPException(404, f"UBID {ubid} not found")

    # Load events from DuckDB
    raw_events = get_events_for_ubid(ubid, lookback_days=730)

    events: list[ActivityEvent] = []
    for row in raw_events:
        try:
            events.append(ActivityEvent(
                event_id=row["event_id"],
                source_system=row["source_system"],
                source_record_id="",
                event_type=EventType(row["event_type"]),
                event_date=row["event_date"],
                ubid=ubid,
                metadata=row.get("metadata") or {},
            ))
        except Exception:
            continue

    result = compute_verdict(
        ubid=ubid,
        events=events,
        sector=node.sector_canonical,
    )

    response = {
        "ubid": ubid,
        "verdict": result.verdict,
        "continuity_score": result.continuity_score,
        "evidence_timeline": [e.__dict__ for e in result.evidence_timeline],
        "deterministic_overrides": result.deterministic_overrides,
        "sector_prior_applied": result.sector_prior_applied,
        "computed_at": str(result.computed_at),
    }

    # Persist verdict and cache
    _persist_verdict(ubid, result)
    redis_cache.set_verdict_cache(ubid, response, ttl=300)

    return response


def _persist_verdict(ubid: str, result: VerdictResult):
    from datetime import datetime, timezone
    import uuid
    with get_db() as db:
        existing = db.execute(
            select(ActivityVerdictORM).where(ActivityVerdictORM.ubid == ubid)
        ).scalar_one_or_none()

        timeline_json = [e.__dict__ for e in result.evidence_timeline]

        if existing:
            existing.verdict = result.verdict
            existing.continuity_score = result.continuity_score
            existing.evidence_timeline = timeline_json
            existing.deterministic_overrides = result.deterministic_overrides
            existing.sector_prior_applied = result.sector_prior_applied
            existing.computed_at = datetime.now(timezone.utc)
        else:
            db.add(ActivityVerdictORM(
                verdict_id=str(uuid.uuid4()),
                ubid=ubid,
                verdict=result.verdict,
                continuity_score=result.continuity_score,
                evidence_timeline=timeline_json,
                deterministic_overrides=result.deterministic_overrides,
                sector_prior_applied=result.sector_prior_applied,
                computed_at=datetime.now(timezone.utc),
            ))
