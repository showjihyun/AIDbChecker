# Changelog

All notable changes to this project will be documented in this file.

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
