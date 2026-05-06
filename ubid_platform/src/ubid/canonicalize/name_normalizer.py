"""Deterministic business-name normalization pipeline."""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate
    _INDIC_AVAILABLE = True
except ImportError:
    _INDIC_AVAILABLE = False

_DICT_DIR = Path(__file__).parent.parent.parent.parent / "data" / "dictionaries"

with open(_DICT_DIR / "legal_form_patterns.json", encoding="utf-8") as f:
    _LFP = json.load(f)

with open(_DICT_DIR / "abbreviations.json", encoding="utf-8") as f:
    _ABBREVS: dict[str, str] = json.load(f)

_STRIP_SUFFIXES: list[str] = sorted(
    [s.lower() for s in _LFP["strip_suffixes"]], key=len, reverse=True
)

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")


def _to_ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _transliterate_kannada(text: str) -> str:
    if not _INDIC_AVAILABLE:
        return text
    try:
        return transliterate(text, sanscript.KANNADA, sanscript.ITRANS)
    except Exception:
        return text


def _is_likely_kannada(text: str) -> bool:
    return any("ಀ" <= c <= "೿" for c in text)


def normalize(raw: str) -> tuple[str, list[str], str]:
    """
    Returns (normalized_name, token_list, legal_form_stripped_name).
    All outputs are lowercase ASCII.
    """
    text = raw.strip()

    if _is_likely_kannada(text):
        text = _transliterate_kannada(text)

    text = _to_ascii(text)
    text = text.lower()
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()

    # Expand abbreviations (token-level)
    tokens = text.split()
    tokens = [_ABBREVS.get(t, t) for t in tokens]
    text = " ".join(tokens)

    # Strip legal form suffixes (longest match first)
    stripped = text
    for suffix in _STRIP_SUFFIXES:
        if stripped.endswith(" " + suffix):
            stripped = stripped[: -(len(suffix) + 1)].strip()
            break
        if stripped == suffix:
            stripped = ""
            break

    tokens = [t for t in text.split() if t]
    return text, tokens, stripped


def name_prefix4(normalized: str) -> str:
    """First 4 chars of the normalized name (Soundex-ish blocking key)."""
    clean = re.sub(r"\s+", "", normalized)
    return clean[:4] if len(clean) >= 4 else clean.ljust(4, "_")
