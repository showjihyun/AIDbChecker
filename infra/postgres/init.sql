-- Spec: DM-MIG-001
-- NeuralDB PostgreSQL 16 초기화 — Extensions

-- Required extensions (always available in pgvector/pgvector:pg16 image)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";          -- pgvector

-- Optional extensions: pg_partman, pg_cron, pg_stat_statements
-- These require installation in the Docker image or shared_preload_libraries.
-- Enable them manually when the image supports them:
-- CREATE EXTENSION IF NOT EXISTS "pg_partman";
-- CREATE EXTENSION IF NOT EXISTS "pg_cron";
-- CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
