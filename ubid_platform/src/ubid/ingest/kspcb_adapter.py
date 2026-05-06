"""Adapter for KSPCB XGN consent records — best structured source."""
from __future__ import annotations
from datetime import date
from typing import Any, Optional

from ubid.schema.canonical import CanonicalRecord, SourceSystem, KSPCBCategory
from ubid.canonicalize import identifier_extractor
from ubid.ingest.base_adapter import BaseAdapter
from ubid.ingest.ekarmika_adapter import _parse_date, _parse_int

_CATEGORY_MAP = {
    "red": KSPCBCategory.RED,
    "r": KSPCBCategory.RED,
    "orange": KSPCBCategory.ORANGE,
    "o": KSPCBCategory.ORANGE,
    "green": KSPCBCategory.GREEN,
    "g": KSPCBCategory.GREEN,
    "white": KSPCBCategory.WHITE,
    "w": KSPCBCategory.WHITE,
}


class KSPCBAdapter(BaseAdapter):
    source_system = SourceSystem.KSPCB

    def adapt(self, row: dict[str, Any]) -> CanonicalRecord:
        raw_name = str(row.get("industry_name", "") or row.get("name", "")).strip()

        # KSPCB has the cleanest structured address — use separate fields directly
        industrial_area = str(row.get("industrial_area", "") or "").strip()
        taluk = str(row.get("taluk", "") or "").strip()
        district = str(row.get("district", "") or "").strip().lower()
        pin_code = str(row.get("pin_code", "") or "").strip() or None

        raw_address = ", ".join(p for p in [industrial_area, taluk, district, pin_code or ""] if p)

        name_norm, name_tokens, name_stripped = self._canonicalize_name(raw_name)

        # Use structured locality (industrial_area) for canonical lookup
        locality_can = self._normalize_locality(industrial_area or None)

        pan = self._clean_pan(row.get("pan"))
        gstin = self._clean_gstin(row.get("gstin"))
        cin = identifier_extractor.clean_cin(row.get("cin"))

        legal_entity_pan = pan
        pan_derived = False
        if not pan and gstin:
            legal_entity_pan = identifier_extractor.extract_pan_from_gstin(gstin)
            pan_derived = bool(legal_entity_pan)

        phone = identifier_extractor.clean_phone(row.get("phone"))
        email = identifier_extractor.clean_email(row.get("email"))

        category_raw = str(row.get("industry_category", "") or "").strip().lower()
        kspcb_cat = _CATEGORY_MAP.get(category_raw)

        lat: Optional[float] = None
        lon: Optional[float] = None
        try:
            lat = float(row["latitude"]) if row.get("latitude") else None
            lon = float(row["longitude"]) if row.get("longitude") else None
        except (TypeError, ValueError):
            pass

        consent_until = _parse_date(row.get("valid_until") or row.get("consent_valid_until"))
        reg_date = _parse_date(row.get("date_of_commissioning") or row.get("registration_date"))

        record = CanonicalRecord(
            source_system=SourceSystem.KSPCB,
            source_record_id=str(row.get("consent_file_no", row.get("id", ""))),

            name_raw=raw_name,
            name_normalized=name_norm,
            name_tokens=name_tokens,
            name_legal_form_stripped=name_stripped,

            address_raw=raw_address,
            pin_code=pin_code,
            door_number=None,
            street_raw=None,
            locality_raw=industrial_area or None,
            locality_canonical=locality_can,
            taluk=taluk or None,
            district=district or None,
            latitude=lat,
            longitude=lon,

            pan=pan,
            pan_entity_type=identifier_extractor.pan_entity_type(pan),
            pan_is_proprietorship=identifier_extractor.pan_is_proprietorship(pan),
            gstin=gstin,
            gstin_state_code=identifier_extractor.gstin_state_code(gstin),
            legal_entity_pan=legal_entity_pan,
            pan_derived_from_gstin=pan_derived,
            cin=cin,

            phone=phone,
            email=email,
            email_domain=identifier_extractor.email_domain(email),

            sector_raw=str(row.get("sector", "") or "").strip() or None,
            nic_code=str(row.get("nic_code", "") or "").strip() or None,
            kspcb_category=kspcb_cat,

            registration_date=reg_date,
            consent_valid_until=consent_until,
        )
        return self._blocking_keys(record)
