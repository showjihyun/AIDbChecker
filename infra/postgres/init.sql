-- Spec: DM-MIG-001
-- NeuralDB PostgreSQL 16 초기화 — Extensions + pg_partman setup

-- Required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";          -- pgvector
CREATE EXTENSION IF NOT EXISTS "pg_partman";       -- auto partitioning
-- pg_cron은 shared_preload_libraries에서 로드 필요 (Docker 설정)
-- CREATE EXTENSION IF NOT EXISTS "pg_cron";

-- pg_stat_statements (보통 이미 활성화)
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
