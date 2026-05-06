"""Shared fixtures for unit tests."""
import pytest
from datetime import date
from ubid.schema.canonical import CanonicalRecord, SourceSystem
from ubid.schema.events import ActivityEvent, EventType


@pytest.fixture
def se_record():
    return CanonicalRecord(
        source_system=SourceSystem.EKARMIKA,
        source_record_id="SE-560058-001",
        name_raw="Sharma Traders Pvt Ltd",
        name_normalized="sharma traders pvt ltd",
        name_tokens=["sharma", "traders", "pvt", "ltd"],
        name_legal_form_stripped="sharma traders",
        address_raw="No. 12, 3rd Cross, Peenya 2nd Stage, Bengaluru 560058",
        pin_code="560058",
        door_number="12",
        locality_raw="Peenya 2nd Stage",
        locality_canonical="peenya industrial area phase 2",
        pan="ABCDE1234F",
        pan_entity_type="company",
        gstin="29ABCDE1234F1Z5",
        legal_entity_pan="ABCDE1234F",
        blocking_name_prefix4="shar",
        blocking_pin_name="560058|shar",
    )


@pytest.fixture
def fbis_record_same_entity():
    """Factory record for the same entity as se_record."""
    return CanonicalRecord(
        source_system=SourceSystem.FBIS,
        source_record_id="FAC-KA-001234",
        name_raw="Sharma Traders (P) Ltd",
        name_normalized="sharma traders p ltd",
        name_tokens=["sharma", "traders", "p", "ltd"],
        name_legal_form_stripped="sharma traders",
        address_raw="Plot 12, Peenya Industrial Area Phase 2, Bengaluru 560058",
        pin_code="560058",
        door_number="12",
        locality_raw="Peenya Industrial Area Phase 2",
        locality_canonical="peenya industrial area phase 2",
        pan="ABCDE1234F",
        pan_entity_type="company",
        legal_entity_pan="ABCDE1234F",
        blocking_name_prefix4="shar",
        blocking_pin_name="560058|shar",
    )


@pytest.fixture
def different_entity_record():
    """A completely different business."""
    return CanonicalRecord(
        source_system=SourceSystem.KSPCB,
        source_record_id="KSPCB-BNG-9999",
        name_raw="Patel Chemicals Pvt Ltd",
        name_normalized="patel chemicals pvt ltd",
        name_tokens=["patel", "chemicals", "pvt", "ltd"],
        name_legal_form_stripped="patel chemicals",
        address_raw="Site 45, Bommasandra Industrial Area, Bengaluru 560099",
        pin_code="560099",
        pan="ZYXWV9876K",
        pan_entity_type="company",
        blocking_name_prefix4="pate",
        blocking_pin_name="560099|pate",
    )


@pytest.fixture
def sample_events():
    return [
        ActivityEvent(
            event_id="evt-001",
            source_system=SourceSystem.FBIS,
            source_record_id="FAC-KA-001234",
            event_type=EventType.FAC_FORM20_ANNUAL,
            event_date=date(2024, 2, 1),
            ubid="test-ubid-001",
        ),
        ActivityEvent(
            event_id="evt-002",
            source_system=SourceSystem.BESCOM,
            source_record_id="RR-1234567890",
            event_type=EventType.BESCOM_BILL_PAID,
            event_date=date(2025, 3, 15),
            ubid="test-ubid-001",
        ),
        ActivityEvent(
            event_id="evt-003",
            source_system=SourceSystem.KSPCB,
            source_record_id="KSPCB-BNG-001",
            event_type=EventType.KSPCB_CFO_RENEWAL,
            event_date=date(2024, 8, 1),
            ubid="test-ubid-001",
        ),
    ]
