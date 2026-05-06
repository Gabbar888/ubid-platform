"""Adapter for e-Karmika Shop & Establishment records."""
from __future__ import annotations
from datetime import date
from typing import Any, Optional

from ubid.schema.canonical import CanonicalRecord, SourceSystem
from ubid.canonicalize import identifier_extractor
from ubid.ingest.base_adapter import BaseAdapter


class EKarmikaAdapter(BaseAdapter):
    source_system = SourceSystem.EKARMIKA

    def adapt(self, row: dict[str, Any]) -> CanonicalRecord:
        raw_name = str(row.get("name", "") or row.get("establishment_name", "")).strip()
        raw_address = str(row.get("address", "") or row.get("postal_address", "")).strip()

        name_norm, name_tokens, name_stripped = self._canonicalize_name(raw_name)
        addr = self._parse_address(raw_address)
        locality_can = self._normalize_locality(addr.locality_raw)

        pan = self._clean_pan(row.get("pan"))
        gstin = self._clean_gstin(row.get("gstin"))

        # Derive legal-entity PAN from GSTIN if PAN is absent
        legal_entity_pan = pan
        pan_derived = False
        if not pan and gstin:
            legal_entity_pan = identifier_extractor.extract_pan_from_gstin(gstin)
            pan_derived = bool(legal_entity_pan)

        phone = identifier_extractor.clean_phone(row.get("phone") or row.get("contact_phone"))
        email = identifier_extractor.clean_email(row.get("email") or row.get("contact_email"))

        reg_date = _parse_date(row.get("date_of_commencement") or row.get("registration_date"))

        record = CanonicalRecord(
            source_system=SourceSystem.EKARMIKA,
            source_record_id=str(row.get("establishment_registration_no", row.get("id", ""))),

            name_raw=raw_name,
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

            pan=pan,
            pan_entity_type=identifier_extractor.pan_entity_type(pan),
            pan_is_proprietorship=identifier_extractor.pan_is_proprietorship(pan),
            gstin=gstin,
            gstin_state_code=identifier_extractor.gstin_state_code(gstin),
            legal_entity_pan=legal_entity_pan,
            pan_derived_from_gstin=pan_derived,

            phone=phone,
            email=email,
            email_domain=identifier_extractor.email_domain(email),

            sector_raw=str(row.get("nature_of_business", "") or "").strip() or None,
            employee_count=_parse_int(row.get("employee_count") or row.get("total_employees")),
            registration_date=reg_date,
        )
        return self._blocking_keys(record)


def _parse_date(val: Any) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        from datetime import datetime
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(str(val).strip(), fmt).date()
            except ValueError:
                continue
    except Exception:
        pass
    return None


def _parse_int(val: Any) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
