-- Runs ONCE, the first time the database volume is created.
-- Turns on the three PostgreSQL "superpowers" FALCON uses.

CREATE EXTENSION IF NOT EXISTS postgis;   -- geo: "within 200 m of Location A?"
CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector: AI similarity / duplicates
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy text: "CCTV-01" finds "CCTV-001"
