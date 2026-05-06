"""Tests for activity verdict engine."""
import pytest
from datetime import date
from ubid.activity.verdict import compute_verdict
from ubid.activity.decay import contribution
from ubid.activity.signal_catalog import SIGNAL_CATALOG
from ubid.schema.canonical import VerdictLabel
from ubid.schema.events import EventType, ActivityEvent
from ubid.schema.canonical import SourceSystem


class TestDecay:
    def test_recent_event_high_contribution(self):
        cfg = SIGNAL_CATALOG[EventType.BESCOM_BILL_PAID]
        c = contribution(cfg, date(2025, 5, 1), date(2025, 5, 5), alpha=1.5)
        assert c > 0.8  # almost no decay for 4-day-old event

    def test_old_event_low_contribution(self):
        cfg = SIGNAL_CATALOG[EventType.BESCOM_BILL_PAID]
        # Bill not paid for 6 months — τ=30 days
        c = contribution(cfg, date(2024, 11, 1), date(2025, 5, 5), alpha=1.5)
        assert c < 0.01

    def test_negative_signal_reduces_score(self):
        cfg = SIGNAL_CATALOG[EventType.BESCOM_ZERO_CONSUMPTION]
        c = contribution(cfg, date(2025, 5, 1), date(2025, 5, 5), alpha=1.5)
        assert c < 0  # sign=-1

    def test_terminal_signal_full_weight(self):
        cfg = SIGNAL_CATALOG[EventType.SE_CLOSURE]
        c = contribution(cfg, date(2020, 1, 1), date(2025, 5, 5), alpha=1.5)
        assert c == cfg.weight  # terminal signals don't decay


class TestVerdictEngine:
    def test_active_verdict_with_recent_events(self, sample_events):
        result = compute_verdict("test-ubid", sample_events, reference_date=date(2025, 5, 5))
        assert result.verdict in (VerdictLabel.ACTIVE, VerdictLabel.DORMANT)
        assert result.continuity_score > 0

    def test_closed_on_closure_event(self):
        events = [ActivityEvent(
            event_id="ev1",
            source_system=SourceSystem.EKARMIKA,
            source_record_id="SE-001",
            event_type=EventType.SE_CLOSURE,
            event_date=date(2023, 6, 1),
            ubid="test-ubid",
        )]
        result = compute_verdict("test-ubid", events, reference_date=date(2025, 5, 5))
        assert result.verdict == VerdictLabel.CLOSED
        assert len(result.deterministic_overrides) > 0

    def test_nascent_for_new_ubid(self):
        result = compute_verdict(
            "new-ubid",
            events=[],
            registration_date=date(2025, 4, 1),
            reference_date=date(2025, 5, 5),
        )
        assert result.verdict == VerdictLabel.NASCENT

    def test_dormant_for_old_bescom_only(self):
        events = [ActivityEvent(
            event_id="ev1",
            source_system=SourceSystem.BESCOM,
            source_record_id="RR-001",
            event_type=EventType.BESCOM_BILL_PAID,
            event_date=date(2024, 11, 1),  # 6 months ago
            ubid="test-ubid",
        )]
        result = compute_verdict("test-ubid", events, reference_date=date(2025, 5, 5))
        # Single old BESCOM payment only — should be Dormant or Closed-by-silence, not Active
        assert result.verdict in (VerdictLabel.DORMANT, VerdictLabel.CLOSED_BY_SILENCE)

    def test_evidence_timeline_populated(self, sample_events):
        result = compute_verdict("test-ubid", sample_events, reference_date=date(2025, 5, 5))
        assert len(result.evidence_timeline) > 0
        for entry in result.evidence_timeline:
            assert entry.event_type is not None
            assert entry.days_ago >= 0
