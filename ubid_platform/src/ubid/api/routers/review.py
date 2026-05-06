"""Reviewer console API."""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ubid.review.queue import get_pending_items, queue_stats
from ubid.review.feedback import apply_decision
from ubid.activity.quarantine import get_quarantine_stats
from ubid.canonicalize.locality_normalizer import add_synonym

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/queue")
def get_review_queue(limit: int = 20):
    """Get top-priority items pending review."""
    return {
        "items": get_pending_items(limit=limit),
        "stats": queue_stats(),
    }


@router.get("/stats")
def get_stats():
    return {
        "queue": queue_stats(),
        "quarantine": get_quarantine_stats(),
    }


class DecisionRequest(BaseModel):
    queue_id: Optional[str] = None
    pair_id: str
    canonical_id_a: str
    canonical_id_b: str
    decision: str  # confirm_match | reject | defer | flag_quality
    reviewer_id: str
    reviewer_tier: str = "junior"
    notes: Optional[str] = None


@router.post("/decide")
def submit_decision(body: DecisionRequest):
    valid = {"confirm_match", "reject", "defer", "flag_quality"}
    if body.decision not in valid:
        raise HTTPException(400, f"Decision must be one of {valid}")

    apply_decision(body.model_dump())

    # Publish to Kafka for async processing
    try:
        from ubid.kafka.producer import publish_review_decision
        publish_review_decision(body.model_dump())
    except Exception as e:
        logger.warning("Kafka publish skipped: %s", e)

    return {"status": "accepted", "decision": body.decision}


class SynonymRequest(BaseModel):
    variant: str
    canonical: str
    reviewer_id: str


@router.post("/synonyms")
def add_locality_synonym(body: SynonymRequest):
    """Add a locality synonym discovered during review."""
    add_synonym(body.variant, body.canonical)
    return {"status": "added", "variant": body.variant, "canonical": body.canonical}
