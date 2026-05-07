"""OpenSearch-backed blocking engine.

Union-blocking: a pair is a candidate if it shares any blocking key.
Keys: PAN, derived-PAN, pin+name_prefix4, pin+door, phone.
"""
from __future__ import annotations
import logging
from typing import Any

from opensearchpy import OpenSearch, helpers

from ubid.config import get_settings
from ubid.schema.canonical import CanonicalRecord

logger = logging.getLogger(__name__)

INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 2,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "trigram": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "trigram_filter"],
                },
            },
            "filter": {
                "trigram_filter": {
                    "type": "ngram",
                    "min_gram": 3,
                    "max_gram": 3,
                }
            },
        },
    },
    "mappings": {
        "properties": {
            "canonical_id":          {"type": "keyword"},
            "source_system":         {"type": "keyword"},
            "source_record_id":      {"type": "keyword"},
            "pan":                   {"type": "keyword"},
            "legal_entity_pan":      {"type": "keyword"},
            "pin_code":              {"type": "keyword"},
            "blocking_name_prefix4": {"type": "keyword"},
            "blocking_pin_name":     {"type": "keyword"},
            "blocking_pin_door":     {"type": "keyword"},
            "phone":                 {"type": "keyword"},
            "name_normalized":       {"type": "text", "analyzer": "trigram"},
        }
    },
}

_client: OpenSearch | None = None


def get_client() -> OpenSearch:
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenSearch(
            hosts=[settings.opensearch_url],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
        )
    return _client


def ensure_index():
    client = get_client()
    settings = get_settings()
    index = settings.opensearch_index
    if not client.indices.exists(index=index):
        client.indices.create(index=index, body=INDEX_SETTINGS)
        logger.info("Created OpenSearch index: %s", index)


def index_record(record: CanonicalRecord):
    client = get_client()
    settings = get_settings()
    doc = {
        "canonical_id":          record.canonical_id,
        "source_system":         record.source_system,
        "source_record_id":      record.source_record_id,
        "pan":                   record.pan,
        "legal_entity_pan":      record.legal_entity_pan,
        "pin_code":              record.pin_code,
        "blocking_name_prefix4": record.blocking_name_prefix4,
        "blocking_pin_name":     record.blocking_pin_name,
        "blocking_pin_door":     record.blocking_pin_door,
        "phone":                 record.phone,
        "name_normalized":       record.name_normalized,
    }
    client.index(index=settings.opensearch_index, id=record.canonical_id, body=doc)


def bulk_index(records: list[CanonicalRecord]):
    settings = get_settings()
    actions = [
        {
            "_index": settings.opensearch_index,
            "_id": r.canonical_id,
            "_source": {
                "canonical_id":          r.canonical_id,
                "source_system":         r.source_system,
                "source_record_id":      r.source_record_id,
                "pan":                   r.pan,
                "legal_entity_pan":      r.legal_entity_pan,
                "pin_code":              r.pin_code,
                "blocking_name_prefix4": r.blocking_name_prefix4,
                "blocking_pin_name":     r.blocking_pin_name,
                "blocking_pin_door":     r.blocking_pin_door,
                "phone":                 r.phone,
                "name_normalized":       r.name_normalized,
            },
        }
        for r in records
    ]
    success, errors = helpers.bulk(get_client(), actions, raise_on_error=False)
    if errors:
        logger.warning("Bulk index had %d errors", len(errors))
    return success


def find_candidates(record: CanonicalRecord, max_per_key: int = 200) -> list[str]:
    """Return canonical_ids of candidate matches via union-blocking.

    Union-of-keys: a record is a candidate if it shares any of:
      • PAN equality
      • legal_entity_pan (PAN extracted from GSTIN)
      • pin_code + name-prefix-4 soundex (the workhorse)
      • pin_code + door-number prefix
      • phone equality
      • trigram name-similarity (catches PAN-less BESCOM and cross-pin typos)
    """
    client = get_client()
    settings = get_settings()

    should_clauses: list[dict[str, Any]] = []

    if record.pan:
        should_clauses.append({"term": {"pan": record.pan}})
    if record.legal_entity_pan:
        should_clauses.append({"term": {"legal_entity_pan": record.legal_entity_pan}})
    if record.blocking_pin_name:
        should_clauses.append({"term": {"blocking_pin_name": record.blocking_pin_name}})
    if record.blocking_pin_door:
        should_clauses.append({"term": {"blocking_pin_door": record.blocking_pin_door}})
    if record.phone:
        should_clauses.append({"term": {"phone": record.phone}})

    # Trigram-similar name. Cheap fuzzy block, especially valuable when PAN is
    # missing (e.g. BESCOM) or pin codes differ. minimum_should_match=60%
    # keeps the candidate set small while still catching close variants like
    # "Sharma Traders" vs "Sharma Trading Co".
    if record.name_normalized and len(record.name_normalized) >= 4:
        should_clauses.append({
            "match": {
                "name_normalized": {
                    "query": record.name_normalized,
                    "minimum_should_match": "60%",
                }
            }
        })

    if not should_clauses:
        return []

    query = {
        "query": {
            "bool": {
                "should": should_clauses,
                "minimum_should_match": 1,
                "must_not": [
                    {"term": {"canonical_id": record.canonical_id}}
                ],
            }
        },
        "size": max_per_key,
        "_source": ["canonical_id"],
    }

    resp = client.search(index=settings.opensearch_index, body=query)
    return [hit["_source"]["canonical_id"] for hit in resp["hits"]["hits"]]


def which_blocks_shared(a: CanonicalRecord, b: CanonicalRecord) -> list[str]:
    """Return the names of blocks that A and B share (for feature vector)."""
    shared = []
    if a.pan and b.pan and a.pan == b.pan:
        shared.append("pan")
    if a.legal_entity_pan and b.legal_entity_pan and a.legal_entity_pan == b.legal_entity_pan:
        shared.append("derived_pan")
    if a.blocking_pin_name and b.blocking_pin_name and a.blocking_pin_name == b.blocking_pin_name:
        shared.append("pin_name")
    if a.blocking_pin_door and b.blocking_pin_door and a.blocking_pin_door == b.blocking_pin_door:
        shared.append("pin_door")
    if a.phone and b.phone and a.phone == b.phone:
        shared.append("phone")
    return shared
