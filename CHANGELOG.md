# Changelog

All notable changes to this project will be documented in this file.

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
