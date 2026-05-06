"""Adapter for BESCOM electricity billing records.

BESCOM-specific challenges:
- Consumer name is often the property owner, not the operating business.
- PAN is absent.
- Three internal identifiers (RR Number, Account ID, K Number) that don't carry PAN.
- We flag high-risk records and use address-only matching with raised threshold.
"""
from __future__ import annotations
from typing import Any, Optional

from ubid.schema.canonical import CanonicalRecord, SourceSystem
from ubid.canonicalize import identifier_extractor
from ubid.ingest.base_adapter import BaseAdapter
from ubid.ingest.ekarmika_adapter import _parse_int

# Tariff categories that indicate a commercial/industrial connection
_BUSINESS_TARIFFS = {"lt-2", "lt-3", "lt-4", "ht-1", "ht-2", "ht-3", "ht-4"}

# Tariff categories that are likely domestic (exclude from entity resolution)
_DOMESTIC_TARIFFS = {"lt-1"}


class BESCOMAdapter(BaseAdapter):
    source_system = SourceSystem.BESCOM

    def adapt(self, row: dict[str, Any]) -> CanonicalRecord:
        consumer_name = str(row.get("consumer_name", "") or "").strip()
        raw_address = str(row.get("service_address", "") or row.get("address", "")).strip()

        name_norm, name_tokens, name_stripped = self._canonicalize_name(consumer_name)
        addr = self._parse_address(raw_address)
        locality_can = self._normalize_locality(addr.locality_raw)

        rr_number = _clean_rr(row.get("rr_number"))
        account_id = str(row.get("account_id", "") or "").strip() or None
        k_number = str(row.get("k_number", "") or row.get("consumer_number", "") or "").strip() or None

        tariff_raw = str(row.get("tariff_category", "") or "").strip()
        tariff_lower = tariff_raw.lower()

        # Flag records where consumer name is likely an individual (property owner)
        # Heuristic: name has no digits, no common business keywords, single-token names
        is_likely_individual = _looks_like_individual(consumer_name)

        load_kw: Optional[float] = None
        try:
            load_kw = float(row["sanctioned_load_kw"]) if row.get("sanctioned_load_kw") else None
        except (TypeError, ValueError):
            pass

        # Source record ID: prefer rr_number, fallback to account_id
        source_id = rr_number or account_id or k_number or str(row.get("id", ""))

        record = CanonicalRecord(
            source_system=SourceSystem.BESCOM,
            source_record_id=source_id,

            name_raw=consumer_name,
            name_normalized=name_norm,
            name_tokens=name_tokens,
            name_legal_form_stripped=name_stripped,

            address_raw=raw_address,
            pin_code=addr.pin_code,
            door_number=addr.door_number,
            street_raw=addr.street_raw,
            locality_raw=addr.locality_raw,
            locality_canonical=locality_can,
            taluk=addr.taluk,
            district=addr.district,

            # BESCOM has no PAN
            pan=None,
            gstin=None,

            phone=identifier_extractor.clean_phone(row.get("phone")),
            email=None,

            sector_raw=None,
            tariff_category=tariff_raw or None,
            sanctioned_load_kw=load_kw,

            rr_number=rr_number,
            account_id=account_id,
            k_number=k_number,
            bescom_consumer_name_risk=is_likely_individual,
        )
        return self._blocking_keys(record)


def _clean_rr(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    import re
    # Handle both legacy (MS3EH12345) and new (0123456789) formats
    cleaned = str(raw).strip().upper()
    # Strip brackets that appear in legacy-inside-new-format bills
    cleaned = re.sub(r"[\(\)\[\]]", "", cleaned).strip()
    return cleaned or None


def _looks_like_individual(name: str) -> bool:
    if not name:
        return False
    tokens = name.lower().split()
    business_keywords = {
        "pvt", "ltd", "limited", "industries", "traders", "enterprises",
        "company", "co", "llp", "manufacturing", "solutions", "services",
        "technologies", "tech", "infra", "construction",
    }
    has_business_keyword = any(t in business_keywords for t in tokens)
    has_digit = any(c.isdigit() for c in name)
    short_name = len(tokens) <= 2
    return not has_business_keyword and not has_digit and short_name
