"""UBID status API — activity verdict + evidence timeline."""
from __future__ import annotations
import logging
from datetime import date
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


@router.get("")
def list_ubids(
    verdict: Optional[str] = Query(None, description="Filter: active|dormant|closed|closed_by_silence|nascent"),
    pin_code: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    source_system: Optional[str] = Query(None, description="Filter: only UBIDs containing a record from this source"),
    min_records: int = Query(1, ge=1, description="Minimum source-record count per UBID"),
    search: Optional[str] = Query(None, description="Substring match on any source record's name_normalized"),
    audit_status: Optional[str] = Query(None, description="Filter: pending|approved (audit status). 'pending' = at least one member-pair has no must-link constraint."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Paginated list of UBIDs with verdict, record count, audit status, and quick filters."""
    filters = ["1=1"]
    params: dict = {"limit": limit, "offset": offset}
    if verdict:
        filters.append("av.verdict = :verdict")
        params["verdict"] = verdict
    if pin_code:
        filters.append("u.pin_code = :pin_code")
        params["pin_code"] = pin_code
    if district:
        filters.append("LOWER(u.district) = LOWER(:district)")
        params["district"] = district
    if source_system:
        filters.append("""u.ubid IN (
            SELECT DISTINCT usl.ubid FROM ubid_source_links usl
            JOIN canonical_records cr ON usl.canonical_id = cr.canonical_id
            WHERE cr.source_system = :source_system
        )""")
        params["source_system"] = source_system
    if search:
        filters.append("""u.ubid IN (
            SELECT DISTINCT usl.ubid FROM ubid_source_links usl
            JOIN canonical_records cr ON usl.canonical_id = cr.canonical_id
            WHERE LOWER(cr.name_normalized) LIKE :search
        )""")
        params["search"] = f"%{search.lower()}%"

    # Audit-status filter: a UBID is "approved" only when every pair of its
    # members has a must-link constraint. Anything else is "pending".
    if audit_status == "approved":
        filters.append("""u.ubid IN (
            SELECT usl.ubid
            FROM ubid_source_links usl
            GROUP BY usl.ubid
            HAVING COUNT(usl.canonical_id) >= 2
               AND COUNT(usl.canonical_id) * (COUNT(usl.canonical_id) - 1) / 2 = (
                   SELECT COUNT(*) FROM linkage_constraints lc
                   WHERE lc.constraint_type = 'must_link'
                     AND lc.canonical_id_a IN (
                         SELECT canonical_id FROM ubid_source_links WHERE ubid = usl.ubid
                     )
                     AND lc.canonical_id_b IN (
                         SELECT canonical_id FROM ubid_source_links WHERE ubid = usl.ubid
                     )
               )
        )""")
    elif audit_status == "pending":
        filters.append("""u.ubid NOT IN (
            SELECT usl.ubid
            FROM ubid_source_links usl
            GROUP BY usl.ubid
            HAVING COUNT(usl.canonical_id) >= 2
               AND COUNT(usl.canonical_id) * (COUNT(usl.canonical_id) - 1) / 2 = (
                   SELECT COUNT(*) FROM linkage_constraints lc
                   WHERE lc.constraint_type = 'must_link'
                     AND lc.canonical_id_a IN (
                         SELECT canonical_id FROM ubid_source_links WHERE ubid = usl.ubid
                     )
                     AND lc.canonical_id_b IN (
                         SELECT canonical_id FROM ubid_source_links WHERE ubid = usl.ubid
                     )
               )
        )""")

    where = " AND ".join(filters)

    with get_db() as db:
        total = db.execute(text(f"""
            SELECT COUNT(DISTINCT u.ubid)
            FROM ubid_nodes u
            LEFT JOIN activity_verdicts av ON av.ubid = u.ubid
            WHERE {where}
        """), params).scalar() or 0

        rows = db.execute(text(f"""
            SELECT
                u.ubid,
                u.pin_code,
                u.district,
                u.sector_canonical,
                COALESCE(av.verdict, 'unknown') AS verdict,
                COALESCE(av.continuity_score, 0) AS score,
                av.computed_at,
                COUNT(usl.canonical_id) AS record_count,
                STRING_AGG(DISTINCT cr.source_system, ',' ORDER BY cr.source_system) AS sources,
                MAX(cr.name_raw) AS sample_name,
                (
                    SELECT COUNT(*) FROM linkage_constraints lc
                    WHERE lc.constraint_type = 'must_link'
                      AND lc.canonical_id_a IN (SELECT canonical_id FROM ubid_source_links WHERE ubid = u.ubid)
                      AND lc.canonical_id_b IN (SELECT canonical_id FROM ubid_source_links WHERE ubid = u.ubid)
                ) AS must_link_count
            FROM ubid_nodes u
            LEFT JOIN activity_verdicts av ON av.ubid = u.ubid
            LEFT JOIN ubid_source_links usl ON usl.ubid = u.ubid
            LEFT JOIN canonical_records cr ON cr.canonical_id = usl.canonical_id
            WHERE {where}
            GROUP BY u.ubid, u.pin_code, u.district, u.sector_canonical,
                     av.verdict, av.continuity_score, av.computed_at
            HAVING COUNT(usl.canonical_id) >= :min_records
            ORDER BY COALESCE(av.continuity_score, 0) DESC, u.ubid
            LIMIT :limit OFFSET :offset
        """), {**params, "min_records": min_records}).fetchall()

    def _audit_status(record_count: int, must_link_count: int) -> str:
        if record_count < 2:
            return "singleton"
        expected_pairs = record_count * (record_count - 1) // 2
        return "approved" if must_link_count >= expected_pairs else "pending"

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [
            {
                "ubid": str(r.ubid),
                "verdict": r.verdict,
                "continuity_score": float(r.score) if r.score is not None else 0.0,
                "pin_code": r.pin_code,
                "district": r.district,
                "sector": r.sector_canonical,
                "record_count": r.record_count,
                "sources": (r.sources or "").split(",") if r.sources else [],
                "sample_name": r.sample_name,
                "verdict_computed_at": str(r.computed_at) if r.computed_at else None,
                "audit_status": _audit_status(r.record_count, r.must_link_count or 0),
                "must_link_count": r.must_link_count or 0,
            }
            for r in rows
        ],
    }


@router.get("/{ubid}/pair-evidence")
def get_pair_evidence(ubid: str):
    """For each pair of records in a UBID, return how confident the model
    was about merging them — calibrated probability, top SHAP features,
    shared blocks, plus existing constraints.

    Drives the merge-audit UI: lets a reviewer see *why* the system grouped
    these records and decide whether each pair really belongs together.
    """
    with get_db() as db:
        members = db.execute(text("""
            SELECT cr.canonical_id, cr.source_system, cr.source_record_id,
                   cr.name_raw, cr.pin_code, cr.pan
            FROM ubid_source_links usl
            JOIN canonical_records cr ON cr.canonical_id = usl.canonical_id
            WHERE usl.ubid = :u
            ORDER BY cr.source_system, cr.source_record_id
        """), {"u": ubid}).fetchall()
        member_ids = [str(m.canonical_id) for m in members]

        if len(member_ids) < 2:
            return {"ubid": ubid, "members": len(member_ids), "pairs": []}

        # Pull every linkage_pair row connecting two members
        prows = db.execute(text("""
            SELECT canonical_id_a, canonical_id_b, calibrated_probability, raw_score,
                   deterministic_tier_fired, deterministic_result,
                   shap_contributions, shared_blocks
            FROM linkage_pairs
            WHERE canonical_id_a IN :ids AND canonical_id_b IN :ids
        """).bindparams(__import__("sqlalchemy").bindparam("ids", expanding=True)),
            {"ids": member_ids}).fetchall()

        pair_map = {
            tuple(sorted([str(p.canonical_id_a), str(p.canonical_id_b)])): p
            for p in prows
        }

        crows = db.execute(text("""
            SELECT canonical_id_a, canonical_id_b, constraint_type, created_by, created_at
            FROM linkage_constraints
            WHERE canonical_id_a IN :ids AND canonical_id_b IN :ids
        """).bindparams(__import__("sqlalchemy").bindparam("ids", expanding=True)),
            {"ids": member_ids}).fetchall()
        constraint_map = {
            tuple(sorted([str(c.canonical_id_a), str(c.canonical_id_b)])): c
            for c in crows
        }

    member_by_id = {str(m.canonical_id): m for m in members}

    pairs = []
    for i in range(len(member_ids)):
        for j in range(i + 1, len(member_ids)):
            a, b = sorted([member_ids[i], member_ids[j]])
            p = pair_map.get((a, b))
            c = constraint_map.get((a, b))
            shap = (p.shap_contributions if p else None) or {}
            top = sorted(shap.items(), key=lambda x: abs(x[1]), reverse=True)[:5] if shap else []

            pairs.append({
                "canonical_id_a": a,
                "canonical_id_b": b,
                "record_a_label": f"{member_by_id[a].source_system}/{member_by_id[a].source_record_id}",
                "record_b_label": f"{member_by_id[b].source_system}/{member_by_id[b].source_record_id}",
                "calibrated_probability": (
                    float(p.calibrated_probability) if p and p.calibrated_probability is not None else None
                ),
                "raw_score": float(p.raw_score) if p and p.raw_score is not None else None,
                "deterministic_tier_fired": p.deterministic_tier_fired if p else False,
                "deterministic_result": p.deterministic_result if p else None,
                "shared_blocks": (p.shared_blocks if p else []) or [],
                "top_features": [{"name": k, "contribution": round(v, 4)} for k, v in top],
                "constraint": c.constraint_type if c else None,
                "constraint_by": c.created_by if c else None,
            })

    return {"ubid": ubid, "members": len(member_ids), "pairs": pairs}


@router.get("/{ubid}")
def get_ubid_detail(ubid: str):
    """Full UBID details: every linked source record (from Postgres, the
    source of truth), latest verdict, and Neo4j legal-entity context if any."""
    with get_db() as db:
        node = db.get(UBIDNodeORM, ubid)
        if not node:
            raise HTTPException(404, f"UBID {ubid} not found")

        rows = db.execute(text("""
            SELECT cr.canonical_id, cr.source_system, cr.source_record_id,
                   cr.name_raw, cr.name_normalized, cr.address_raw, cr.pin_code,
                   cr.district, cr.pan, cr.gstin, cr.phone, cr.sector_raw,
                   cr.legal_form, cr.employee_count, cr.registration_date,
                   usl.linked_by, usl.linked_at, usl.confidence
            FROM ubid_source_links usl
            JOIN canonical_records cr ON cr.canonical_id = usl.canonical_id
            WHERE usl.ubid = :u
            ORDER BY cr.source_system, cr.source_record_id
        """), {"u": ubid}).fetchall()
        source_records = [
            {
                "canonical_id": str(r.canonical_id),
                "source_system": r.source_system,
                "source_record_id": r.source_record_id,
                "name_raw": r.name_raw,
                "name_normalized": r.name_normalized,
                "address_raw": r.address_raw,
                "pin_code": r.pin_code,
                "district": r.district,
                "pan": r.pan,
                "gstin": r.gstin,
                "phone": r.phone,
                "sector_raw": r.sector_raw,
                "legal_form": r.legal_form,
                "employee_count": r.employee_count,
                "registration_date": str(r.registration_date) if r.registration_date else None,
                "linked_by": r.linked_by,
                "linked_at": str(r.linked_at) if r.linked_at else None,
                "confidence": float(r.confidence) if r.confidence is not None else None,
            }
            for r in rows
        ]

        verdict_row = db.execute(
            select(ActivityVerdictORM).where(ActivityVerdictORM.ubid == ubid)
        ).scalar_one_or_none()
        verdict_payload = None
        if verdict_row:
            verdict_payload = {
                "verdict": verdict_row.verdict,
                "continuity_score": verdict_row.continuity_score,
                "computed_at": str(verdict_row.computed_at) if verdict_row.computed_at else None,
                "evidence_timeline": verdict_row.evidence_timeline or [],
                "deterministic_overrides": verdict_row.deterministic_overrides or [],
                "sector_prior_applied": verdict_row.sector_prior_applied,
            }

    legal_entity = None
    try:
        graph_data = neo4j_graph.get_ubid_details(ubid)
        legal_entity = graph_data.get("legal_entity")
    except Exception:
        legal_entity = None

    return {
        "ubid": ubid,
        "pin_code": node.pin_code,
        "district": node.district,
        "sector": node.sector_canonical,
        "created_at": str(node.created_at) if node.created_at else None,
        "legal_entity": legal_entity,
        "source_records": source_records,
        "record_count": len(source_records),
        "verdict": verdict_payload,
    }


@router.get("/{ubid}/status")
def get_ubid_status(
    ubid: str,
    force_recompute: bool = Query(False, description="Bypass cache and recompute verdict"),
    reference_date: Optional[date] = Query(
        None,
        description="ISO date treated as 'today' for decay computation. Defaults to today.",
    ),
    lookback_days: int = Query(
        730, description="How many days back to consider events from the reference date."
    ),
):
    """Activity verdict with full evidence timeline."""

    # Cache key includes reference_date so two different references don't collide
    cache_key_suffix = f"::ref={reference_date}" if reference_date else ""

    if not force_recompute:
        cached = redis_cache.get_verdict_cache(f"{ubid}{cache_key_suffix}")
        if cached:
            return cached

    with get_db() as db:
        node = db.get(UBIDNodeORM, ubid)
        if not node:
            raise HTTPException(404, f"UBID {ubid} not found")

    raw_events = get_events_for_ubid(
        ubid,
        lookback_days=lookback_days,
        reference_date=reference_date,
    )

    events: list[ActivityEvent] = []
    for row in raw_events:
        try:
            md = row.get("metadata")
            if isinstance(md, str):
                import json as _json
                try:
                    md = _json.loads(md)
                except Exception:
                    md = {}
            events.append(ActivityEvent(
                event_id=row["event_id"],
                source_system=row["source_system"],
                source_record_id="",
                event_type=EventType(row["event_type"]),
                event_date=row["event_date"],
                ubid=ubid,
                metadata=md or {},
            ))
        except Exception as e:
            logger.debug("Skipping event row: %s — %s", e, row)
            continue

    result = compute_verdict(
        ubid=ubid,
        events=events,
        sector=node.sector_canonical,
        reference_date=reference_date,
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
    redis_cache.set_verdict_cache(f"{ubid}{cache_key_suffix}", response, ttl=300)

    return response


@router.get("/{ubid}/audit")
def get_ubid_audit_trail(ubid: str):
    """Lineage of how this UBID was assembled — which records were linked, when,
    by whom, plus every reviewer decision touching its members."""
    with get_db() as db:
        node = db.get(UBIDNodeORM, ubid)
        if not node:
            raise HTTPException(404, f"UBID {ubid} not found")

        # All current source-link rows for this UBID
        link_rows = db.execute(text("""
            SELECT usl.canonical_id, usl.linked_at, usl.linked_by, usl.confidence,
                   cr.source_system, cr.source_record_id, cr.name_raw
            FROM ubid_source_links usl
            JOIN canonical_records cr ON cr.canonical_id = usl.canonical_id
            WHERE usl.ubid = :u
            ORDER BY usl.linked_at
        """), {"u": ubid}).fetchall()

        member_ids = [str(r.canonical_id) for r in link_rows]

        # Reviewer decisions touching any member
        decisions = []
        if member_ids:
            drows = db.execute(text("""
                SELECT decision_id, pair_id, canonical_id_a, canonical_id_b,
                       decision, reviewer_id, reviewer_tier, notes, decided_at
                FROM reviewer_decisions
                WHERE canonical_id_a IN :ids OR canonical_id_b IN :ids
                ORDER BY decided_at DESC
            """).bindparams(__import__("sqlalchemy").bindparam("ids", expanding=True)),
                {"ids": member_ids}).fetchall()
            decisions = [
                {
                    "decision_id": str(d.decision_id),
                    "pair_id": str(d.pair_id),
                    "canonical_id_a": str(d.canonical_id_a),
                    "canonical_id_b": str(d.canonical_id_b),
                    "decision": d.decision,
                    "reviewer_id": d.reviewer_id,
                    "reviewer_tier": d.reviewer_tier,
                    "notes": d.notes,
                    "decided_at": str(d.decided_at) if d.decided_at else None,
                }
                for d in drows
            ]

        # Constraints (must-link / cannot-link) on member pairs
        constraints = []
        if member_ids:
            crows = db.execute(text("""
                SELECT canonical_id_a, canonical_id_b, constraint_type,
                       created_by, created_at, notes
                FROM linkage_constraints
                WHERE canonical_id_a IN :ids OR canonical_id_b IN :ids
                ORDER BY created_at DESC
            """).bindparams(__import__("sqlalchemy").bindparam("ids", expanding=True)),
                {"ids": member_ids}).fetchall()
            constraints = [
                {
                    "canonical_id_a": str(c.canonical_id_a),
                    "canonical_id_b": str(c.canonical_id_b),
                    "constraint_type": c.constraint_type,
                    "created_by": c.created_by,
                    "created_at": str(c.created_at) if c.created_at else None,
                    "notes": c.notes,
                }
                for c in crows
            ]

    # Build a unified timeline (link events + decisions + constraints)
    events: list[dict] = []
    for r in link_rows:
        events.append({
            "ts": str(r.linked_at) if r.linked_at else "",
            "kind": "link",
            "actor": r.linked_by,
            "summary": f"linked {r.source_system}/{r.source_record_id} to UBID",
            "details": {
                "canonical_id": str(r.canonical_id),
                "source_system": r.source_system,
                "source_record_id": r.source_record_id,
                "name_raw": r.name_raw,
                "confidence": float(r.confidence) if r.confidence is not None else None,
            },
        })
    for d in decisions:
        events.append({
            "ts": d["decided_at"] or "",
            "kind": "decision",
            "actor": f"{d['reviewer_id']} ({d['reviewer_tier']})",
            "summary": f"reviewer decision: {d['decision']}",
            "details": d,
        })
    for c in constraints:
        events.append({
            "ts": c["created_at"] or "",
            "kind": "constraint",
            "actor": c["created_by"],
            "summary": f"{c['constraint_type']} constraint",
            "details": c,
        })
    events.sort(key=lambda e: e["ts"], reverse=True)

    return {
        "ubid": ubid,
        "created_at": str(node.created_at) if node.created_at else None,
        "current_member_count": len(link_rows),
        "members": [
            {
                "canonical_id": str(r.canonical_id),
                "source_system": r.source_system,
                "source_record_id": r.source_record_id,
                "name_raw": r.name_raw,
                "linked_by": r.linked_by,
                "linked_at": str(r.linked_at) if r.linked_at else None,
                "confidence": float(r.confidence) if r.confidence is not None else None,
            }
            for r in link_rows
        ],
        "decision_count": len(decisions),
        "constraint_count": len(constraints),
        "timeline": events,
    }


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
