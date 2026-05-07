"""Ingest API — receive batches of source records, canonicalize, index, score."""
from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select

from ubid.schema.canonical import SourceSystem, CanonicalRecord
from ubid.ingest.ekarmika_adapter import EKarmikaAdapter
from ubid.ingest.fbis_adapter import FBISAdapter
from ubid.ingest.kspcb_adapter import KSPCBAdapter
from ubid.ingest.bescom_adapter import BESCOMAdapter
from ubid.ingest.bwssb_adapter import BWSSBAdapter
from ubid.blocking.opensearch_blocker import bulk_index, find_candidates
from ubid.clustering.union_find import UnionFind
from ubid.scoring.lgbm_scorer import get_scorer
from ubid.review.queue import enqueue_pair
from ubid.graph import neo4j_graph
from ubid.storage import redis_cache
from ubid.storage.postgres import (
    get_db, CanonicalRecordORM, LinkagePairORM, UBIDNodeORM, UBIDSourceLinkORM
)
from ubid.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)

_ADAPTERS = {
    SourceSystem.EKARMIKA: EKarmikaAdapter(),
    SourceSystem.FBIS:     FBISAdapter(),
    SourceSystem.KSPCB:    KSPCBAdapter(),
    SourceSystem.BESCOM:   BESCOMAdapter(),
    SourceSystem.BWSSB:    BWSSBAdapter(),
}


class IngestRequest(BaseModel):
    records: list[dict[str, Any]]


class IngestResponse(BaseModel):
    accepted: int
    auto_linked: int
    review_queued: int
    new_ubids: int


@router.post("/{source}", response_model=IngestResponse)
def ingest_records(source: SourceSystem, body: IngestRequest):
    adapter = _ADAPTERS.get(source)
    if not adapter:
        raise HTTPException(400, f"Unknown source system: {source}")

    raw_records = adapter.adapt_batch(body.records)
    if not raw_records:
        return IngestResponse(accepted=0, auto_linked=0, review_queued=0, new_ubids=0)

    # ── Step 0: Geocode (locality / pin / district lookup, optionally Nominatim)
    # Mutates rec.latitude / rec.longitude in place. Best-effort — records
    # without a recognisable locality stay unc oded and just skip the
    # addr_geo_distance_km feature.
    from ubid.canonicalize.geocoder import geocode_and_attach
    for rec in raw_records:
        try:
            geocode_and_attach(rec)
        except Exception as e:
            logger.debug("Geocoding failed for %s: %s", rec.source_record_id, e)

    # ── Step 1: Upsert canonical records, fixing canonical_id consistency ─────
    # If a record already exists in Postgres, reuse its canonical_id so that
    # OpenSearch and Postgres always reference the same UUID.
    persisted: list[CanonicalRecord] = []
    with get_db() as db:
        for rec in raw_records:
            existing = db.execute(
                select(CanonicalRecordORM).where(
                    CanonicalRecordORM.source_system == rec.source_system,
                    CanonicalRecordORM.source_record_id == rec.source_record_id,
                )
            ).scalar_one_or_none()

            if existing:
                # Reuse the stored canonical_id — do NOT index a new UUID
                rec.canonical_id = str(existing.canonical_id)
            else:
                db.add(_canonical_to_orm(rec))

            persisted.append(rec)
    # All canonical_ids in `persisted` are now committed in Postgres

    # ── Step 2: Index in OpenSearch using the resolved canonical_ids ──────────
    bulk_index(persisted)

    # ── Step 3: Score candidate pairs ─────────────────────────────────────────
    settings = get_settings()
    auto_thresh = settings.auto_link_threshold
    scorer = get_scorer()

    auto_linked = 0
    review_queued = 0
    pairs_to_enqueue: list[tuple[str, float, dict]] = []
    auto_link_pairs: list[tuple[str, str]] = []  # for inline clustering

    # Collect all pairs first, then commit once — avoids autoflush FK violations
    new_pairs: list[LinkagePairORM] = []
    seen_pairs: set[tuple[str, str]] = set()

    with get_db() as db:
        # Load existing pair keys to skip duplicates
        existing_keys = set(
            db.execute(
                select(LinkagePairORM.canonical_id_a, LinkagePairORM.canonical_id_b)
            ).fetchall()
        )

        for rec in persisted:
            candidate_ids = find_candidates(rec)
            for cid in candidate_ids:
                if cid == rec.canonical_id:
                    continue

                a_id, b_id = sorted([rec.canonical_id, cid])
                pair_key = (a_id, b_id)

                if pair_key in existing_keys or pair_key in seen_pairs:
                    continue

                # Fetch candidate from DB — use no_autoflush to prevent premature flush
                with db.no_autoflush:
                    cand_orm = db.execute(
                        select(CanonicalRecordORM).where(
                            CanonicalRecordORM.canonical_id == cid
                        )
                    ).scalar_one_or_none()

                if not cand_orm:
                    continue

                cand_rec = _orm_to_canonical(cand_orm)
                sp = scorer.score(rec, cand_rec)

                pair_id = str(uuid.uuid4())
                pair_orm = LinkagePairORM(
                    pair_id=pair_id,
                    canonical_id_a=a_id,
                    canonical_id_b=b_id,
                    raw_score=sp.raw_score,
                    calibrated_probability=sp.calibrated_probability,
                    deterministic_tier_fired=sp.deterministic_tier_fired,
                    deterministic_result=sp.deterministic_result,
                    feature_vector=sp.feature_vector,
                    shap_contributions=sp.shap_contributions,
                    shared_blocks=sp.shared_blocks,
                    scored_at=datetime.now(timezone.utc),
                )
                db.add(pair_orm)
                seen_pairs.add(pair_key)

                is_auto = sp.calibrated_probability >= auto_thresh or (
                    sp.deterministic_tier_fired and sp.deterministic_result is True
                )
                if is_auto:
                    auto_linked += 1
                    auto_link_pairs.append((a_id, b_id))
                else:
                    pairs_to_enqueue.append((pair_id, sp.calibrated_probability, sp.feature_vector))
                    review_queued += 1
    # linkage_pairs committed — now safe to insert reviewer_queue rows

    for pid, prob, fv in pairs_to_enqueue:
        enqueue_pair(pid, prob, fv)

    # ── Step 4: Cluster the batch and assign UBIDs ────────────────────────────
    # Build a union-find over (a) every record in this batch, (b) every
    # auto-linked pair we just produced, (c) any historical auto-linked pair
    # that touches a canonical_id we've already pulled in, and (d) reviewer
    # must-link constraints. Cannot-link constraints block specific unions.
    # Each connected component gets one UBID (existing one if any member is
    # already assigned, merging if multiple).
    new_ubids = 0
    now = datetime.now(timezone.utc)
    rec_by_canonical: dict[str, CanonicalRecord] = {r.canonical_id: r for r in persisted}

    from sqlalchemy import text, bindparam  # noqa: E402

    with get_db() as db:
        # Pull cannot-link constraints up-front so we can respect them while
        # building the union-find.
        cannot_link: set[frozenset[str]] = set()
        must_link_pairs: list[tuple[str, str]] = []
        for ca, cb, ctype in db.execute(text("""
            SELECT canonical_id_a, canonical_id_b, constraint_type FROM linkage_constraints
        """)).fetchall():
            if str(ctype).lower().startswith("cannot"):
                cannot_link.add(frozenset([str(ca), str(cb)]))
            else:
                must_link_pairs.append((str(ca), str(cb)))

        uf = UnionFind()
        for cid in rec_by_canonical:
            uf.add(cid)

        def _safe_union(a: str, b: str) -> bool:
            if frozenset([a, b]) in cannot_link:
                return False
            uf.union(a, b)
            return True

        for a, b in auto_link_pairs:
            _safe_union(a, b)
        for a, b in must_link_pairs:
            _safe_union(a, b)

        # Pull historical auto-link edges that touch nodes in our current graph
        # so cross-batch components form correctly.
        known_ids = list(uf.parent.keys())
        if known_ids:
            hist_rows = db.execute(text("""
                SELECT canonical_id_a, canonical_id_b
                FROM linkage_pairs
                WHERE (canonical_id_a IN :ids OR canonical_id_b IN :ids)
                  AND (calibrated_probability >= :t
                       OR (deterministic_tier_fired AND deterministic_result = TRUE))
            """).bindparams(bindparam("ids", expanding=True)),
                {"ids": known_ids, "t": auto_thresh}
            ).fetchall()
            for ca, cb in hist_rows:
                _safe_union(str(ca), str(cb))

        # Process each connected component
        for _, members in uf.components().items():
            # What UBIDs (if any) already exist for these canonical_ids?
            existing = db.execute(text("""
                SELECT canonical_id, ubid FROM ubid_source_links
                WHERE canonical_id IN :ids
            """).bindparams(bindparam("ids", expanding=True)),
                {"ids": members}
            ).fetchall()
            existing_links = {str(c): str(u) for c, u in existing}
            existing_ubids = sorted(set(existing_links.values()))

            if existing_ubids:
                target_ubid = existing_ubids[0]
                # Merge multiple UBIDs into the chosen one
                for old in existing_ubids[1:]:
                    db.execute(text("""
                        UPDATE ubid_source_links SET ubid = :t WHERE ubid = :o
                    """), {"t": target_ubid, "o": old})
                    # Drop dependent rows that FK to the old ubid_nodes row
                    db.execute(text("DELETE FROM activity_verdicts WHERE ubid = :o"), {"o": old})
                    db.execute(text("DELETE FROM ubid_nodes WHERE ubid = :o"), {"o": old})
                    redis_cache.invalidate_verdict(old)
                redis_cache.invalidate_verdict(target_ubid)
            else:
                target_ubid = str(uuid.uuid4())
                rep = next((rec_by_canonical[m] for m in members if m in rec_by_canonical), None)
                db.add(UBIDNodeORM(
                    ubid=target_ubid,
                    pin_code=rep.pin_code if rep else None,
                    district=rep.district if rep else None,
                    sector_canonical=(rep.nic_code or rep.sector_raw) if rep else None,
                    created_at=now,
                    updated_at=now,
                ))
                new_ubids += 1

            # Link any members that aren't already linked to target_ubid
            for cid in members:
                if existing_links.get(cid) == target_ubid:
                    continue
                if cid in existing_links:
                    # Already linked but to a now-merged UBID (handled by UPDATE above)
                    continue
                db.add(UBIDSourceLinkORM(
                    link_id=str(uuid.uuid4()),
                    ubid=target_ubid,
                    canonical_id=cid,
                    linked_at=now,
                    linked_by="auto",
                    confidence=1.0,
                ))
                rec = rec_by_canonical.get(cid)
                if rec:
                    redis_cache.set_ubid_for_source(rec.source_system, rec.source_record_id, target_ubid)
                    try:
                        neo4j_graph.upsert_ubid(target_ubid, None, rec.pin_code, rec.district, rec.sector_raw)
                        neo4j_graph.upsert_source_record(
                            rec.canonical_id, target_ubid,
                            rec.source_system, rec.source_record_id, rec.name_raw
                        )
                    except Exception as e:
                        logger.warning("Neo4j upsert failed (non-fatal): %s", e)

    return IngestResponse(
        accepted=len(persisted),
        auto_linked=auto_linked,
        review_queued=review_queued,
        new_ubids=new_ubids,
    )


@router.post("/{source}/upload")
async def ingest_csv_upload(source: SourceSystem, file: UploadFile = File(...)):
    import csv, io
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    records = list(reader)
    return ingest_records(source, IngestRequest(records=records))


# ── ORM helpers ───────────────────────────────────────────────────────────────

def _canonical_to_orm(rec: CanonicalRecord) -> CanonicalRecordORM:
    return CanonicalRecordORM(
        canonical_id=rec.canonical_id,
        ingested_at=rec.ingested_at,
        source_system=rec.source_system,
        source_record_id=rec.source_record_id,
        source_schema_version=rec.source_schema_version,
        name_raw=rec.name_raw,
        name_normalized=rec.name_normalized,
        name_tokens=rec.name_tokens,
        name_legal_form_stripped=rec.name_legal_form_stripped,
        address_raw=rec.address_raw,
        pin_code=rec.pin_code,
        door_number=rec.door_number,
        street_raw=rec.street_raw,
        locality_raw=rec.locality_raw,
        locality_canonical=rec.locality_canonical,
        taluk=rec.taluk,
        district=rec.district,
        latitude=rec.latitude,
        longitude=rec.longitude,
        pan=rec.pan,
        pan_entity_type=rec.pan_entity_type,
        pan_is_proprietorship=rec.pan_is_proprietorship,
        gstin=rec.gstin,
        gstin_state_code=rec.gstin_state_code,
        legal_entity_pan=rec.legal_entity_pan,
        pan_derived_from_gstin=rec.pan_derived_from_gstin,
        cin=rec.cin,
        phone=rec.phone,
        email=rec.email,
        email_domain=rec.email_domain,
        sector_raw=rec.sector_raw,
        nic_code=rec.nic_code,
        kspcb_category=rec.kspcb_category,
        tariff_category=rec.tariff_category,
        legal_form=rec.legal_form,
        employee_count=rec.employee_count,
        sanctioned_load_kw=rec.sanctioned_load_kw,
        registration_date=rec.registration_date,
        rr_number=rec.rr_number,
        account_id=rec.account_id,
        k_number=rec.k_number,
        bescom_consumer_name_risk=rec.bescom_consumer_name_risk,
        consent_valid_until=rec.consent_valid_until,
        licence_valid_until=rec.licence_valid_until,
        blocking_name_prefix4=rec.blocking_name_prefix4,
        blocking_pin_name=rec.blocking_pin_name,
        blocking_pin_door=rec.blocking_pin_door,
    )


def _orm_to_canonical(orm: CanonicalRecordORM) -> CanonicalRecord:
    return CanonicalRecord(
        canonical_id=str(orm.canonical_id),
        ingested_at=orm.ingested_at,
        source_system=orm.source_system,
        source_record_id=orm.source_record_id,
        name_raw=orm.name_raw,
        name_normalized=orm.name_normalized,
        name_tokens=orm.name_tokens or [],
        name_legal_form_stripped=orm.name_legal_form_stripped or "",
        address_raw=orm.address_raw or "",
        pin_code=orm.pin_code,
        door_number=orm.door_number,
        locality_raw=orm.locality_raw,
        locality_canonical=orm.locality_canonical,
        taluk=orm.taluk,
        district=orm.district,
        latitude=orm.latitude,
        longitude=orm.longitude,
        pan=orm.pan,
        pan_entity_type=orm.pan_entity_type,
        pan_is_proprietorship=orm.pan_is_proprietorship or False,
        gstin=orm.gstin,
        gstin_state_code=orm.gstin_state_code,
        legal_entity_pan=orm.legal_entity_pan,
        pan_derived_from_gstin=orm.pan_derived_from_gstin or False,
        cin=orm.cin,
        phone=orm.phone,
        email=orm.email,
        email_domain=orm.email_domain,
        sector_raw=orm.sector_raw,
        nic_code=orm.nic_code,
        kspcb_category=orm.kspcb_category,
        tariff_category=orm.tariff_category,
        legal_form=orm.legal_form,
        employee_count=orm.employee_count,
        sanctioned_load_kw=orm.sanctioned_load_kw,
        registration_date=orm.registration_date,
        rr_number=orm.rr_number,
        account_id=orm.account_id,
        k_number=orm.k_number,
        bescom_consumer_name_risk=orm.bescom_consumer_name_risk or False,
        consent_valid_until=orm.consent_valid_until,
        licence_valid_until=orm.licence_valid_until,
        blocking_name_prefix4=orm.blocking_name_prefix4 or "",
        blocking_pin_name=orm.blocking_pin_name or "",
        blocking_pin_door=orm.blocking_pin_door or "",
    )
