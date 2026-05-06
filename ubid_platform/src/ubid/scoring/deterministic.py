"""Deterministic matching tier — high-precision rules that bypass the model.

Rules (in priority order):
1. Same non-null PAN, no conflicting signals → deterministic MATCH.
2. Different non-null PANs → deterministic NON-MATCH (hard reject).
3. Same PAN with 4th-char P (proprietorship) → soft-match (downgrade to probabilistic).
4. Same GSTIN → deterministic MATCH.
5. Different non-null GSTINs → deterministic NON-MATCH.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from ubid.schema.canonical import CanonicalRecord


@dataclass
class DeterministicResult:
    fired: bool
    is_match: Optional[bool]   # True=match, False=nonmatch, None=soft (route to model)
    reason: str
    probability: float         # 1.0 for hard match, 0.0 for hard nonmatch, 0.5 for soft


_NO_FIRE = DeterministicResult(fired=False, is_match=None, reason="", probability=-1.0)


def evaluate(a: CanonicalRecord, b: CanonicalRecord) -> DeterministicResult:
    """Apply deterministic rules to a candidate pair."""

    # ── PAN rules ─────────────────────────────────────────────────────────────
    if a.pan and b.pan:
        if a.pan == b.pan:
            # Same PAN — check entity type
            if a.pan_is_proprietorship or b.pan_is_proprietorship:
                # Proprietorship: one PAN → many establishments; route to address comparison
                return DeterministicResult(
                    fired=True,
                    is_match=None,
                    reason=f"Shared PAN {a.pan} is proprietorship type — soft match, address required",
                    probability=0.7,
                )
            # Non-proprietorship: same PAN = same legal entity → match if no hard conflict
            if _has_hard_address_conflict(a, b):
                return DeterministicResult(
                    fired=True,
                    is_match=None,
                    reason=f"Shared PAN {a.pan} but conflicting pin codes — soft match",
                    probability=0.6,
                )
            return DeterministicResult(
                fired=True,
                is_match=True,
                reason=f"Identical PAN {a.pan}, no conflicting fields",
                probability=1.0,
            )
        else:
            # Different non-null PANs → hard reject
            return DeterministicResult(
                fired=True,
                is_match=False,
                reason=f"Different PANs: {a.pan} vs {b.pan}",
                probability=0.0,
            )

    # ── GSTIN rules ───────────────────────────────────────────────────────────
    if a.gstin and b.gstin:
        if a.gstin == b.gstin:
            return DeterministicResult(
                fired=True,
                is_match=True,
                reason=f"Identical GSTIN {a.gstin}",
                probability=1.0,
            )
        # Different GSTINs might still share a PAN (multi-vertical) — soft, not hard reject
        pan_a = a.legal_entity_pan or a.pan
        pan_b = b.legal_entity_pan or b.pan
        if pan_a and pan_b and pan_a != pan_b:
            return DeterministicResult(
                fired=True,
                is_match=False,
                reason=f"Different embedded PANs from GSTINs: {pan_a} vs {pan_b}",
                probability=0.0,
            )

    # ── Derived-PAN rules (extracted from GSTIN) ─────────────────────────────
    if a.legal_entity_pan and b.legal_entity_pan:
        if a.legal_entity_pan == b.legal_entity_pan:
            if not a.pan_is_proprietorship and not b.pan_is_proprietorship:
                return DeterministicResult(
                    fired=True,
                    is_match=None,
                    reason=f"Shared legal-entity PAN {a.legal_entity_pan} from GSTIN — soft match",
                    probability=0.75,
                )
        elif a.legal_entity_pan != b.legal_entity_pan:
            return DeterministicResult(
                fired=True,
                is_match=False,
                reason=f"Different legal-entity PANs from GSTINs: {a.legal_entity_pan} vs {b.legal_entity_pan}",
                probability=0.0,
            )

    return _NO_FIRE


def _has_hard_address_conflict(a: CanonicalRecord, b: CanonicalRecord) -> bool:
    """True when both records have pin codes and they disagree."""
    if a.pin_code and b.pin_code:
        return a.pin_code != b.pin_code
    return False
