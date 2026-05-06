"""Activity verdict engine.

Three-stage verdict (from proposal):
  1. Deterministic overrides — closure/revocation events force CLOSED regardless of score.
  2. Rule-bounded thresholding — continuity score → Active / Dormant / Closed-by-silence.
  3. Sector-aware adjustment — seasonal sectors widen Dormant band.
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from ubid.activity.signal_catalog import SIGNAL_CATALOG, SignalConfig
from ubid.activity.decay import contribution
from ubid.config import get_settings
from ubid.schema.canonical import VerdictLabel
from ubid.schema.events import ActivityEvent, EventType

logger = logging.getLogger(__name__)

_DICT_DIR = Path(__file__).parent.parent.parent.parent / "data" / "dictionaries"
with open(_DICT_DIR / "sector_priors.json", encoding="utf-8") as f:
    _SECTOR_PRIORS = json.load(f)


@dataclass
class EvidenceEntry:
    event_id: str
    event_type: str
    event_date: str
    source_system: str
    weight: float
    sign: int
    decayed_contribution: float
    days_ago: int


@dataclass
class VerdictResult:
    ubid: str
    verdict: VerdictLabel
    continuity_score: float
    evidence_timeline: list[EvidenceEntry] = field(default_factory=list)
    deterministic_overrides: list[str] = field(default_factory=list)
    sector_prior_applied: bool = False
    computed_at: datetime = field(default_factory=datetime.utcnow)


def compute_verdict(
    ubid: str,
    events: list[ActivityEvent],
    registration_date: Optional[date] = None,
    sector: Optional[str] = None,
    reference_date: Optional[date] = None,
) -> VerdictResult:
    settings = get_settings()
    ref = reference_date or date.today()
    alpha = settings.activity_alpha

    evidence: list[EvidenceEntry] = []
    overrides: list[str] = []

    # ── Stage 1: Deterministic overrides ─────────────────────────────────────
    for evt in events:
        cfg = SIGNAL_CATALOG.get(evt.event_type)
        if cfg and cfg.terminal:
            overrides.append(
                f"{evt.event_type} on {evt.event_date} → {cfg.terminal_verdict}"
            )
            return VerdictResult(
                ubid=ubid,
                verdict=cfg.terminal_verdict or VerdictLabel.CLOSED,
                continuity_score=0.0,
                evidence_timeline=_build_evidence(events, ref, alpha),
                deterministic_overrides=overrides,
            )

    # ── Nascent: only a registration event and within hold period ─────────────
    if registration_date:
        days_since_reg = (ref - registration_date).days
        has_activity = any(
            e for e in events if e.event_type not in (
                EventType.SE_AMENDMENT,
            )
        )
        if not has_activity and days_since_reg <= settings.nascent_hold_days:
            return VerdictResult(
                ubid=ubid,
                verdict=VerdictLabel.NASCENT,
                continuity_score=0.0,
                evidence_timeline=[],
                deterministic_overrides=["No activity events within nascent hold period"],
            )

    # ── Stage 2: Compute continuity score ────────────────────────────────────
    total_score = 0.0
    for evt in events:
        cfg = SIGNAL_CATALOG.get(evt.event_type)
        if not cfg or cfg.terminal:
            continue
        c = contribution(cfg, evt.event_date, ref, alpha)
        total_score += c
        days_ago = (ref - evt.event_date).days
        evidence.append(EvidenceEntry(
            event_id=evt.event_id,
            event_type=evt.event_type,
            event_date=str(evt.event_date),
            source_system=evt.source_system,
            weight=cfg.weight,
            sign=cfg.sign,
            decayed_contribution=round(c, 4),
            days_ago=days_ago,
        ))

    # Sort evidence by event_date descending
    evidence.sort(key=lambda e: e.event_date, reverse=True)

    # ── Stage 3: Sector-aware adjustment ─────────────────────────────────────
    sector_prior_applied = False
    active_thresh = settings.active_score_threshold
    dormant_thresh = settings.dormant_score_threshold

    sector_cfg = _get_sector_prior(sector)
    if sector_cfg.get("seasonal"):
        dormant_thresh *= sector_cfg.get("dormant_multiplier", 2.0)
        sector_prior_applied = True

    if total_score >= active_thresh:
        verdict = VerdictLabel.ACTIVE
    elif total_score >= dormant_thresh:
        verdict = VerdictLabel.DORMANT
    elif total_score > 0:
        verdict = VerdictLabel.CLOSED_BY_SILENCE
    else:
        verdict = VerdictLabel.CLOSED_BY_SILENCE

    return VerdictResult(
        ubid=ubid,
        verdict=verdict,
        continuity_score=round(total_score, 4),
        evidence_timeline=evidence,
        deterministic_overrides=overrides,
        sector_prior_applied=sector_prior_applied,
    )


def _build_evidence(events: list[ActivityEvent], ref: date, alpha: float) -> list[EvidenceEntry]:
    result = []
    for evt in events:
        cfg = SIGNAL_CATALOG.get(evt.event_type)
        if not cfg:
            continue
        c = contribution(cfg, evt.event_date, ref, alpha)
        result.append(EvidenceEntry(
            event_id=evt.event_id,
            event_type=evt.event_type,
            event_date=str(evt.event_date),
            source_system=evt.source_system,
            weight=cfg.weight,
            sign=cfg.sign,
            decayed_contribution=round(c, 4),
            days_ago=(ref - evt.event_date).days,
        ))
    return result


def _get_sector_prior(sector: Optional[str]) -> dict:
    if not sector:
        return _SECTOR_PRIORS.get("defaults", {})
    sector_lower = sector.lower()
    for key, cfg in _SECTOR_PRIORS.get("sectors", {}).items():
        keywords = cfg.get("keywords", [])
        if any(kw in sector_lower for kw in keywords):
            return cfg
    return _SECTOR_PRIORS.get("defaults", {})
