"""Adapter for BWSSB (Bangalore Water Supply & Sewerage Board) records.

BWSSB-specific characteristics:
- KNCA Number (Karnataka Nagara Connection Account) is the persistent
  connection identifier — analogous to BESCOM's RR Number.
- Like BESCOM, the consumer name on a water connection is often the
  property owner (landlord) rather than the operating business.
- Connection size in mm (15 / 20 / 25 / 50 / 100) indicates load —
  industrial connections are 25 mm+.
- No PAN / GSTIN. Linkage relies on address + (occasionally) phone.

We deliberately mirror the BESCOM adapter's data model. Both are
infrastructure-level utility records; both share the address-only
matching constraint and the consumer-name-may-be-landlord risk flag.
"""
from __future__ import annotations
from typing import Any, Optional

from ubid.schema.canonical import CanonicalRecord, SourceSystem
from ubid.canonicalize import identifier_extractor
from ubid.ingest.base_adapter import BaseAdapter

# Connection sizes that indicate commercial / industrial use (in mm)
_BUSINESS_CONNECTION_SIZES = {25, 32, 40, 50, 75, 100, 150, 200}


class BWSSBAdapter(BaseAdapter):
    source_system = SourceSystem.BWSSB

    def adapt(self, row: dict[str, Any]) -> CanonicalRecord:
        consumer_name = str(row.get("consumer_name", "") or "").strip()
        raw_address = str(
            row.get("service_address", "") or row.get("address", "")
        ).strip()

        name_norm, name_tokens, name_stripped = self._canonicalize_name(consumer_name)
        addr = self._parse_address(raw_address)
        locality_can = self._normalize_locality(addr.locality_raw)

        knca_number = _clean_id(row.get("knca_number") or row.get("connection_number"))
        account_id = str(row.get("account_id", "") or "").strip() or None
        consumer_number = (
            str(row.get("consumer_number", "") or "").strip() or None
        )

        # Connection size in mm — drives the "is this a business connection?" flag
        connection_size_mm: Optional[int] = None
        try:
            v = row.get("connection_size_mm") or row.get("size_mm")
            if v not in (None, ""):
                connection_size_mm = int(float(v))
        except (TypeError, ValueError):
            pass

        tariff_raw = str(row.get("tariff_category", "") or "").strip()

        # Apply the same "consumer name may be landlord" heuristic as BESCOM —
        # water and electricity bills both tend to be in the property owner's
        # name regardless of who's actually operating the business.
        is_likely_individual = _looks_like_individual(consumer_name)

        # Source record ID: prefer KNCA, fallback to account / consumer
        source_id = knca_number or account_id or consumer_number or str(row.get("id", ""))

        record = CanonicalRecord(
            source_system=SourceSystem.BWSSB,
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

            # BWSSB has no PAN/GSTIN — same constraint as BESCOM
            pan=None,
            gstin=None,

            phone=identifier_extractor.clean_phone(row.get("phone")),
            email=None,

            sector_raw=None,
            tariff_category=tariff_raw or None,
            # Reuse sanctioned_load_kw to carry the connection size for now;
            # the scorer's struct_employee_ratio_log doesn't depend on it.
            sanctioned_load_kw=float(connection_size_mm) if connection_size_mm else None,

            # Reuse the BESCOM-style identifier slots — semantically these are
            # connection-level identifiers and the underlying scorer features
            # don't care about the source system, only the value.
            rr_number=knca_number,
            account_id=account_id,
            k_number=consumer_number,
            bescom_consumer_name_risk=is_likely_individual,
        )
        return self._blocking_keys(record)


def _clean_id(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    import re
    cleaned = str(raw).strip().upper()
    cleaned = re.sub(r"[\(\)\[\]]", "", cleaned).strip()
    return cleaned or None


def _looks_like_individual(name: str) -> bool:
    """Same heuristic as BESCOM: water bills often in landlord's individual name."""
    if not name:
        return False
    tokens = name.lower().split()
    business_keywords = {
        "pvt", "ltd", "limited", "industries", "traders", "enterprises",
        "company", "co", "llp", "manufacturing", "solutions", "services",
        "technologies", "tech", "infra", "construction", "corp", "corporation",
    }
    has_business_keyword = any(t in business_keywords for t in tokens)
    has_digit = any(c.isdigit() for c in name)
    short_name = len(tokens) <= 2
    return not has_business_keyword and not has_digit and short_name
