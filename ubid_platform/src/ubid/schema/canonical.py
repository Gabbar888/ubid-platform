from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class SourceSystem(str, Enum):
    EKARMIKA = "ekarmika"
    FBIS = "fbis"
    KSPCB = "kspcb"
    BESCOM = "bescom"


class LegalForm(str, Enum):
    PROPRIETORSHIP = "proprietorship"
    PARTNERSHIP = "partnership"
    PVT_LTD = "pvt_ltd"
    PUBLIC_LTD = "public_ltd"
    LLP = "llp"
    HUF = "huf"
    TRUST = "trust"
    COOPERATIVE = "cooperative"
    GOVERNMENT = "government"
    OTHER = "other"


class KSPCBCategory(str, Enum):
    RED = "red"
    ORANGE = "orange"
    GREEN = "green"
    WHITE = "white"


class CanonicalRecord(BaseModel):
    """Normalized projection of a source-system record. Immutable once created."""

    # Internal identifiers
    canonical_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

    # Source provenance
    source_system: SourceSystem
    source_record_id: str
    source_schema_version: str = "1.0"

    # ── Business name ──────────────────────────────────────────────────────────
    name_raw: str
    name_normalized: str
    name_tokens: list[str] = Field(default_factory=list)
    name_legal_form_stripped: str = ""

    # ── Address ───────────────────────────────────────────────────────────────
    address_raw: str = ""
    pin_code: Optional[str] = None
    door_number: Optional[str] = None
    street_raw: Optional[str] = None
    locality_raw: Optional[str] = None
    locality_canonical: Optional[str] = None
    taluk: Optional[str] = None
    district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # ── Identifiers ───────────────────────────────────────────────────────────
    pan: Optional[str] = None
    pan_entity_type: Optional[str] = None          # 4th character of PAN
    pan_is_proprietorship: bool = False             # True when pan_entity_type == "P"
    gstin: Optional[str] = None
    gstin_state_code: Optional[str] = None
    legal_entity_pan: Optional[str] = None         # Extracted from GSTIN chars 3–12
    pan_derived_from_gstin: bool = False
    cin: Optional[str] = None

    # ── Contact ───────────────────────────────────────────────────────────────
    phone: Optional[str] = None
    email: Optional[str] = None
    email_domain: Optional[str] = None

    # ── Sector ────────────────────────────────────────────────────────────────
    sector_raw: Optional[str] = None
    nic_code: Optional[str] = None
    kspcb_category: Optional[KSPCBCategory] = None
    tariff_category: Optional[str] = None          # BESCOM tariff (LT-2, LT-3, HT-1 …)

    # ── Structural ────────────────────────────────────────────────────────────
    legal_form: Optional[LegalForm] = None
    employee_count: Optional[int] = None
    sanctioned_load_kw: Optional[float] = None
    registration_date: Optional[date] = None

    # ── BESCOM-specific ───────────────────────────────────────────────────────
    rr_number: Optional[str] = None
    account_id: Optional[str] = None
    k_number: Optional[str] = None
    bescom_consumer_name_risk: bool = False         # True when name likely a property owner

    # ── KSPCB-specific ────────────────────────────────────────────────────────
    consent_valid_until: Optional[date] = None

    # ── FBIS-specific ─────────────────────────────────────────────────────────
    licence_valid_until: Optional[date] = None

    # ── Blocking keys (pre-computed) ──────────────────────────────────────────
    blocking_name_prefix4: str = ""                # first 4 chars of name_normalized
    blocking_pin_name: str = ""                    # "{pin_code}|{name_prefix4}"
    blocking_pin_door: str = ""                    # "{pin_code}|{door_number}"


class LinkageDecisionType(str, Enum):
    AUTO_LINK = "auto_link"
    AUTO_REJECT = "auto_reject"
    REVIEWER_CONFIRM = "reviewer_confirm"
    REVIEWER_REJECT = "reviewer_reject"
    DETERMINISTIC_MATCH = "deterministic_match"
    DETERMINISTIC_NONMATCH = "deterministic_nonmatch"


class ConstraintType(str, Enum):
    MUST_LINK = "must_link"
    CANNOT_LINK = "cannot_link"


class ScoredPair(BaseModel):
    canonical_id_a: str
    canonical_id_b: str
    raw_score: float
    calibrated_probability: float
    deterministic_tier_fired: bool
    deterministic_result: Optional[bool] = None  # True=match, False=nonmatch
    feature_vector: dict[str, float] = Field(default_factory=dict)
    shap_contributions: dict[str, float] = Field(default_factory=dict)
    shared_blocks: list[str] = Field(default_factory=list)
    scored_at: datetime = Field(default_factory=datetime.utcnow)


class VerdictLabel(str, Enum):
    NASCENT = "nascent"
    ACTIVE = "active"
    DORMANT = "dormant"
    CLOSED = "closed"
    CLOSED_BY_SILENCE = "closed_by_silence"
