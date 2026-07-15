-- ============================================================
-- RegLens — Regulatory Sludge Intelligence Agent
-- Database Schema
--
-- Design principles (Ketchup DEV session, Jul 7 2026, Wiebe Geldenhuys):
--   1. No FK constraints — relationships enforced in application
--   2. UUIDs from application (uuid.uuid4()), never DB-generated
--   3. Link tables for all relationships (one-to-many + self-ref)
--   4. Index EVERY link table column
--   5. Status flag on every entity table (fast current-state queries)
--   6. Separate log tables for full change history
--   7. Generic 'description' field everywhere, aliased in SELECT
--   8. No triggers — all state changes in application layer
--   9. Hierarchical domain/corpus metadata (adaptive to ingested docs)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- DROP (safe order — no FK so any order works)
-- ============================================================
DROP TABLE IF EXISTS finding_log;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS session_finding;
DROP TABLE IF EXISTS finding_provision;
DROP TABLE IF EXISTS review;
DROP TABLE IF EXISTS provision;
DROP TABLE IF EXISTS finding;
DROP TABLE IF EXISTS document_chunk;
DROP TABLE IF EXISTS chunk_chunk;
DROP TABLE IF EXISTS chunk;
DROP TABLE IF EXISTS document;
DROP TABLE IF EXISTS session;
DROP TABLE IF EXISTS user_account;

-- ============================================================
-- ENTITY TABLES
-- All UUIDs are NOT NULL — inserted by application, not DB DEFAULT
-- All tables have: description, status, created_at
-- ============================================================

CREATE TABLE user_account (
    user_uid        UUID            NOT NULL,
    description     VARCHAR(255),               -- display name (alias in SELECT)
    email           VARCHAR(255),
    user_type       VARCHAR(100),               -- admin | analyst | regulator | reviewer
    organisation    VARCHAR(255),               -- e.g. "FCA", "NBG"
    status          VARCHAR(100),               -- active | inactive
    created_at      TIMESTAMP       DEFAULT NOW()
);

-- ============================================================
-- RAG TABLES — adaptive: no hardcoded domains or jurisdictions
-- All domain/jurisdiction info lives in document.metadata JSONB
-- extracted by LLM during ingestion
-- ============================================================

CREATE TABLE document (
    document_uid    UUID            NOT NULL,
    description     TEXT,                       -- title (alias as 'title' in SELECT)
    source          TEXT,                       -- file path or URL
    content         TEXT,
    source_type     VARCHAR(100),               -- regulatory | guidance | statute | circular
    status          VARCHAR(100),               -- active | archived | processing
    -- All adaptive context lives here — extracted by LLM on ingest
    -- Keys: regulatory_body, domain, document_type, regulatory_level,
    --       obligations_present, detected_at
    metadata        JSONB           DEFAULT '{}',
    created_at      TIMESTAMP       DEFAULT NOW()
);

CREATE TABLE chunk (
    chunk_uid       UUID            NOT NULL,
    description     TEXT,                       -- brief summary (alias as 'summary')
    content         TEXT,
    embedding       vector(1536),               -- change to 768 for nomic-embed-text
    chunk_index     INTEGER,
    token_count     INTEGER,
    status          VARCHAR(100),               -- active | orphaned
    metadata        JSONB           DEFAULT '{}',
    created_at      TIMESTAMP       DEFAULT NOW()
);

-- Link: document → chunks (one document, many chunks)
-- Wiebe: "one to many... equipment_part pattern"
CREATE TABLE document_chunk (
    document_uid    UUID            NOT NULL,
    chunk_uid       UUID            NOT NULL
);

-- Chunks can reference overlapping/context chunks
-- Wiebe: "equipment can reference itself... equipment_equipment"
CREATE TABLE chunk_chunk (
    chunk_uid           UUID        NOT NULL,
    linked_chunk_uid    UUID        NOT NULL,
    relationship_type   VARCHAR(100)            -- overlap | context | continuation
);

-- ============================================================
-- FINDINGS TABLES
-- ============================================================

CREATE TABLE finding (
    finding_uid         UUID        NOT NULL,
    description         TEXT,                   -- title (alias as 'title' in SELECT)
    sludge_type         VARCHAR(100),           -- horizontal | vertical | cumulative
    severity            VARCHAR(50),            -- high | medium | low
    recommended_action  VARCHAR(100),           -- delete | consolidate | clarify | escalate
    rationale           TEXT,
    confidence_score    DOUBLE PRECISION,
    cross_cutting       BOOLEAN     DEFAULT FALSE,
    estimated_burden    TEXT,
    affected_domains    JSONB       DEFAULT '[]', -- discovered from corpus, not hardcoded
    status              VARCHAR(100),           -- pending_review | validated | approved | rejected
    created_at          TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE provision (
    provision_uid       UUID        NOT NULL,
    description         TEXT,                   -- full citation text (alias as 'citation')
    document_uid        UUID,                   -- source document (no FK)
    reference_text      VARCHAR(500),           -- e.g. "Article 9(1)" or "Section 4.3"
    status              VARCHAR(100),
    created_at          TIMESTAMP   DEFAULT NOW()
);

-- Link: finding ↔ provisions (many-to-many)
CREATE TABLE finding_provision (
    finding_uid         UUID        NOT NULL,
    provision_uid       UUID        NOT NULL,
    relationship_type   VARCHAR(50)             -- source | overlapping | conflicting
);

-- ============================================================
-- SESSION + WORKFLOW TABLES
-- ============================================================

CREATE TABLE session (
    session_uid         UUID        NOT NULL,
    user_uid            UUID        NOT NULL,   -- link (no FK)
    description         TEXT,                   -- query summary (alias as 'title')
    query               TEXT,
    approval_status     VARCHAR(100),           -- pending | approved | rejected
    status              VARCHAR(100),           -- active | complete | error
    metadata            JSONB       DEFAULT '{}',
    created_at          TIMESTAMP   DEFAULT NOW()
);

-- Link: session → findings
CREATE TABLE session_finding (
    session_uid         UUID        NOT NULL,
    finding_uid         UUID        NOT NULL
);

CREATE TABLE review (
    review_uid          UUID        NOT NULL,
    session_uid         UUID        NOT NULL,   -- link (no FK)
    user_uid            UUID        NOT NULL,   -- reviewer (no FK)
    description         TEXT,                   -- reviewer notes (alias as 'notes')
    decision            VARCHAR(100),           -- approved | rejected | needs_revision
    status              VARCHAR(100),
    created_at          TIMESTAMP   DEFAULT NOW()
);

-- ============================================================
-- LOG TABLES
-- Wiebe: "part_log... every time something happens you add an entry"
-- Entity table = current state (fast queries)
-- Log table = full history (audit trail)
-- ============================================================

CREATE TABLE finding_log (
    log_uid             UUID        NOT NULL,
    finding_uid         UUID        NOT NULL,   -- link (no FK)
    session_uid         UUID,
    user_uid            UUID,
    description         TEXT,                   -- what happened
    status_from         VARCHAR(100),
    status_to           VARCHAR(100),
    log_type            VARCHAR(100),           -- detected | validated | approved | rejected
    created_at          TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE audit_log (
    log_uid             UUID        NOT NULL,
    session_uid         UUID,
    user_uid            UUID,
    description         TEXT,                   -- workflow step description
    log_type            VARCHAR(100),           -- discover | retrieve | detect | validate | hitl | report
    status_from         VARCHAR(100),
    status_to           VARCHAR(100),
    iteration_count     INTEGER,
    created_at          TIMESTAMP   DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- Wiebe: "as soon as we add that index, three went down to two"
-- Index every column used in joins and WHERE clauses
-- ============================================================

-- user_account
CREATE INDEX idx_user_uid           ON user_account(user_uid);
CREATE INDEX idx_user_email         ON user_account(email);
CREATE INDEX idx_user_status        ON user_account(status);

-- document
CREATE INDEX idx_document_uid       ON document(document_uid);
CREATE INDEX idx_document_status    ON document(status);
CREATE INDEX idx_document_metadata  ON document USING GIN (metadata);

-- chunk
CREATE INDEX idx_chunk_uid          ON chunk(chunk_uid);
CREATE INDEX idx_chunk_status       ON chunk(status);
CREATE INDEX idx_chunk_embedding    ON chunk USING ivfflat (embedding vector_cosine_ops)
                                    WITH (lists = 1);
CREATE INDEX idx_chunk_content_trgm ON chunk USING GIN (content gin_trgm_ops);

-- document_chunk link — index BOTH columns
CREATE INDEX idx_dc_document        ON document_chunk(document_uid);
CREATE INDEX idx_dc_chunk           ON document_chunk(chunk_uid);

-- chunk_chunk link
CREATE INDEX idx_cc_chunk           ON chunk_chunk(chunk_uid);
CREATE INDEX idx_cc_linked          ON chunk_chunk(linked_chunk_uid);

-- finding
CREATE INDEX idx_finding_uid        ON finding(finding_uid);
CREATE INDEX idx_finding_status     ON finding(status);
CREATE INDEX idx_finding_severity   ON finding(severity);
CREATE INDEX idx_finding_type       ON finding(sludge_type);

-- provision
CREATE INDEX idx_provision_uid      ON provision(provision_uid);
CREATE INDEX idx_provision_doc      ON provision(document_uid);

-- finding_provision link — index BOTH columns
CREATE INDEX idx_fp_finding         ON finding_provision(finding_uid);
CREATE INDEX idx_fp_provision       ON finding_provision(provision_uid);

-- session
CREATE INDEX idx_session_uid        ON session(session_uid);
CREATE INDEX idx_session_user       ON session(user_uid);
CREATE INDEX idx_session_status     ON session(status);

-- session_finding link — index BOTH columns
CREATE INDEX idx_sf_session         ON session_finding(session_uid);
CREATE INDEX idx_sf_finding         ON session_finding(finding_uid);

-- review
CREATE INDEX idx_review_uid         ON review(review_uid);
CREATE INDEX idx_review_session     ON review(session_uid);

-- logs
CREATE INDEX idx_fl_finding         ON finding_log(finding_uid);
CREATE INDEX idx_fl_session         ON finding_log(session_uid);
CREATE INDEX idx_al_session         ON audit_log(session_uid);

-- ============================================================
-- SEARCH
-- No triggers, no stored procedures — search queries live in the
-- application layer (agent/tools.py: hybrid_search / vector fallback)
-- as parameterized SQL. 'description' aliased as meaningful names
-- in SELECT there.
-- ============================================================
