-- 001_item_embeddings.sql
--
-- Block 1 (hours 0-4), owner: Vandanaa.
-- Rule R1 (DATA_MODEL.md): additive only. This never renames or repurposes
-- anything in the given 15-table schema — it only adds a new table sitting
-- beside it, keyed by entity_type + entity_id.
--
-- Run this AFTER data/schema.sql (the given schema) and the CSV load, and
-- BEFORE backend/ingestion/embed_catalogue.py.
--
-- Idempotent: safe to re-run.

CREATE EXTENSION IF NOT EXISTS vector;

-- paraphrase-multilingual-MiniLM-L12-v2 (ARCHITECTURE.md) outputs 384-dim
-- vectors. If the embedding model is ever swapped, this dimension and the
-- ivfflat index below both need to change together.
CREATE TABLE IF NOT EXISTS item_embeddings (
    entity_type   text        NOT NULL CHECK (entity_type IN ('hotel', 'poi', 'package')),
    entity_id     text        NOT NULL,
    embedding     vector(384) NOT NULL,
    source_hash   text        NOT NULL, -- md5 of the embedded text; lets the
                                         -- ingestion job skip unchanged rows
                                         -- on re-run instead of re-embedding
                                         -- the whole catalogue every time
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_type, entity_id)
);

-- Cosine distance is what retrieval.py (Prakruti, Block 2) will query with —
-- confirm against API_SPEC.md / her retrieval code before Block 2 starts,
-- since an L2 vs cosine mismatch here would silently mis-rank everything.
-- ivfflat needs rows in the table before it's useful; if this is run before
-- any rows exist, ANALYZE + reindex after the embedding job finishes.
CREATE INDEX IF NOT EXISTS item_embeddings_cosine_idx
    ON item_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS item_embeddings_entity_type_idx
    ON item_embeddings (entity_type);
