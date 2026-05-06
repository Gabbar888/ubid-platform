"""Abstract base for source-system adapters."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from ubid.schema.canonical import CanonicalRecord
from ubid.canonicalize import name_normalizer, address_parser, locality_normalizer, identifier_extractor


class BaseAdapter(ABC):
    source_system: str

    @abstractmethod
    def adapt(self, row: dict[str, Any]) -> CanonicalRecord:
        """Convert one raw source row to a CanonicalRecord."""
        ...

    def adapt_batch(self, rows: list[dict[str, Any]]) -> list[CanonicalRecord]:
        results = []
        for row in rows:
            try:
                results.append(self.adapt(row))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Adapter %s failed on row %s: %s", self.source_system, row.get("id", "?"), e
                )
        return results

    # ── Shared canonicalization helpers ──────────────────────────────────────

    def _canonicalize_name(self, raw: str):
        return name_normalizer.normalize(raw)

    def _parse_address(self, raw: str):
        return address_parser.parse(raw)

    def _normalize_locality(self, raw: str | None):
        return locality_normalizer.normalize(raw)

    def _clean_pan(self, raw: str | None):
        return identifier_extractor.clean_pan(raw)

    def _clean_gstin(self, raw: str | None):
        return identifier_extractor.clean_gstin(raw)

    def _blocking_keys(self, record: CanonicalRecord) -> CanonicalRecord:
        prefix4 = name_normalizer.name_prefix4(record.name_normalized)
        record.blocking_name_prefix4 = prefix4
        if record.pin_code:
            record.blocking_pin_name = f"{record.pin_code}|{prefix4}"
            if record.door_number:
                record.blocking_pin_door = f"{record.pin_code}|{record.door_number}"
        return record
