"""Deterministic address parser tuned for Bengaluru / Karnataka patterns."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

PIN_RE = re.compile(r"\b(5[6-9][0-9]{4}|[1-9][0-9]{5})\b")

# Door number: No./# followed by digits, or plain digit/alpha-digit formats
DOOR_RE = re.compile(
    r"(?:no[.\s]?|#|plot\s*no[.\s]?|door\s*no[.\s]?|flat\s*no[.\s]?|site\s*no[.\s]?)?"
    r"\b([0-9]{1,5}(?:[/-][0-9A-Za-z]{1,5})*)\b",
    re.IGNORECASE,
)

# Ordinal variants for cross/main numbers
_ORDINAL_MAP = {
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
    "6th": 6, "7th": 7, "8th": 8, "9th": 9, "10th": 10,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
    "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
}

CROSS_MAIN_RE = re.compile(
    r"(\d+|1st|2nd|3rd|\d+th|first|second|third|fourth|fifth|i{1,3}|iv|v[i]{0,3})"
    r"\s*(cross|main|stage|phase|block)\b",
    re.IGNORECASE,
)

DISTRICT_KEYWORDS = {
    "bengaluru urban": "bengaluru urban",
    "bangalore urban": "bengaluru urban",
    "bengaluru rural": "bengaluru rural",
    "bangalore rural": "bengaluru rural",
    "mysuru": "mysuru",
    "mysore": "mysuru",
    "hubli": "dharwad",
    "dharwad": "dharwad",
    "mangaluru": "dakshina kannada",
    "mangalore": "dakshina kannada",
    "belagavi": "belagavi",
    "belgaum": "belagavi",
    "tumakuru": "tumakuru",
    "tumkur": "tumakuru",
    "kolar": "kolar",
    "ramanagara": "ramanagara",
    "chikkaballapur": "chikkaballapur",
    "mandya": "mandya",
    "hassan": "hassan",
    "chitradurga": "chitradurga",
    "davanagere": "davanagere",
    "davangere": "davanagere",
    "shivamogga": "shivamogga",
    "shimoga": "shivamogga",
    "udupi": "udupi",
    "kodagu": "kodagu",
    "coorg": "kodagu",
}

TALUK_KEYWORDS = {
    "anekal": "anekal",
    "bangalore north": "bengaluru north",
    "bangalore south": "bengaluru south",
    "bangalore east": "bengaluru east",
    "yelahanka": "yelahanka",
    "krishnarajapura": "krishnarajapura",
    "kengeri": "kengeri",
    "nelamangala": "nelamangala",
    "devanahalli": "devanahalli",
    "doddaballapur": "doddaballapur",
    "ramanagara": "ramanagara",
    "channapatna": "channapatna",
}


@dataclass
class ParsedAddress:
    pin_code: Optional[str]
    door_number: Optional[str]
    street_raw: Optional[str]
    locality_raw: Optional[str]
    taluk: Optional[str]
    district: Optional[str]
    cross_main_numbers: list[int]


def parse(raw: str) -> ParsedAddress:
    if not raw:
        return ParsedAddress(None, None, None, None, None, None, [])

    text = raw.strip()

    # Extract pin code
    pin_match = PIN_RE.search(text)
    pin_code = pin_match.group(0) if pin_match else None

    # Remove pin code from further processing
    cleaned = PIN_RE.sub("", text).strip(" ,;")

    # Extract door number (greedy: first match)
    door_number: Optional[str] = None
    door_match = DOOR_RE.search(cleaned)
    if door_match:
        door_number = door_match.group(0).strip()
        cleaned = cleaned[door_match.end():].strip(" ,;")

    # Extract cross/main numbers
    cross_main_numbers: list[int] = []
    for m in CROSS_MAIN_RE.finditer(cleaned):
        num_str = m.group(1).lower()
        if num_str.isdigit():
            cross_main_numbers.append(int(num_str))
        elif num_str in _ORDINAL_MAP:
            cross_main_numbers.append(_ORDINAL_MAP[num_str])

    # District detection
    lower_text = raw.lower()
    district: Optional[str] = None
    for kw, canonical in DISTRICT_KEYWORDS.items():
        if kw in lower_text:
            district = canonical
            break

    # Taluk detection
    taluk: Optional[str] = None
    for kw, canonical in TALUK_KEYWORDS.items():
        if kw in lower_text:
            taluk = canonical
            break

    # Locality: take the remaining cleaned text as locality_raw
    locality_raw = cleaned.strip(" ,;") or None

    return ParsedAddress(
        pin_code=pin_code,
        door_number=door_number,
        street_raw=raw[:64] if raw else None,
        locality_raw=locality_raw,
        taluk=taluk,
        district=district,
        cross_main_numbers=cross_main_numbers,
    )
