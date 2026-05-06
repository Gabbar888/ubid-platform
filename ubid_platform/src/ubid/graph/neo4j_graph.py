"""Neo4j UBID entity graph.

Node labels:
  LegalEntity  — anchored to PAN
  UBID         — one per establishment
  SourceRecord — one per canonical record

Relationship types:
  (LegalEntity)-[:OWNS]->(UBID)
  (UBID)-[:HAS_SOURCE]->(SourceRecord)
  (UBID)-[:SUCCESSOR_OF]->(UBID)   for address-change continuity
"""
from __future__ import annotations
import logging
from typing import Optional

from neo4j import GraphDatabase, Driver

from ubid.config import get_settings

logger = logging.getLogger(__name__)

_driver: Optional[Driver] = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        _ensure_constraints(_driver)
    return _driver


def _ensure_constraints(driver: Driver):
    with driver.session() as s:
        s.run("CREATE CONSTRAINT ubid_unique IF NOT EXISTS FOR (u:UBID) REQUIRE u.ubid IS UNIQUE")
        s.run("CREATE CONSTRAINT le_pan_unique IF NOT EXISTS FOR (l:LegalEntity) REQUIRE l.pan IS UNIQUE")
        s.run("CREATE CONSTRAINT sr_unique IF NOT EXISTS FOR (r:SourceRecord) REQUIRE r.canonical_id IS UNIQUE")


def upsert_legal_entity(legal_entity_id: str, pan: Optional[str], name: Optional[str]):
    with get_driver().session() as s:
        s.run("""
            MERGE (l:LegalEntity {legal_entity_id: $lei})
            SET l.pan = $pan, l.name = $name, l.updated_at = datetime()
        """, lei=legal_entity_id, pan=pan, name=name)


def upsert_ubid(ubid: str, legal_entity_id: Optional[str], pin_code: Optional[str],
                district: Optional[str], sector: Optional[str]):
    with get_driver().session() as s:
        s.run("""
            MERGE (u:UBID {ubid: $ubid})
            SET u.pin_code = $pin, u.district = $district,
                u.sector = $sector, u.updated_at = datetime()
        """, ubid=ubid, pin=pin_code, district=district, sector=sector)

        if legal_entity_id:
            s.run("""
                MATCH (l:LegalEntity {legal_entity_id: $lei})
                MATCH (u:UBID {ubid: $ubid})
                MERGE (l)-[:OWNS]->(u)
            """, lei=legal_entity_id, ubid=ubid)


def upsert_source_record(canonical_id: str, ubid: str, source_system: str,
                         source_record_id: str, name: str):
    with get_driver().session() as s:
        s.run("""
            MERGE (r:SourceRecord {canonical_id: $cid})
            SET r.source_system = $sys, r.source_record_id = $rid,
                r.name = $name, r.updated_at = datetime()
        """, cid=canonical_id, sys=source_system, rid=source_record_id, name=name)

        s.run("""
            MATCH (u:UBID {ubid: $ubid})
            MATCH (r:SourceRecord {canonical_id: $cid})
            MERGE (u)-[:HAS_SOURCE]->(r)
        """, ubid=ubid, cid=canonical_id)


def add_successor_edge(old_ubid: str, new_ubid: str, reason: str = "address_change"):
    with get_driver().session() as s:
        s.run("""
            MATCH (old:UBID {ubid: $old})
            MATCH (new:UBID {ubid: $new})
            MERGE (new)-[:SUCCESSOR_OF {reason: $reason, created_at: datetime()}]->(old)
        """, old=old_ubid, new=new_ubid, reason=reason)


def get_ubid_details(ubid: str) -> dict:
    with get_driver().session() as s:
        result = s.run("""
            MATCH (u:UBID {ubid: $ubid})
            OPTIONAL MATCH (l:LegalEntity)-[:OWNS]->(u)
            OPTIONAL MATCH (u)-[:HAS_SOURCE]->(r:SourceRecord)
            RETURN u, l, collect(r) AS sources
        """, ubid=ubid).single()
        if not result:
            return {}
        return {
            "ubid": dict(result["u"]),
            "legal_entity": dict(result["l"]) if result["l"] else None,
            "source_records": [dict(r) for r in result["sources"]],
        }


def find_ubids_by_pan(pan: str) -> list[str]:
    with get_driver().session() as s:
        rows = s.run("""
            MATCH (l:LegalEntity {pan: $pan})-[:OWNS]->(u:UBID)
            RETURN u.ubid AS ubid
        """, pan=pan).data()
        return [r["ubid"] for r in rows]


def unmerge(canonical_id: str, old_ubid: str, new_ubid: str, reviewer_id: str):
    """Remove a source record from old UBID and attach to new UBID."""
    with get_driver().session() as s:
        s.run("""
            MATCH (u:UBID {ubid: $old})-[rel:HAS_SOURCE]->(r:SourceRecord {canonical_id: $cid})
            DELETE rel
        """, old=old_ubid, cid=canonical_id)

        upsert_ubid(new_ubid, None, None, None, None)
        upsert_source_record(canonical_id, new_ubid, "", "", "")

        s.run("""
            MATCH (u:UBID {ubid: $old})
            MATCH (n:UBID {ubid: $new})
            MERGE (u)-[:UNMERGE_EVENT {reviewer: $rev, at: datetime()}]->(n)
        """, old=old_ubid, new=new_ubid, rev=reviewer_id)
