"""Adapter for FBIS (Factories) records — Form 2 / Form 3."""
from __future__ import annotations
from datetime import date
from typing import Any, Optional

from ubid.schema.canonical import CanonicalRecord, SourceSystem, LegalForm
from ubid.canonicalize import identifier_extractor
from ubid.ingest.base_adapter import BaseAdapter
from ubid.ingest.ekarmika_adapter import _parse_date, _parse_int

_LEGAL_FORM_MAP = {
    "proprietorship": LegalForm.PROPRIETORSHIP,
    "sole proprietor": LegalForm.PROPRIETORSHIP,
    "partnership": LegalForm.PARTNERSHIP,
    "pvt ltd": LegalForm.PVT_LTD,
    "private limited": LegalForm.PVT_LTD,
    "public limited": LegalForm.PUBLIC_LTD,
    "llp": LegalForm.LLP,
    "cooperative": LegalForm.COOPERATIVE,
    "government": LegalForm.GOVERNMENT,
    "huf": LegalForm.HUF,
}


def _map_legal_form(raw: Optional[str]) -> Optional[LegalForm]:
    if not raw:
        return None
    lower = raw.lower().strip()
    for key, val in _LEGAL_FORM_MAP.items():
        if key in lower:
            return val
    return LegalForm.OTHER


class FBISAdapter(BaseAdapter):
    source_system = SourceSystem.FBIS

    def adapt(self, row: dict[str, Any]) -> CanonicalRecord:
        raw_name = str(row.get("factory_name", "") or row.get("name", "")).strip()
        # FBIS may store taluk and district as separate fields
        raw_address = _build_address(row)

        name_norm, name_tokens, name_stripped = self._canonicalize_name(raw_name)
        addr = self._parse_address(raw_address)

        # FBIS has separate structured taluk/district — override parser result if present
        if row.get("taluk"):
            addr.taluk = str(row["taluk"]).strip()
        if row.get("district"):
            addr.district = str(row["district"]).strip().lower()
        if row.get("pin_code"):
            addr.pin_code = str(row["pin_code"]).strip()

        locality_can = self._normalize_locality(addr.locality_raw)

        # PAN is captured at the Occupier level in FBIS
        pan = self._clean_pan(row.get("occupier_pan") or row.get("pan"))
        gstin = self._clean_gstin(row.get("gstin"))

        legal_entity_pan = pan
        pan_derived = False
        if not pan and gstin:
            legal_entity_pan = identifier_extractor.extract_pan_from_gstin(gstin)
            pan_derived = bool(legal_entity_pan)

        phone = identifier_extractor.clean_phone(row.get("phone"))
        email = identifier_extractor.clean_email(row.get("email"))

        licence_until = _parse_date(row.get("licence_valid_until"))
        reg_date = _parse_date(row.get("registration_date") or row.get("date_of_incorporation"))

        # HP → KW conversion (1 HP ≈ 0.7457 kW)
        load_kw: Optional[float] = None
        if row.get("installed_kw"):
            try:
                load_kw = float(row["installed_kw"])
            except (TypeError, ValueError):
                pass
        elif row.get("installed_hp"):
            try:
                load_kw = float(row["installed_hp"]) * 0.7457
            except (TypeError, ValueError):
                pass

        record = CanonicalRecord(
            source_system=SourceSystem.FBIS,
            source_record_id=str(row.get("licence_number", row.get("form2_registration_no", row.get("id", "")))),

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

            sector_raw=str(row.get("nature_of_manufacturing", "") or "").strip() or None,
            nic_code=str(row.get("nic_code", "") or "").strip() or None,
            legal_form=_map_legal_form(row.get("constitution_type")),
            employee_count=_parse_int(row.get("employee_count") or row.get("max_workers")),
            sanctioned_load_kw=load_kw,
            registration_date=reg_date,
            licence_valid_until=licence_until,
        )
        return self._blocking_keys(record)


def _build_address(row: dict[str, Any]) -> str:
    parts = [
        row.get("address", ""),
        row.get("village_town", ""),
        row.get("taluk", ""),
        row.get("district", ""),
        str(row.get("pin_code", "") or ""),
    ]
    return ", ".join(p for p in parts if p and str(p).strip())
