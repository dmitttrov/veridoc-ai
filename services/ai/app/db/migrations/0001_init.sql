-- Veridoc AI — Phase 2 schema: documents, pages, chunks, ingestion runs.
-- Versioned, forward-only migration. Applied by app/db/migrate.py inside a
-- transaction (the runner wraps each file in BEGIN/COMMIT).
--
-- The embedding vector dimension is fixed at 384 (matches the deterministic
-- provider and sentence-transformers/all-MiniLM-L6-v2). Changing the embedding
-- model to a different dimensionality requires a new migration.

CREATE EXTENSION IF NOT EXISTS vector;

-- Lifecycle of an ingestion attempt.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ingestion_state') THEN
        CREATE TYPE ingestion_state AS ENUM ('pending', 'running', 'succeeded', 'failed');
    END IF;
END$$;

-- One row per unique document (unique by SHA-256 content hash). The id is a
-- deterministic UUIDv5 derived from the content hash, so re-ingesting identical
-- bytes maps to the same row (idempotency).
CREATE TABLE IF NOT EXISTS documents (
    id            uuid PRIMARY KEY,
    content_hash  char(64) NOT NULL UNIQUE,
    filename      text NOT NULL,
    title         text NOT NULL,
    mime_type     text NOT NULL,
    size_bytes    bigint NOT NULL CHECK (size_bytes >= 0),
    page_count    integer NOT NULL CHECK (page_count >= 0),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- One row per page, holding the deterministically normalized page text.
-- Character offsets in document_chunks are relative to normalized_text.
CREATE TABLE IF NOT EXISTS document_pages (
    id              uuid PRIMARY KEY,
    document_id     uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number     integer NOT NULL CHECK (page_number >= 1),
    normalized_text text NOT NULL,
    char_count      integer NOT NULL CHECK (char_count >= 0),
    -- Generated full-text vector for the lexical retrieval leg.
    text_tsv        tsvector GENERATED ALWAYS AS (to_tsvector('english', normalized_text)) STORED,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, page_number)
);

-- One row per chunk. The id is a deterministic UUIDv5 of
-- (content_hash, page_number, char_start, char_end), so chunk identities are
-- stable and reproducible across re-ingestion.
CREATE TABLE IF NOT EXISTS document_chunks (
    id              uuid PRIMARY KEY,
    document_id     uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id         uuid NOT NULL REFERENCES document_pages(id) ON DELETE CASCADE,
    page_number     integer NOT NULL CHECK (page_number >= 1),
    chunk_index     integer NOT NULL CHECK (chunk_index >= 0),
    char_start      integer NOT NULL CHECK (char_start >= 0),
    char_end        integer NOT NULL CHECK (char_end >= char_start),
    text            text NOT NULL,
    -- Embedding metadata travels with every vector so we never silently mix
    -- embeddings from different models/dimensions at retrieval time.
    embedding       vector(384) NOT NULL,
    embedding_model text NOT NULL,
    embedding_dim   integer NOT NULL CHECK (embedding_dim = 384),
    text_tsv        tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, page_number, char_start, char_end)
);

-- One row per ingestion attempt, with explicit state and error capture.
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id               uuid PRIMARY KEY,
    document_id      uuid REFERENCES documents(id) ON DELETE SET NULL,
    content_hash     char(64),
    filename         text NOT NULL,
    mime_type        text,
    size_bytes       bigint CHECK (size_bytes >= 0),
    state            ingestion_state NOT NULL DEFAULT 'pending',
    already_ingested boolean NOT NULL DEFAULT false,
    page_count       integer CHECK (page_count >= 0),
    chunk_count      integer CHECK (chunk_count >= 0),
    error            text,
    started_at       timestamptz NOT NULL DEFAULT now(),
    finished_at      timestamptz
);

-- Indexes -------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_model ON document_chunks (embedding_model);
CREATE INDEX IF NOT EXISTS idx_pages_document ON document_pages (document_id);
CREATE INDEX IF NOT EXISTS idx_runs_content_hash ON ingestion_runs (content_hash);

-- Lexical (full-text) indexes.
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON document_chunks USING gin (text_tsv);
CREATE INDEX IF NOT EXISTS idx_pages_tsv ON document_pages USING gin (text_tsv);

-- Approximate-nearest-neighbour index for the semantic leg (cosine).
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
