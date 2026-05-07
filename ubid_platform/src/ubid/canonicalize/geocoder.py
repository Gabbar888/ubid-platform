"""Geocoding: address → (latitude, longitude).

Strategy (cheapest first):
  1. Curated locality dictionary (data/dictionaries/locality_coordinates.json) —
     ~70 hand-mapped Bengaluru / Karnataka centroids. Sub-millisecond lookup.
  2. Pin-code centroid lookup from the same dictionary.
  3. District centroid lookup.
  4. (Optional) Self-hosted Nominatim — only used if NOMINATIM_URL env var is
     set. Adds a docker service; see docker-compose.yml comments.

This module fills the latitude / longitude fields on a CanonicalRecord, which
then enables the `addr_geo_distance_km` feature in the LightGBM scorer.

Production note: the proposal explicitly forbids hosted geocoders (Google,
HERE, etc.). Nominatim is the only legally-defensible option because it can
run on-prem.
"""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Optional

import httpx

from ubid.schema.canonical import CanonicalRecord

logger = logging.getLogger(__name__)

_DICT_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "dictionaries" / "locality_coordinates.json"
)

_LOCALITIES: dict[str, list[float]] = {}
_PINS: dict[str, list[float]] = {}
_DISTRICTS: dict[str, list[float]] = {}

if _DICT_PATH.exists():
    with open(_DICT_PATH, encoding="utf-8") as _f:
        _raw = json.load(_f)
    _LOCALITIES = _raw.get("localities", {})
    _PINS = _raw.get("pin_codes", {})
    _DISTRICTS = _raw.get("districts", {})

_NOMINATIM_URL = os.getenv("NOMINATIM_URL")  # e.g. http://nominatim:8080
_NOMINATIM_TIMEOUT = float(os.getenv("NOMINATIM_TIMEOUT", "3.0"))
_HTTP_CLIENT: Optional[httpx.Client] = None


def _client() -> httpx.Client:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.Client(timeout=_NOMINATIM_TIMEOUT)
    return _HTTP_CLIENT


def lookup_locality(locality_canonical: Optional[str]) -> Optional[tuple[float, float]]:
    if not locality_canonical:
        return None
    coords = _LOCALITIES.get(locality_canonical.lower().strip())
    if coords:
        return float(coords[0]), float(coords[1])
    return None


def lookup_pin(pin_code: Optional[str]) -> Optional[tuple[float, float]]:
    if not pin_code:
        return None
    coords = _PINS.get(pin_code.strip())
    if coords:
        return float(coords[0]), float(coords[1])
    return None


def lookup_district(district: Optional[str]) -> Optional[tuple[float, float]]:
    if not district:
        return None
    coords = _DISTRICTS.get(district.lower().strip())
    if coords:
        return float(coords[0]), float(coords[1])
    return None


def query_nominatim(address: str) -> Optional[tuple[float, float]]:
    """Query a self-hosted Nominatim instance. No-op if NOMINATIM_URL unset."""
    if not _NOMINATIM_URL:
        return None
    if not address or len(address.strip()) < 5:
        return None
    try:
        r = _client().get(
            f"{_NOMINATIM_URL.rstrip('/')}/search",
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "in"},
            headers={"User-Agent": "UBID-Platform/1.0 (Karnataka C&I)"},
        )
        r.raise_for_status()
        results = r.json()
        if results:
            lat = float(results[0]["lat"])
            lng = float(results[0]["lon"])
            return lat, lng
    except Exception as e:
        logger.debug("Nominatim query failed for '%s': %s", address[:60], e)
    return None


def geocode(record: CanonicalRecord) -> Optional[tuple[float, float]]:
    """Return (lat, lng) for a canonical record.

    Priority order:
      1. Already geocoded — return cached coords.
      2. Nominatim (if NOMINATIM_URL set) — building-level precision when the
         address has a door number, otherwise a city-block precision result
         that still beats the locality centroid for cross-record distinction.
      3. Curated locality dict — fast fallback when Nominatim has no match
         (e.g. very-rural addresses or typo'd street names).
      4. Pin-code centroid — coarse but better than nothing.
      5. District centroid — coarsest fallback.

    Returns None if every path fails. Coordinates outside the Karnataka
    bounding box (lat 11.5-19, lng 74-78.5) are rejected as garbage and the
    fallback chain continues.
    """
    if record.latitude is not None and record.longitude is not None:
        return float(record.latitude), float(record.longitude)

    # ── Try Nominatim first (most precise) ──────────────────────────────
    if _NOMINATIM_URL and record.address_raw:
        coords = query_nominatim(record.address_raw)
        if coords and _within_karnataka(coords):
            return coords

    # ── Curated dict fallbacks ──────────────────────────────────────────
    for fn, key in [
        (lookup_locality, record.locality_canonical),
        (lookup_pin, record.pin_code),
        (lookup_district, record.district),
    ]:
        coords = fn(key)
        if coords:
            return coords

    return None


def _within_karnataka(coords: tuple[float, float]) -> bool:
    """Reject Nominatim results that fall outside the Karnataka bounding box.
    Avoids returning a 'New York, USA' geocode for a corrupt address."""
    lat, lng = coords
    return 11.5 <= lat <= 19.0 and 74.0 <= lng <= 78.5


def geocode_and_attach(record: CanonicalRecord) -> bool:
    """Mutate the record in-place with geocoded coords. Returns True if attached."""
    coords = geocode(record)
    if coords is None:
        return False
    record.latitude, record.longitude = coords
    return True


def stats() -> dict:
    """Snapshot of the in-memory dictionary sizes (for /admin diagnostics)."""
    return {
        "localities": len(_LOCALITIES),
        "pin_codes": len(_PINS),
        "districts": len(_DISTRICTS),
        "nominatim_configured": _NOMINATIM_URL is not None,
        "nominatim_url": _NOMINATIM_URL or None,
    }
