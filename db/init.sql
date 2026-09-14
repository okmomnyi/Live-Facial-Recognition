-- ---------------------------------------------------------------------------
-- LFR prototype schema. Source of truth for the database (do NOT rely on
-- SQLAlchemy create_all for real deploys). Bootstrapped by the Postgres
-- container on first start; for Neon, run this once in the SQL editor.
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS persons (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL CHECK (category IN ('wanted','missing','escaped','poi')),
    notes      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS refs (
    id            SERIAL PRIMARY KEY,
    person_id     INT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    image_path    TEXT NOT NULL,
    embedding     vector(512) NOT NULL,
    quality_score REAL NOT NULL DEFAULT 1.0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- NOTE: no ANN index on refs.embedding, on purpose.
--
-- An ivfflat index has a small-N recall cliff: with few rows and the default
-- ivfflat.probes = 1, `ORDER BY embedding <=> q` probes a single list and can
-- miss the nearest row entirely, returning NO match at any threshold. A
-- checkpoint watchlist is small (hundreds to a few thousand refs), where an
-- exact cosine scan is both correct and fast. Correct recall matters far more
-- than sub-millisecond latency here, so we do a full scan.
--
-- Embeddings are L2-normalized, so cosine similarity = 1 - (embedding <=> q).
--
-- If this ever needs to scale to very large watchlists, prefer an HNSW index
-- (no probes recall cliff):
--   CREATE INDEX refs_embedding_hnsw_idx
--     ON refs USING hnsw (embedding vector_cosine_ops);
-- An ivfflat index would additionally require building it only after many rows
-- exist AND `SET LOCAL ivfflat.probes = N` on the search query.

CREATE TABLE IF NOT EXISTS cameras (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    location    TEXT,
    source_type TEXT NOT NULL DEFAULT 'upload'
);

-- Seed two demo checkpoints (only if the table is empty).
INSERT INTO cameras (name, location, source_type)
SELECT * FROM (VALUES
    ('Checkpoint A', 'Main Terminal - Entry Gate', 'upload'),
    ('Checkpoint B', 'Bus Bay 3 - Departures',    'upload')
) AS seed(name, location, source_type)
WHERE NOT EXISTS (SELECT 1 FROM cameras);

CREATE TABLE IF NOT EXISTS alerts (
    id           SERIAL PRIMARY KEY,
    person_id    INT NOT NULL REFERENCES persons(id),
    ref_id       INT NOT NULL REFERENCES refs(id),
    camera_id    INT REFERENCES cameras(id),
    confidence   REAL NOT NULL,
    capture_path TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','confirmed','dismissed')),
    reviewed_by  TEXT,
    reviewed_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS alerts_created_at_idx ON alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS alerts_status_idx     ON alerts (status);

CREATE TABLE IF NOT EXISTS audit_log (
    id           SERIAL PRIMARY KEY,
    actor        TEXT NOT NULL,
    action       TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id   INT,
    detail       JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
