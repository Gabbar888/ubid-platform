"""Validate and extract structured information from PAN and GSTIN."""
import re
from typing import Optional

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

PAN_ENTITY_TYPE_MAP = {
    "P": "individual",
    "C": "company",
    "F": "partnership",
    "H": "huf",
    "T": "trust",
    "A": "aop",
    "B": "boi",
    "L": "local_authority",
    "J": "juridical_person",
    "G": "government",
}

KARNATAKA_STATE_CODE = "29"


def clean_pan(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip().upper().replace(" ", "").replace("-", "")
    return cleaned if PAN_RE.match(cleaned) else None


def pan_entity_type(pan: Optional[str]) -> Optional[str]:
    if not pan or len(pan) < 4:
        return None
    return PAN_ENTITY_TYPE_MAP.get(pan[3])


def pan_is_proprietorship(pan: Optional[str]) -> bool:
    """PAN 4th char == 'P' means an individual / proprietorship."""
    if not pan or len(pan) < 4:
        return False
    return pan[3] == "P"


def clean_gstin(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip().upper().replace(" ", "")
    return cleaned if GSTIN_RE.match(cleaned) else None


def gstin_state_code(gstin: Optional[str]) -> Optional[str]:
    if not gstin or len(gstin) < 2:
        return None
    return gstin[:2]


def extract_pan_from_gstin(gstin: Optional[str]) -> Optional[str]:
    """Extract the embedded 10-char PAN from a GSTIN (positions 3–12 inclusive)."""
    if not gstin or len(gstin) < 12:
        return None
    candidate = gstin[2:12]
    return candidate if PAN_RE.match(candidate) else None


def clean_cin(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip().upper().replace(" ", "")
    # CIN: L/U + 5 digit + 2 alpha + 4 digit + 3 alpha + 6 digit
    cin_re = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
    return cleaned if cin_re.match(cleaned) else None


def clean_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"[^0-9]", "", raw)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return None


def clean_email(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip().lower()
    email_re = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")
    return cleaned if email_re.match(cleaned) else None


def email_domain(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1]
