"""25-feature vector for pairwise scoring.

Feature groups:
  Name      (5)  — jaro_winkler, token_set_ratio, jaccard_ngram, lcs_ratio, exact_stripped
  Address   (6)  — pin_eq, door_eq, locality_match, cross_distance, levenshtein_residual, geo_distance
  Identifier(4)  — gstin_eq, phone_eq, email_domain_eq, pan_agreement
  Structural(4)  — sector_compat, legal_form_compat, employee_ratio, reg_date_diff
  Blocking  (6)  — shared_pan, shared_derived_pan, shared_pin_name, shared_pin_door, shared_phone, n_blocks
"""
from __future__ import annotations
import math
from typing import Optional

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from ubid.schema.canonical import CanonicalRecord

FEATURE_NAMES = [
    # Name
    "name_jaro_winkler",
    "name_token_set_ratio",
    "name_jaccard_trigram",
    "name_lcs_ratio",
    "name_exact_stripped",
    # Address
    "addr_pin_eq",
    "addr_door_eq",
    "addr_locality_match",
    "addr_cross_distance",
    "addr_levenshtein_residual",
    "addr_geo_distance_km",
    # Identifier
    "id_gstin_eq",
    "id_phone_eq",
    "id_email_domain_eq",
    "id_pan_agreement",
    # Structural
    "struct_sector_compat",
    "struct_legal_form_compat",
    "struct_employee_ratio_log",
    "struct_reg_date_diff_log",
    # Blocking
    "blk_shared_pan",
    "blk_shared_derived_pan",
    "blk_shared_pin_name",
    "blk_shared_pin_door",
    "blk_shared_phone",
    "blk_n_shared",
]

MISSING = -1.0   # sentinel for "field absent in one or both records"


def compute(a: CanonicalRecord, b: CanonicalRecord) -> dict[str, float]:
    fv: dict[str, float] = {}

    # ── Name features ─────────────────────────────────────────────────────────
    fv["name_jaro_winkler"] = fuzz.WRatio(a.name_normalized, b.name_normalized) / 100.0
    fv["name_token_set_ratio"] = fuzz.token_set_ratio(a.name_normalized, b.name_normalized) / 100.0
    fv["name_jaccard_trigram"] = _jaccard_trigrams(a.name_normalized, b.name_normalized)
    fv["name_lcs_ratio"] = _lcs_ratio(a.name_normalized, b.name_normalized)
    fv["name_exact_stripped"] = float(
        bool(a.name_legal_form_stripped and b.name_legal_form_stripped
             and a.name_legal_form_stripped == b.name_legal_form_stripped)
    )

    # ── Address features ──────────────────────────────────────────────────────
    if a.pin_code and b.pin_code:
        fv["addr_pin_eq"] = float(a.pin_code == b.pin_code)
    else:
        fv["addr_pin_eq"] = MISSING

    if a.door_number and b.door_number:
        fv["addr_door_eq"] = float(a.door_number == b.door_number)
    else:
        fv["addr_door_eq"] = MISSING

    if a.locality_canonical and b.locality_canonical:
        fv["addr_locality_match"] = float(a.locality_canonical == b.locality_canonical)
    elif a.locality_raw and b.locality_raw:
        fv["addr_locality_match"] = fuzz.token_set_ratio(a.locality_raw, b.locality_raw) / 100.0
    else:
        fv["addr_locality_match"] = MISSING

    fv["addr_cross_distance"] = MISSING  # populated when geocoded

    # Levenshtein on residual address (street_raw or address_raw fallback)
    addr_a = a.street_raw or a.address_raw or ""
    addr_b = b.street_raw or b.address_raw or ""
    if addr_a and addr_b:
        max_len = max(len(addr_a), len(addr_b), 1)
        lev = Levenshtein.distance(addr_a[:128], addr_b[:128])
        fv["addr_levenshtein_residual"] = 1.0 - lev / max_len
    else:
        fv["addr_levenshtein_residual"] = MISSING

    if a.latitude and a.longitude and b.latitude and b.longitude:
        # Skip identical-coord pairs: centroid-based geocoding (locality dict)
        # gives every record in the same locality the same lat/lng, which would
        # be redundant with addr_locality_match. Only emit the feature when the
        # two records have meaningfully different coords (precision >= 100m).
        if (abs(a.latitude - b.latitude) < 1e-3
            and abs(a.longitude - b.longitude) < 1e-3):
            fv["addr_geo_distance_km"] = MISSING
        else:
            fv["addr_geo_distance_km"] = _haversine_km(
                a.latitude, a.longitude, b.latitude, b.longitude
            )
    else:
        fv["addr_geo_distance_km"] = MISSING

    # ── Identifier features ───────────────────────────────────────────────────
    if a.gstin and b.gstin:
        fv["id_gstin_eq"] = float(a.gstin == b.gstin)
    else:
        fv["id_gstin_eq"] = MISSING

    if a.phone and b.phone:
        fv["id_phone_eq"] = float(a.phone == b.phone)
    else:
        fv["id_phone_eq"] = MISSING

    if a.email_domain and b.email_domain:
        fv["id_email_domain_eq"] = float(a.email_domain == b.email_domain)
    else:
        fv["id_email_domain_eq"] = MISSING

    fv["id_pan_agreement"] = _pan_agreement(a, b)

    # ── Structural features ───────────────────────────────────────────────────
    fv["struct_sector_compat"] = _sector_compat(a, b)
    fv["struct_legal_form_compat"] = _legal_form_compat(a, b)

    if a.employee_count and b.employee_count and a.employee_count > 0 and b.employee_count > 0:
        ratio = min(a.employee_count, b.employee_count) / max(a.employee_count, b.employee_count)
        fv["struct_employee_ratio_log"] = math.log1p(ratio)
    else:
        fv["struct_employee_ratio_log"] = MISSING

    if a.registration_date and b.registration_date:
        days = abs((a.registration_date - b.registration_date).days)
        fv["struct_reg_date_diff_log"] = math.log1p(days)
    else:
        fv["struct_reg_date_diff_log"] = MISSING

    # ── Blocking features ─────────────────────────────────────────────────────
    fv["blk_shared_pan"] = float(bool(a.pan and b.pan and a.pan == b.pan))
    fv["blk_shared_derived_pan"] = float(
        bool(a.legal_entity_pan and b.legal_entity_pan and a.legal_entity_pan == b.legal_entity_pan)
    )
    fv["blk_shared_pin_name"] = float(
        bool(a.blocking_pin_name and b.blocking_pin_name and a.blocking_pin_name == b.blocking_pin_name)
    )
    fv["blk_shared_pin_door"] = float(
        bool(a.blocking_pin_door and b.blocking_pin_door and a.blocking_pin_door == b.blocking_pin_door)
    )
    fv["blk_shared_phone"] = float(bool(a.phone and b.phone and a.phone == b.phone))
    fv["blk_n_shared"] = sum([
        fv["blk_shared_pan"], fv["blk_shared_derived_pan"],
        fv["blk_shared_pin_name"], fv["blk_shared_pin_door"], fv["blk_shared_phone"],
    ])

    return fv


def to_vector(fv: dict[str, float]) -> list[float]:
    return [fv[name] for name in FEATURE_NAMES]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _jaccard_trigrams(a: str, b: str) -> float:
    def trigrams(s: str) -> set[str]:
        return {s[i:i+3] for i in range(len(s) - 2)} if len(s) >= 3 else set()
    ta, tb = trigrams(a), trigrams(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _lcs_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(2)]
    best = 0
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                dp[i % 2][j] = dp[(i-1) % 2][j-1] + 1
                best = max(best, dp[i % 2][j])
            else:
                dp[i % 2][j] = 0
    return best / max(m, n)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _pan_agreement(a: CanonicalRecord, b: CanonicalRecord) -> float:
    """Score 0–1 based on PAN / GSTIN cross-agreement."""
    pan_a = a.pan or a.legal_entity_pan
    pan_b = b.pan or b.legal_entity_pan
    if pan_a and pan_b:
        return 1.0 if pan_a == pan_b else 0.0
    return MISSING


def _sector_compat(a: CanonicalRecord, b: CanonicalRecord) -> float:
    # NIC code prefix match (2-digit industry group)
    if a.nic_code and b.nic_code:
        return 1.0 if a.nic_code[:2] == b.nic_code[:2] else 0.3
    # KSPCB category match
    if a.kspcb_category and b.kspcb_category:
        return 1.0 if a.kspcb_category == b.kspcb_category else 0.4
    return MISSING


def _legal_form_compat(a: CanonicalRecord, b: CanonicalRecord) -> float:
    if a.legal_form and b.legal_form:
        return 1.0 if a.legal_form == b.legal_form else 0.2
    return MISSING
