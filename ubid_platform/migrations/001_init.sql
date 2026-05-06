-- UBID Platform — initial schema
-- Run order matters: no FK violations.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Canonical records (one row per source-system record after canonicalization)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS canonical_records (
    canonical_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_system       TEXT NOT NULL,
    source_record_id    TEXT NOT NULL,
    source_schema_version TEXT NOT NULL DEFAULT '1.0',

    -- Business name
    name_raw            TEXT NOT NULL,
    name_normalized     TEXT NOT NULL,
    name_tokens         TEXT[] NOT NULL DEFAULT '{}',
    name_legal_form_stripped TEXT NOT NULL DEFAULT '',

    -- Address
    address_raw         TEXT NOT NULL DEFAULT '',
    pin_code            TEXT,
    door_number         TEXT,
    street_raw          TEXT,
    locality_raw        TEXT,
    locality_canonical  TEXT,
    taluk               TEXT,
    district            TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,

    -- Identifiers
    pan                 TEXT,
    pan_entity_type     CHAR(1),
    pan_is_proprietorship BOOLEAN NOT NULL DEFAULT FALSE,
    gstin               TEXT,
    gstin_state_code    TEXT,
    legal_entity_pan    TEXT,
    pan_derived_from_gstin BOOLEAN NOT NULL DEFAULT FALSE,
    cin                 TEXT,

    -- Contact
    phone               TEXT,
    email               TEXT,
    email_domain        TEXT,

    -- Sector
    sector_raw          TEXT,
    nic_code            TEXT,
    kspcb_category      TEXT,
    tariff_category     TEXT,

    -- Structural
    legal_form          TEXT,
    employee_count      INTEGER,
    sanctioned_load_kw  DOUBLE PRECISION,
    registration_date   DATE,

    -- BESCOM-specific
    rr_number           TEXT,
    account_id          TEXT,
    k_number            TEXT,
    bescom_consumer_name_risk BOOLEAN NOT NULL DEFAULT FALSE,

    -- Validity windows
    consent_valid_until DATE,
    licence_valid_until DATE,

    -- Blocking keys
    blocking_name_prefix4 TEXT NOT NULL DEFAULT '',
    blocking_pin_name   TEXT NOT NULL DEFAULT '',
    blocking_pin_door   TEXT NOT NULL DEFAULT '',

    UNIQUE (source_system, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_cr_pan ON canonical_records(pan) WHERE pan IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cr_legal_entity_pan ON canonical_records(legal_entity_pan) WHERE legal_entity_pan IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cr_pin_code ON canonical_records(pin_code) WHERE pin_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cr_blocking_pin_name ON canonical_records(blocking_pin_name) WHERE blocking_pin_name != '';
CREATE INDEX IF NOT EXISTS idx_cr_source ON canonical_records(source_system, source_record_id);
CREATE INDEX IF NOT EXISTS idx_cr_phone ON canonical_records(phone) WHERE phone IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Legal entities (PAN-anchored)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS legal_entities (
    legal_entity_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pan                 TEXT UNIQUE,
    name_canonical      TEXT,
    legal_form          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_le_pan ON legal_entities(pan) WHERE pan IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. UBID nodes (one per establishment)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ubid_nodes (
    ubid                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    legal_entity_id     UUID REFERENCES legal_entities(legal_entity_id),
    pin_code            TEXT,
    district            TEXT,
    sector_canonical    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    cluster_version     INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_ubid_pin ON ubid_nodes(pin_code) WHERE pin_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ubid_sector ON ubid_nodes(sector_canonical) WHERE sector_canonical IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. UBID ↔ source record links
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ubid_source_links (
    link_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ubid                UUID NOT NULL REFERENCES ubid_nodes(ubid),
    canonical_id        UUID NOT NULL REFERENCES canonical_records(canonical_id),
    linked_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    linked_by           TEXT NOT NULL DEFAULT 'auto',
    confidence          DOUBLE PRECISION,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (ubid, canonical_id)
);

CREATE INDEX IF NOT EXISTS idx_usl_ubid ON ubid_source_links(ubid);
CREATE INDEX IF NOT EXISTS idx_usl_canonical ON ubid_source_links(canonical_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Scored candidate pairs
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS linkage_pairs (
    pair_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_id_a      UUID NOT NULL REFERENCES canonical_records(canonical_id),
    canonical_id_b      UUID NOT NULL REFERENCES canonical_records(canonical_id),
    raw_score           DOUBLE PRECISION NOT NULL,
    calibrated_probability DOUBLE PRECISION NOT NULL,
    deterministic_tier_fired BOOLEAN NOT NULL DEFAULT FALSE,
    deterministic_result BOOLEAN,
    feature_vector      JSONB NOT NULL DEFAULT '{}',
    shap_contributions  JSONB NOT NULL DEFAULT '{}',
    shared_blocks       TEXT[] NOT NULL DEFAULT '{}',
    scored_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    decision            TEXT,
    decided_at          TIMESTAMPTZ,
    decided_by          TEXT,
    UNIQUE (canonical_id_a, canonical_id_b)
);

CREATE INDEX IF NOT EXISTS idx_lp_prob ON linkage_pairs(calibrated_probability);
CREATE INDEX IF NOT EXISTS idx_lp_decision ON linkage_pairs(decision) WHERE decision IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Linkage constraints (must-link / cannot-link from reviewers)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS linkage_constraints (
    constraint_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_id_a      UUID NOT NULL REFERENCES canonical_records(canonical_id),
    canonical_id_b      UUID NOT NULL REFERENCES canonical_records(canonical_id),
    constraint_type     TEXT NOT NULL,   -- must_link | cannot_link
    created_by          TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes               TEXT,
    UNIQUE (canonical_id_a, canonical_id_b)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Activity events (UBID-keyed event log, synced from DuckDB)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS activity_events (
    event_id            UUID PRIMARY KEY,
    ubid                UUID REFERENCES ubid_nodes(ubid),
    canonical_id        UUID REFERENCES canonical_records(canonical_id),
    source_system       TEXT NOT NULL,
    source_record_id    TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    event_date          DATE NOT NULL,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata            JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_ae_ubid ON activity_events(ubid) WHERE ubid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ae_event_date ON activity_events(event_date);
CREATE INDEX IF NOT EXISTS idx_ae_event_type ON activity_events(event_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- 8. Activity verdicts (current verdict per UBID)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS activity_verdicts (
    verdict_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ubid                UUID NOT NULL REFERENCES ubid_nodes(ubid),
    verdict             TEXT NOT NULL,
    continuity_score    DOUBLE PRECISION NOT NULL,
    evidence_timeline   JSONB NOT NULL DEFAULT '[]',
    deterministic_overrides JSONB NOT NULL DEFAULT '[]',
    sector_prior_applied BOOLEAN NOT NULL DEFAULT FALSE,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ubid)
);

CREATE INDEX IF NOT EXISTS idx_av_verdict ON activity_verdicts(verdict);

-- ─────────────────────────────────────────────────────────────────────────────
-- 9. Quarantine events (unjoined)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quarantine_events (
    event_id            UUID PRIMARY KEY,
    source_system       TEXT NOT NULL,
    source_record_id    TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    event_date          DATE NOT NULL,
    quarantined_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason              TEXT NOT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}',
    retry_count         INTEGER NOT NULL DEFAULT 0,
    last_retry_at       TIMESTAMPTZ,
    resolved            BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_ubid       UUID,
    resolved_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_qe_resolved ON quarantine_events(resolved);
CREATE INDEX IF NOT EXISTS idx_qe_source ON quarantine_events(source_system, source_record_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 10. Reviewer queue
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reviewer_queue (
    queue_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pair_id             UUID NOT NULL REFERENCES linkage_pairs(pair_id),
    priority_score      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    assigned_to         TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',  -- pending|in_review|decided|deferred
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rq_status ON reviewer_queue(status);
CREATE INDEX IF NOT EXISTS idx_rq_priority ON reviewer_queue(priority_score DESC) WHERE status = 'pending';

-- ─────────────────────────────────────────────────────────────────────────────
-- 11. Reviewer decisions (audit log)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reviewer_decisions (
    decision_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    queue_id            UUID REFERENCES reviewer_queue(queue_id),
    pair_id             UUID NOT NULL REFERENCES linkage_pairs(pair_id),
    canonical_id_a      UUID NOT NULL,
    canonical_id_b      UUID NOT NULL,
    decision            TEXT NOT NULL,  -- confirm_match|reject|defer|flag_quality
    reviewer_id         TEXT NOT NULL,
    reviewer_tier       TEXT NOT NULL DEFAULT 'junior',
    notes               TEXT,
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_training_label   BOOLEAN NOT NULL DEFAULT TRUE
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 12. Training labels (for model retraining)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS training_labels (
    label_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_id_a      UUID NOT NULL,
    canonical_id_b      UUID NOT NULL,
    is_match            BOOLEAN NOT NULL,
    source              TEXT NOT NULL DEFAULT 'reviewer',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (canonical_id_a, canonical_id_b)
);
