"""Analytical query API — the exemplar query class from the proposal.

Key query: 'active factories in pin code X with no inspection in last N months'
"""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from ubid.storage.postgres import get_db
from ubid.activity.quarantine import get_quarantine_stats
from ubid.review.queue import queue_stats

router = APIRouter()
logger = logging.getLogger(__name__)


class ActiveBusinessQuery(BaseModel):
    verdict: str = "active"                      # active | dormant | closed | nascent
    pin_code: Optional[str] = None
    district: Optional[str] = None
    sector_keyword: Optional[str] = None
    source_system: Optional[str] = None          # filter by department
    no_event_type: Optional[str] = None          # e.g. "fac_inspection"
    no_event_since_days: Optional[int] = None    # e.g. 540 (18 months)
    limit: int = 100
    offset: int = 0


@router.post("/active-businesses")
def query_active_businesses(body: ActiveBusinessQuery):
    """
    The proposal's exemplar: 'active factories in pin code 560058
    with no inspection in the last 18 months'.
    """
    params: dict = {"verdict": body.verdict, "limit": body.limit, "offset": body.offset}
    filters = ["av.verdict = :verdict"]

    if body.pin_code:
        filters.append("u.pin_code = :pin_code")
        params["pin_code"] = body.pin_code

    if body.district:
        filters.append("LOWER(u.district) = LOWER(:district)")
        params["district"] = body.district

    if body.sector_keyword:
        filters.append("LOWER(u.sector_canonical) LIKE :sector")
        params["sector"] = f"%{body.sector_keyword.lower()}%"

    if body.source_system:
        filters.append("""
            u.ubid IN (
                SELECT DISTINCT usl.ubid FROM ubid_source_links usl
                JOIN canonical_records cr ON usl.canonical_id = cr.canonical_id
                WHERE cr.source_system = :source_system
            )
        """)
        params["source_system"] = body.source_system

    if body.no_event_type and body.no_event_since_days:
        filters.append("""
            u.ubid NOT IN (
                SELECT DISTINCT ae.ubid FROM activity_events ae
                WHERE ae.event_type = :no_event_type
                  AND ae.event_date >= CURRENT_DATE - INTERVAL ':no_event_days days'
                  AND ae.ubid IS NOT NULL
            )
        """)
        params["no_event_type"] = body.no_event_type
        params["no_event_days"] = body.no_event_since_days

    where_clause = " AND ".join(filters)

    sql = text(f"""
        SELECT
            u.ubid,
            u.pin_code,
            u.district,
            u.sector_canonical,
            av.verdict,
            av.continuity_score,
            av.computed_at,
            COUNT(usl.canonical_id) AS source_record_count
        FROM ubid_nodes u
        JOIN activity_verdicts av ON u.ubid = av.ubid
        LEFT JOIN ubid_source_links usl ON u.ubid = usl.ubid
        WHERE {where_clause}
        GROUP BY u.ubid, u.pin_code, u.district, u.sector_canonical,
                 av.verdict, av.continuity_score, av.computed_at
        ORDER BY av.continuity_score DESC
        LIMIT :limit OFFSET :offset
    """)

    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
        total_sql = text(f"""
            SELECT COUNT(DISTINCT u.ubid)
            FROM ubid_nodes u
            JOIN activity_verdicts av ON u.ubid = av.ubid
            WHERE {where_clause}
        """)
        total = db.execute(total_sql, params).scalar() or 0

    return {
        "total": total,
        "results": [
            {
                "ubid": str(r.ubid),
                "pin_code": r.pin_code,
                "district": r.district,
                "sector": r.sector_canonical,
                "verdict": r.verdict,
                "continuity_score": r.continuity_score,
                "source_record_count": r.source_record_count,
                "verdict_computed_at": str(r.computed_at),
            }
            for r in rows
        ],
        "query": body.model_dump(),
    }


@router.get("/stats")
def platform_stats():
    """High-level platform dashboard metrics."""
    with get_db() as db:
        total_ubids = db.execute(text("SELECT COUNT(*) FROM ubid_nodes")).scalar() or 0
        verdict_dist = db.execute(text("""
            SELECT verdict, COUNT(*) as cnt
            FROM activity_verdicts
            GROUP BY verdict
        """)).fetchall()
        total_records = db.execute(text("SELECT COUNT(*) FROM canonical_records")).scalar() or 0
        by_source = db.execute(text("""
            SELECT source_system, COUNT(*) as cnt
            FROM canonical_records
            GROUP BY source_system
        """)).fetchall()

    return {
        "total_ubids": total_ubids,
        "total_source_records": total_records,
        "verdict_distribution": {r.verdict: r.cnt for r in verdict_dist},
        "records_by_source": {r.source_system: r.cnt for r in by_source},
        "queue": queue_stats(),
        "quarantine": get_quarantine_stats(),
    }
