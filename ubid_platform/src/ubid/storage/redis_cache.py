"""Hot-path lookup cache: source_id → UBID, with TTL-based invalidation."""
from typing import Optional
import json
import logging
import redis as redis_lib

from ubid.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[redis_lib.Redis] = None

SOURCE_UBID_PREFIX = "ubid:src:"
UBID_VERDICT_PREFIX = "ubid:verdict:"
DEFAULT_TTL = 3600  # 1 hour


def get_client() -> redis_lib.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis_lib.from_url(settings.redis_url, decode_responses=True)
    return _client


def make_source_key(source_system: str, source_record_id: str) -> str:
    return f"{SOURCE_UBID_PREFIX}{source_system}:{source_record_id}"


def get_ubid_for_source(source_system: str, source_record_id: str) -> Optional[str]:
    try:
        return get_client().get(make_source_key(source_system, source_record_id))
    except Exception as e:
        logger.warning("Redis GET failed: %s", e)
        return None


def set_ubid_for_source(source_system: str, source_record_id: str, ubid: str, ttl: int = DEFAULT_TTL):
    try:
        get_client().setex(make_source_key(source_system, source_record_id), ttl, ubid)
    except Exception as e:
        logger.warning("Redis SET failed: %s", e)


def invalidate_source(source_system: str, source_record_id: str):
    try:
        get_client().delete(make_source_key(source_system, source_record_id))
    except Exception as e:
        logger.warning("Redis DEL failed: %s", e)


def set_verdict_cache(ubid: str, verdict_data: dict, ttl: int = 300):
    try:
        get_client().setex(f"{UBID_VERDICT_PREFIX}{ubid}", ttl, json.dumps(verdict_data))
    except Exception as e:
        logger.warning("Redis verdict SET failed: %s", e)


def get_verdict_cache(ubid: str) -> Optional[dict]:
    try:
        raw = get_client().get(f"{UBID_VERDICT_PREFIX}{ubid}")
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning("Redis verdict GET failed: %s", e)
        return None


def invalidate_verdict(ubid: str):
    try:
        get_client().delete(f"{UBID_VERDICT_PREFIX}{ubid}")
    except Exception as e:
        logger.warning("Redis verdict DEL failed: %s", e)
