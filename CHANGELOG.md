# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0.0] - 2026-03-25 — DB KPI Dashboard

### Added
- **DB KPI Spec** (FS-KPI-001): 5 categories, 12 key performance indicators
- **KPI Calculator**: delta-based TPS/QPS/IOPS/Deadlocks, live slow queries/active sessions/locks
- **GET /api/v1/instances/{id}/kpi**: real-time 12-KPI endpoint with status thresholds
- **KPI Overview Panel**: 5-category dashboard panel with color-coded status
- **InstanceCard extended**: 5 KPIs (TPS, Hit%, Conn, Locks, Size) up from 3
- **Adapter extension**: deadlocks in hot metrics + collect_kpi_extras() for live queries

## [0.3.1.0] - 2026-03-25

### Fixed
- ASH heatmap: SQL literal_column fix + frontend bucket→matrix transform
- ASH sessions/wait-breakdown: correct query params (from_ts/to_ts)
- System Health: parse flat API response (was expecting nested components)
- MetricChart: map raw pg_stat fields + delta/s TPS calculation
- InstanceCard: unified metric labels (Connections, TPS/s, Hit Ratio)
- WebSocket: connect to current origin when VITE_WS_URL is empty
- REST fallback: poll latest metrics when WebSocket disconnected

## [0.3.0.0] - 2026-03-25 — Demo Ready

### Added
- **Instance Management Page**: register/list/test/delete PostgreSQL instances with validation form
- **RegisterInstanceModal**: form with host/port/db/credentials + client-side validation
- **NL2SQL Chat Widget**: floating bottom-right panel, natural language → SQL → result table
- **Docker auto-setup**: entrypoint.sh runs migration + seed before uvicorn (one-command startup)
- **SideNav**: Instances menu item added
- Dashboard "인스턴스 등록" now navigates to /instances

### Changed
- Celery workers depend on backend service (ensures migrations complete first)
- psycopg2-binary moved to main dependencies (Alembic sync driver in Docker)

## [0.2.1.0] - 2026-03-25 — Tests + Security Hardening

### Added
- 41 new tests (80 total): audit API, incidents API, schema changes API, baseline analyzer, anomaly detector, RAG service, MTL Lite, baselines API

### Security
- NL2SQL: block dangerous functions (pg_read_file, dblink), sensitive tables (users, audit_logs), multi-statement SQL, enforce SELECT/WITH prefix
- Incidents: add RBAC to update_incident_status (operator+ required)
- NL2SQL: remove PostgreSQL error details from client responses

## [0.2.0.0] - 2026-03-25 — MVP Feature Complete

### Added
- **Audit Log Middleware**: auto-logs POST/PUT/DELETE with WHO/WHAT/WHEN (Spec: FS-ADMIN-003)
- **Incident List API + Page**: severity filter tabs, ACK/Resolve buttons, real-time updates (Spec: FS-DASH-004)
- **AI Auto-Baselining**: STL decomposition + Isolation Forest per time bucket, 6h retrain (Spec: MVP-AI-001)
- **Anomaly Detection**: z-score severity classification, 30-min cooldown, auto incident creation (Spec: MVP-AI-002)
- **NL2SQL**: LangChain LLM (online=GPT-4o, offline=Ollama), write-query rejection, 5s timeout (Spec: FR-AI-003)
- **Lightweight RAG**: sentence-transformers embeddings, pgvector cosine search, Valkey caching (Spec: FR-AI-002)
- **MTL Lite RCA**: 4-head JSON prediction (anomaly/cause/severity/actions), confidence scoring (Spec: FR-AI-010)
- **Schema Change Detection**: information_schema polling every 60s, snapshot diff (Spec: FS-SCHEMA-001)
- **Settings Page**: 4-section card layout with config display (Spec: MVP.md §6)
- **3 new Feature Specs**: AUDIT_LOG_SPEC, INCIDENT_LIST_SPEC, SCHEMA_CHANGE_SPEC

## [0.1.4.0] - 2026-03-25

### Fixed
- Alembic migration: SAVEPOINT wrapping for pgvector/ARRAY type conversions (prevents transaction abort)
- Alembic env.py: sync psycopg2 driver as default (asyncpg segfaults on Windows)
- init.sql: disable pg_partman/pg_stat_statements extensions (not in base Docker image)
- bcrypt 5.x + passlib compatibility patch for runtime (not just tests)
- Login form: use form-urlencoded for OAuth2PasswordRequestForm (was JSON)
- Auth error handling: coerce Pydantic validation error arrays to string
- useInstances hook: parse `{items, total}` paginated response format
- API client: add `postForm()` method for form-urlencoded requests

## [0.1.3.0] - 2026-03-25

### Added
- Initial Alembic migration: 13 MVP tables with indexes, FK cascades, pgvector HNSW (Spec: DM-001, DM-MIG-001)
- Frontend login page with JWT auth, route guards, and localStorage persistence (Spec: MVP-ADMIN-001)
- Zustand auth store with login/logout/refresh actions
- User profile dropdown with sign-out in TopNav
- TanStack Router auth guards: unauthenticated users redirected to /login

## [0.1.2.0] - 2026-03-25

### Added
- User CRUD API (GET/POST/PUT/DELETE /api/v1/users) with super_admin RBAC (Spec: MVP-ADMIN-001)
- Pydantic v2 schemas for User create/update/response validation (Spec: MVP-ADMIN-002)
- Seed script for default admin user (`uv run python -m app.db.seed`) (Spec: MVP-ADMIN-001)
- 32 new API endpoint tests — User CRUD, JWT auth deps, RBAC enforcement (39 total)
- Spec-Test sync hook: auto-detects when Spec/code changes and prompts test regeneration (Spec: TEST-STRATEGY-001)

### Fixed
- Seed admin password moved to env var `SEED_ADMIN_PASSWORD` (was hardcoded)

### Security
- Admin seed credentials no longer embedded in source code

## [0.1.1.0] - 2026-03-25

### Added
- JWT authentication middleware with login, refresh, and /me endpoints (Spec: MVP-ADMIN-001)
- RBAC role-checking dependency (`require_role`) for endpoint authorization (Spec: MVP-ADMIN-002)
- Auth dependency applied to all protected API routers (instances, metrics, ash, alerts)

### Fixed
- "인스턴스 등록" button on dashboard now navigates to Settings page (was no-op)
- Mobile responsive layout — sidebar collapses to icon-only mode on small screens
- WebSocket reconnection limited to 5 attempts when backend unavailable (was infinite)
- WebSocket CORS restricted to configured origins (was wildcard `*`)

### Security
- CSO-001: All API endpoints now require JWT Bearer token authentication
- CSO-002: Socket.io CORS changed from `"*"` to `settings.CORS_ORIGINS`

## [0.1.0.0] - 2026-03-24

### Added
- Initial MVP scaffolding — Backend (FastAPI) + Frontend (React/Vite) + Infrastructure (Docker Compose)
