from sqlalchemy import (
    Boolean, Column, Date, DateTime, Double, Float, Integer,
    String, Text, ARRAY, JSON, ForeignKey, UniqueConstraint, Index,
    create_engine, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from typing import Generator
import logging

from ubid.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class CanonicalRecordORM(Base):
    __tablename__ = "canonical_records"

    canonical_id = Column(UUID(as_uuid=False), primary_key=True)
    ingested_at = Column(DateTime(timezone=True), nullable=False)
    source_system = Column(Text, nullable=False)
    source_record_id = Column(Text, nullable=False)
    source_schema_version = Column(Text, nullable=False, default="1.0")

    name_raw = Column(Text, nullable=False)
    name_normalized = Column(Text, nullable=False)
    name_tokens = Column(ARRAY(Text), nullable=False, default=list)
    name_legal_form_stripped = Column(Text, nullable=False, default="")

    address_raw = Column(Text, nullable=False, default="")
    pin_code = Column(Text)
    door_number = Column(Text)
    street_raw = Column(Text)
    locality_raw = Column(Text)
    locality_canonical = Column(Text)
    taluk = Column(Text)
    district = Column(Text)
    latitude = Column(Double)
    longitude = Column(Double)

    pan = Column(Text)
    pan_entity_type = Column(Text)
    pan_is_proprietorship = Column(Boolean, nullable=False, default=False)
    gstin = Column(Text)
    gstin_state_code = Column(Text)
    legal_entity_pan = Column(Text)
    pan_derived_from_gstin = Column(Boolean, nullable=False, default=False)
    cin = Column(Text)

    phone = Column(Text)
    email = Column(Text)
    email_domain = Column(Text)

    sector_raw = Column(Text)
    nic_code = Column(Text)
    kspcb_category = Column(Text)
    tariff_category = Column(Text)

    legal_form = Column(Text)
    employee_count = Column(Integer)
    sanctioned_load_kw = Column(Double)
    registration_date = Column(Date)

    rr_number = Column(Text)
    account_id = Column(Text)
    k_number = Column(Text)
    bescom_consumer_name_risk = Column(Boolean, nullable=False, default=False)

    consent_valid_until = Column(Date)
    licence_valid_until = Column(Date)

    blocking_name_prefix4 = Column(Text, nullable=False, default="")
    blocking_pin_name = Column(Text, nullable=False, default="")
    blocking_pin_door = Column(Text, nullable=False, default="")

    __table_args__ = (UniqueConstraint("source_system", "source_record_id"),)


class LegalEntityORM(Base):
    __tablename__ = "legal_entities"

    legal_entity_id = Column(UUID(as_uuid=False), primary_key=True)
    pan = Column(Text, unique=True)
    name_canonical = Column(Text)
    legal_form = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class UBIDNodeORM(Base):
    __tablename__ = "ubid_nodes"

    ubid = Column(UUID(as_uuid=False), primary_key=True)
    legal_entity_id = Column(UUID(as_uuid=False), ForeignKey("legal_entities.legal_entity_id"))
    pin_code = Column(Text)
    district = Column(Text)
    sector_canonical = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    cluster_version = Column(Integer, nullable=False, default=1)


class UBIDSourceLinkORM(Base):
    __tablename__ = "ubid_source_links"

    link_id = Column(UUID(as_uuid=False), primary_key=True)
    ubid = Column(UUID(as_uuid=False), ForeignKey("ubid_nodes.ubid"), nullable=False)
    canonical_id = Column(UUID(as_uuid=False), ForeignKey("canonical_records.canonical_id"), nullable=False)
    linked_at = Column(DateTime(timezone=True), nullable=False)
    linked_by = Column(Text, nullable=False, default="auto")
    confidence = Column(Double)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("ubid", "canonical_id"),)


class LinkagePairORM(Base):
    __tablename__ = "linkage_pairs"

    pair_id = Column(UUID(as_uuid=False), primary_key=True)
    canonical_id_a = Column(UUID(as_uuid=False), ForeignKey("canonical_records.canonical_id"), nullable=False)
    canonical_id_b = Column(UUID(as_uuid=False), ForeignKey("canonical_records.canonical_id"), nullable=False)
    raw_score = Column(Double, nullable=False)
    calibrated_probability = Column(Double, nullable=False)
    deterministic_tier_fired = Column(Boolean, nullable=False, default=False)
    deterministic_result = Column(Boolean)
    feature_vector = Column(JSONB, nullable=False, default=dict)
    shap_contributions = Column(JSONB, nullable=False, default=dict)
    shared_blocks = Column(ARRAY(Text), nullable=False, default=list)
    scored_at = Column(DateTime(timezone=True), nullable=False)
    decision = Column(Text)
    decided_at = Column(DateTime(timezone=True))
    decided_by = Column(Text)

    __table_args__ = (UniqueConstraint("canonical_id_a", "canonical_id_b"),)


class LinkageConstraintORM(Base):
    __tablename__ = "linkage_constraints"

    constraint_id = Column(UUID(as_uuid=False), primary_key=True)
    canonical_id_a = Column(UUID(as_uuid=False), ForeignKey("canonical_records.canonical_id"), nullable=False)
    canonical_id_b = Column(UUID(as_uuid=False), ForeignKey("canonical_records.canonical_id"), nullable=False)
    constraint_type = Column(Text, nullable=False)
    created_by = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text)

    __table_args__ = (UniqueConstraint("canonical_id_a", "canonical_id_b"),)


class ActivityEventORM(Base):
    __tablename__ = "activity_events"

    event_id = Column(UUID(as_uuid=False), primary_key=True)
    ubid = Column(UUID(as_uuid=False), ForeignKey("ubid_nodes.ubid"))
    canonical_id = Column(UUID(as_uuid=False), ForeignKey("canonical_records.canonical_id"))
    source_system = Column(Text, nullable=False)
    source_record_id = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)
    event_date = Column(Date, nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False)
    # 'metadata' is reserved by SQLAlchemy DeclarativeBase — use column alias
    event_metadata = Column("metadata", JSONB, nullable=False, default=dict)


class ActivityVerdictORM(Base):
    __tablename__ = "activity_verdicts"

    verdict_id = Column(UUID(as_uuid=False), primary_key=True)
    ubid = Column(UUID(as_uuid=False), ForeignKey("ubid_nodes.ubid"), nullable=False, unique=True)
    verdict = Column(Text, nullable=False)
    continuity_score = Column(Double, nullable=False)
    evidence_timeline = Column(JSONB, nullable=False, default=list)
    deterministic_overrides = Column(JSONB, nullable=False, default=list)
    sector_prior_applied = Column(Boolean, nullable=False, default=False)
    computed_at = Column(DateTime(timezone=True), nullable=False)


class QuarantineEventORM(Base):
    __tablename__ = "quarantine_events"

    event_id = Column(UUID(as_uuid=False), primary_key=True)
    source_system = Column(Text, nullable=False)
    source_record_id = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)
    event_date = Column(Date, nullable=False)
    quarantined_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(Text, nullable=False)
    event_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    retry_count = Column(Integer, nullable=False, default=0)
    last_retry_at = Column(DateTime(timezone=True))
    resolved = Column(Boolean, nullable=False, default=False)
    resolved_ubid = Column(UUID(as_uuid=False))
    resolved_at = Column(DateTime(timezone=True))


class ReviewerQueueORM(Base):
    __tablename__ = "reviewer_queue"

    queue_id = Column(UUID(as_uuid=False), primary_key=True)
    pair_id = Column(UUID(as_uuid=False), ForeignKey("linkage_pairs.pair_id"), nullable=False)
    priority_score = Column(Double, nullable=False, default=0.0)
    assigned_to = Column(Text)
    status = Column(Text, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class ReviewerDecisionORM(Base):
    __tablename__ = "reviewer_decisions"

    decision_id = Column(UUID(as_uuid=False), primary_key=True)
    queue_id = Column(UUID(as_uuid=False), ForeignKey("reviewer_queue.queue_id"))
    pair_id = Column(UUID(as_uuid=False), ForeignKey("linkage_pairs.pair_id"), nullable=False)
    canonical_id_a = Column(UUID(as_uuid=False), nullable=False)
    canonical_id_b = Column(UUID(as_uuid=False), nullable=False)
    decision = Column(Text, nullable=False)
    reviewer_id = Column(Text, nullable=False)
    reviewer_tier = Column(Text, nullable=False, default="junior")
    notes = Column(Text)
    decided_at = Column(DateTime(timezone=True), nullable=False)
    is_training_label = Column(Boolean, nullable=False, default=True)


class TrainingLabelORM(Base):
    __tablename__ = "training_labels"

    label_id = Column(UUID(as_uuid=False), primary_key=True)
    canonical_id_a = Column(UUID(as_uuid=False), nullable=False)
    canonical_id_b = Column(UUID(as_uuid=False), nullable=False)
    is_match = Column(Boolean, nullable=False)
    source = Column(Text, nullable=False, default="reviewer")
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("canonical_id_a", "canonical_id_b"),)


# ── Engine and session factory ────────────────────────────────────────────────

_engine = None
_SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory


@contextmanager
def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables():
    """Create all tables if they don't exist (idempotent)."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables ensured.")
