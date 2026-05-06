"""Activity signal catalog — exactly Table 2 from the proposal.

Each entry defines:
  weight (wT)       — continuity contribution per occurrence
  cadence_days (τT) — expected inter-event gap in days
  sign              — +1 (positive evidence), -1 (negative evidence)
  terminal          — True = deterministic override (Closed/Disconnect)
  terminal_verdict  — which VerdictLabel to force
  ambiguous         — True = state-driven event, not business-driven
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from ubid.schema.events import EventType
from ubid.schema.canonical import VerdictLabel


@dataclass(frozen=True)
class SignalConfig:
    weight: float
    cadence_days: Optional[int]   # None = event-driven, no regular cadence
    sign: int                     # +1 or -1
    terminal: bool = False
    terminal_verdict: Optional[VerdictLabel] = None
    ambiguous: bool = False       # state-driven signal, lower trust


SIGNAL_CATALOG: dict[EventType, SignalConfig] = {
    # ── Shop & Establishment ──────────────────────────────────────────────────
    EventType.SE_RENEWAL_PRE2019: SignalConfig(
        weight=0.7, cadence_days=1825, sign=+1,
    ),
    EventType.SE_SELFCERT_POST2019: SignalConfig(
        weight=0.3, cadence_days=365, sign=+1,
    ),
    EventType.SE_CLOSURE: SignalConfig(
        weight=1.0, cadence_days=None, sign=+1,
        terminal=True, terminal_verdict=VerdictLabel.CLOSED,
    ),
    EventType.SE_AMENDMENT: SignalConfig(
        weight=0.4, cadence_days=None, sign=+1,
    ),

    # ── Factories / FBIS ──────────────────────────────────────────────────────
    EventType.FAC_FORM20_ANNUAL: SignalConfig(
        weight=0.8, cadence_days=365, sign=+1,
    ),
    EventType.FAC_FORM21_HALFYEARLY: SignalConfig(
        weight=0.7, cadence_days=183, sign=+1,
    ),
    EventType.FAC_LICENSE_RENEWAL: SignalConfig(
        weight=0.9, cadence_days=None, sign=+1,
    ),
    EventType.FAC_INSPECTION: SignalConfig(
        weight=0.4, cadence_days=None, sign=+1, ambiguous=True,
    ),
    EventType.FAC_ACCIDENT: SignalConfig(
        weight=0.3, cadence_days=None, sign=+1, ambiguous=True,
    ),
    EventType.FAC_DELICENSED: SignalConfig(
        weight=1.0, cadence_days=None, sign=+1,
        terminal=True, terminal_verdict=VerdictLabel.CLOSED,
    ),

    # ── KSPCB ─────────────────────────────────────────────────────────────────
    EventType.KSPCB_CFO_RENEWAL: SignalConfig(
        weight=0.9, cadence_days=None, sign=+1,
    ),
    EventType.KSPCB_COMPLIANCE_REPORT: SignalConfig(
        weight=0.6, cadence_days=180, sign=+1,
    ),
    EventType.KSPCB_CONSENT_REVOKED: SignalConfig(
        weight=1.0, cadence_days=None, sign=+1,
        terminal=True, terminal_verdict=VerdictLabel.CLOSED,
    ),
    EventType.KSPCB_CCA_ISSUED: SignalConfig(
        weight=0.8, cadence_days=None, sign=+1,
    ),

    # ── BESCOM ────────────────────────────────────────────────────────────────
    EventType.BESCOM_BILL_GENERATED: SignalConfig(
        weight=0.5, cadence_days=30, sign=+1,
    ),
    EventType.BESCOM_BILL_PAID: SignalConfig(
        weight=0.9, cadence_days=30, sign=+1,
    ),
    EventType.BESCOM_ZERO_CONSUMPTION: SignalConfig(
        weight=0.4, cadence_days=30, sign=-1,
    ),
    EventType.BESCOM_DISCONNECT: SignalConfig(
        weight=0.9, cadence_days=None, sign=-1,
        terminal=False,  # reversible on reconnect
    ),
    EventType.BESCOM_RECONNECT: SignalConfig(
        weight=0.9, cadence_days=None, sign=+1,
    ),
    EventType.BESCOM_TARIFF_CHANGE: SignalConfig(
        weight=0.3, cadence_days=None, sign=+1, ambiguous=True,
    ),
}
