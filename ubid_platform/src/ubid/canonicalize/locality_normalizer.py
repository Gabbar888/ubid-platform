"""Locality normalization: synonym dictionary + fuzzy fallback."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process

_DICT_DIR = Path(__file__).parent.parent.parent.parent / "data" / "dictionaries"

with open(_DICT_DIR / "locality_synonyms.json", encoding="utf-8") as f:
    _RAW_SYNONYMS: dict[str, list[str]] = json.load(f)

# Build forward map: variant → canonical
_SYNONYM_MAP: dict[str, str] = {}
for canonical, variants in _RAW_SYNONYMS.items():
    _SYNONYM_MAP[canonical] = canonical
    for v in variants:
        _SYNONYM_MAP[v.lower().strip()] = canonical

_CANONICAL_KEYS = list(_RAW_SYNONYMS.keys())

_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
FUZZY_THRESHOLD = 80


def _clean(text: str) -> str:
    return _NON_ALNUM_RE.sub(" ", text.lower().strip())


def normalize(raw: Optional[str]) -> Optional[str]:
    """
    Returns the canonical locality key or None.
    Steps: exact match → prefix match → fuzzy fallback → None.
    """
    if not raw:
        return None

    cleaned = _clean(raw)

    # Exact match
    if cleaned in _SYNONYM_MAP:
        return _SYNONYM_MAP[cleaned]

    # Prefix match (raw locality starts with a known canonical/variant)
    for variant, canonical in _SYNONYM_MAP.items():
        if cleaned.startswith(variant) or variant.startswith(cleaned):
            return canonical

    # Fuzzy match against canonical keys
    result = process.extractOne(
        cleaned,
        _CANONICAL_KEYS,
        scorer=fuzz.token_set_ratio,
        score_cutoff=FUZZY_THRESHOLD,
    )
    if result:
        return result[0]

    return None


def add_synonym(variant: str, canonical: str):
    """Runtime update from reviewer feedback (persisted elsewhere)."""
    key = _clean(variant)
    _SYNONYM_MAP[key] = canonical
    if canonical not in _RAW_SYNONYMS:
        _RAW_SYNONYMS[canonical] = []
    if variant not in _RAW_SYNONYMS[canonical]:
        _RAW_SYNONYMS[canonical].append(variant)
    if canonical not in _CANONICAL_KEYS:
        _CANONICAL_KEYS.append(canonical)
