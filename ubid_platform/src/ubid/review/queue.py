"""Active-learning review queue.

Priority score = f(uncertainty, impact, signal_disagreement)

  uncertainty       — pairs near p=0.7-0.85 are more informative than near p=0.55
  impact            — clusters that affect more downstream events rank higher
  signal_disagreement — pairs where name is high but address is low (or vice versa)
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, and_, func

from ubid.config import get_settings
from ubid.schema.canonical import ScoredPair
from ubid.storage.postgres import (
    get_db, LinkagePairORM, ReviewerQueueORM, CanonicalRecordORM
)

logger = logging.getLogger(__name__)

UNCERTAINTY_OPTIMAL = 0.775   # midpoint of [0.55, 1.0] review band → maximize entropy
UNCERTAINTY_BANDWIDTH = 0.15


def _uncertainty_score(p: float) -> float:
    """Higher near 0.775, lower at extremes of the review band."""
    return max(0.0, 1.0 - abs(p - UNCERTAINTY_OPTIMAL) / UNCERTAINTY_BANDWIDTH)


def _signal_disagreement(fv: dict) -> float:
    """High disagreement = name says match but address says no (or vice versa)."""
    name_score = fv.get("name_jaro_winkler", 0.5)
    addr_score = fv.get("addr_pin_eq", 0.5)
    if addr_score < 0:
        addr_score = 0.5  # MISSING sentinel
    return abs(name_score - addr_score)


def compute_priority(pair: LinkagePairORM) -> float:
    uncertainty = _uncertainty_score(pair.calibrated_probability)
    disagreement = _signal_disagreement(pair.feature_vector or {})
    return round(0.6 * uncertainty + 0.4 * disagreement, 4)


def enqueue_pair(pair_id: str, calibrated_probability: float, feature_vector: dict):
    """Add a scored pair to the reviewer queue if it's in the review band."""
    settings = get_settings()
    if calibrated_probability < settings.review_threshold_low or calibrated_probability >= settings.auto_link_threshold:
        return  # outside review band

    priority = _uncertainty_score(calibrated_probability) * 0.6 + _signal_disagreement(feature_vector) * 0.4

    with get_db() as db:
        existing = db.execute(
            select(ReviewerQueueORM).where(ReviewerQueueORM.pair_id == pair_id)
        ).scalar_one_or_none()
        if existing:
            return

        item = ReviewerQueueORM(
            queue_id=str(uuid.uuid4()),
            pair_id=pair_id,
            priority_score=round(priority, 4),
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(item)


def get_pending_items(limit: int = 20, reviewer_id: Optional[str] = None) -> list[dict]:
    """Fetch top-priority pending review items with full pair context."""
    with get_db() as db:
        rows = db.execute(
            select(ReviewerQueueORM, LinkagePairORM)
            .join(LinkagePairORM, ReviewerQueueORM.pair_id == LinkagePairORM.pair_id)
            .where(ReviewerQueueORM.status == "pending")
            .order_by(ReviewerQueueORM.priority_score.desc())
            .limit(limit)
        ).all()

        result = []
        for q, p in rows:
            rec_a = db.get(CanonicalRecordORM, str(p.canonical_id_a))
            rec_b = db.get(CanonicalRecordORM, str(p.canonical_id_b))
            result.append({
                "queue_id": str(q.queue_id),
                "pair_id": str(p.pair_id),
                "priority_score": q.priority_score,
                "calibrated_probability": p.calibrated_probability,
                "feature_vector": p.feature_vector,
                "shap_contributions": p.shap_contributions,
                "shared_blocks": p.shared_blocks,
                "deterministic_tier_fired": p.deterministic_tier_fired,
                "record_a": _record_to_dict(rec_a),
                "record_b": _record_to_dict(rec_b),
            })
        return result


def queue_stats() -> dict:
    with get_db() as db:
        total = db.execute(select(func.count()).select_from(ReviewerQueueORM)).scalar()
        pending = db.execute(
            select(func.count()).select_from(ReviewerQueueORM)
            .where(ReviewerQueueORM.status == "pending")
        ).scalar()
        return {"total": total, "pending": pending, "decided": total - pending}


def _record_to_dict(rec: Optional[CanonicalRecordORM]) -> dict:
    if not rec:
        return {}
    return {
        "canonical_id": str(rec.canonical_id),
        "source_system": rec.source_system,
        "source_record_id": rec.source_record_id,
        "name_raw": rec.name_raw,
        "name_normalized": rec.name_normalized,
        "address_raw": rec.address_raw,
        "pin_code": rec.pin_code,
        "locality_canonical": rec.locality_canonical,
        "district": rec.district,
        "pan": rec.pan,
        "gstin": rec.gstin,
        "phone": rec.phone,
        "sector_raw": rec.sector_raw,
        "legal_form": rec.legal_form,
        "employee_count": rec.employee_count,
        "registration_date": str(rec.registration_date) if rec.registration_date else None,
    }
