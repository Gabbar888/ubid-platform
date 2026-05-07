from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid

from ubid.schema.canonical import SourceSystem


class EventType(str, Enum):
    # Shop & Establishment events
    SE_RENEWAL_PRE2019 = "se_renewal_pre2019"
    SE_SELFCERT_POST2019 = "se_selfcert_post2019"
    SE_CLOSURE = "se_closure"
    SE_AMENDMENT = "se_amendment"

    # Factories / FBIS events
    FAC_FORM20_ANNUAL = "fac_form20_annual"
    FAC_FORM21_HALFYEARLY = "fac_form21_halfyearly"
    FAC_LICENSE_RENEWAL = "fac_license_renewal"
    FAC_INSPECTION = "fac_inspection"
    FAC_ACCIDENT = "fac_accident"
    FAC_DELICENSED = "fac_delicensed"

    # KSPCB events
    KSPCB_CFO_RENEWAL = "kspcb_cfo_renewal"
    KSPCB_COMPLIANCE_REPORT = "kspcb_compliance_report"
    KSPCB_CONSENT_REVOKED = "kspcb_consent_revoked"
    KSPCB_CCA_ISSUED = "kspcb_cca_issued"

    # BESCOM events
    BESCOM_BILL_GENERATED = "bescom_bill_generated"
    BESCOM_BILL_PAID = "bescom_bill_paid"
    BESCOM_ZERO_CONSUMPTION = "bescom_zero_consumption"
    BESCOM_DISCONNECT = "bescom_disconnect"
    BESCOM_RECONNECT = "bescom_reconnect"
    BESCOM_TARIFF_CHANGE = "bescom_tariff_change"

    # BWSSB events (water supply)
    BWSSB_BILL_GENERATED = "bwssb_bill_generated"
    BWSSB_BILL_PAID = "bwssb_bill_paid"
    BWSSB_ZERO_CONSUMPTION = "bwssb_zero_consumption"
    BWSSB_DISCONNECT = "bwssb_disconnect"
    BWSSB_RECONNECT = "bwssb_reconnect"


class ActivityEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_system: SourceSystem
    source_record_id: str
    event_type: EventType
    event_date: date
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    ubid: Optional[str] = None
    canonical_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuarantinedEvent(BaseModel):
    """Event that could not be joined to a UBID at ingestion time."""
    event_id: str
    source_system: SourceSystem
    source_record_id: str
    event_type: EventType
    event_date: date
    quarantined_at: datetime = Field(default_factory=datetime.utcnow)
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    last_retry_at: Optional[datetime] = None
    resolved: bool = False
    resolved_ubid: Optional[str] = None
    resolved_at: Optional[datetime] = None
