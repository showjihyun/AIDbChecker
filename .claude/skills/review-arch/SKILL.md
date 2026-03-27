---
name: review-arch
description: Review code for architecture compliance against the NeuralDB architecture spec v3.0 and PRD v3.1. Checks module boundaries, dependency rules, design pattern adherence, license compliance, and design token consistency.
argument-hint: "[file-or-directory-path]"
allowed-tools: Read, Glob, Grep, Bash
---

# Architecture Compliance Review

You are reviewing code for compliance with the **NeuralDB** architecture specification.

## Arguments
- Target path: $ARGUMENTS (default: entire project)

## Pre-Flight (MUST execute before reviewing)

1. READ `docs/TECH_STACK.md` — extract authorized technology list.
2. READ `AGENTS.md` Section 2 (Task Boundaries) — extract MUST/NEVER rules.
3. READ `AGENTS.md` Section 5 (Code Patterns) — extract Good vs Bad patterns.
4. READ `docs/FRONTEND_DESIGN.md` — extract design token rules (if reviewing frontend).
5. READ `ai-db-monitor-license-audit.jsx` — extract forbidden licenses.
6. GLOB target path — collect all files to review.

## Review Rules (each is a PASS/FAIL gate)

### Gate 1: Spec Reference
- GREP `# Spec:` in every `.py` file under `backend/app/`.
- PASS: file contains `# Spec: {valid-ID}` (FR-, FS-, DM-, AG-, ADR-, MVP-, TEST-).
- FAIL: file has no Spec reference (exclude `__init__.py`).
- SEVERITY: Warning.

### Gate 2: Module Boundaries
- GREP import statements in target files.
- PASS: frontend does NOT import from backend.
- PASS: backend does NOT import from frontend.
- PASS: no circular imports between `app/services/` ↔ `app/api/`.
- PASS: agents communicate via defined interfaces, not direct DB access.
- FAIL: any cross-boundary import detected.
- SEVERITY: Critical.

### Gate 3: License Compliance
- READ `pyproject.toml` dependencies and `package.json` dependencies.
- FAIL if any dependency uses: GPL, AGPL, SSPL, RSALv2, TSL, EUPL, CPAL, OSL.
- PASS: all deps are MIT, Apache 2.0, BSD, ISC, PostgreSQL License, PSF, or commercial SaaS.
- CHECK these specific forbidden patterns:
  - `grafana` → AGPL v3
  - `timescaledb` / `time_bucket` / `create_hypertable` → TSL
  - `redis` server 7.4+ modules (RedisJSON, RediSearch) → RSALv2
  - `next/link` / `getServerSideProps` → Next.js pattern (React SPA only)
- SEVERITY: Critical.

### Gate 4: Python Code Patterns
- GREP for forbidden patterns:
  - `pip install` → FAIL (use `uv add`)
  - `requirements.txt` → FAIL (use `pyproject.toml`)
  - `from sqlalchemy import Column` → FAIL (use `Mapped`, `mapped_column` — SQLAlchemy 2.0)
  - `session.query(` → FAIL (use `select()` — SQLAlchemy 2.0)
  - `.filter(` after `session.query` → FAIL
  - `redis.Redis(host=` → FAIL (use `aioredis.from_url(settings.VALKEY_URL)`)
  - `SERIAL` in SQL → FAIL (use UUID)
  - `TIMESTAMP` without `TZ` → FAIL (use TIMESTAMPTZ)
  - `OFFSET` in pagination → FAIL (use cursor-based)
  - `openai.ChatCompletion.create` → FAIL (use LangChain abstraction)
  - `await execute(action)` without `AUTONOMY_CHECK` → FAIL
- SEVERITY: each violation is Critical or Warning as marked in AGENTS.md.

### Gate 5: Frontend Code Patterns
- GREP for forbidden patterns (if reviewing frontend):
  - `from 'next/` → FAIL (React SPA, no Next.js)
  - `getServerSideProps` / `getStaticProps` → FAIL
  - `bg-black` / `#000000` → FAIL (use design tokens)
  - `border border-gray` → FAIL (No-Line Rule)
  - Hardcoded colors not in FRONTEND_DESIGN.md palette → Warning
- SEVERITY: Warning.

### Gate 6: Security
- GREP for security violations:
  - `password` or `secret` or `api_key` in `.py` string literals → FAIL (use settings/env).
  - `.env` committed (check `.gitignore`) → FAIL.
  - SQL string concatenation (`f"SELECT ... {var}"`) → FAIL (use parameterized).
  - Missing `Depends(get_current_user)` on protected routes → FAIL.
  - Missing `require_role()` on admin endpoints → Warning.
- SEVERITY: Critical.

### Gate 7: Data Patterns
- GREP model files for compliance:
  - Primary key type is `UUID` → PASS.
  - `SERIAL` / `INTEGER` PK → FAIL.
  - `DateTime(timezone=True)` or `TIMESTAMPTZ` → PASS.
  - `DateTime()` without timezone → FAIL.
  - Partitioned tables have `(id, partition_key)` composite PK → PASS.
  - `created_at` and `updated_at` present on all tables → PASS.
- SEVERITY: Warning.

### Gate 8: Observability
- CHECK: `structlog.get_logger` used (not `logging.getLogger` or `print`).
- CHECK: `prometheus-fastapi-instrumentator` in deps and instrumented.
- CHECK: `/metrics` endpoint exposed.
- CHECK: `/api/v1/system/health` endpoint exists.
- SEVERITY: Warning.

### Gate 9: ADR Compliance
- For each ADR in `docs/ADR/*.md`:
  - VERIFY the decision is reflected in code (not contradicted).
  - ADR-001: No NestJS/TypeORM imports.
  - ADR-002: No TimescaleDB functions.
  - ADR-003: Valkey env var, no Redis module imports.
  - ADR-008: Playbook Lite only (no L3/L4 in Phase 2 code).
  - ADR-009: LangChain via LLMProviderManager (no direct openai.* calls).
- SEVERITY: Critical.

## Output Format

Produce a structured report:

```markdown
# Architecture Review Report — {target_path}
Date: {date}

## Summary
| Gate | Status | Violations |
|------|--------|------------|
| 1. Spec Reference | PASS/FAIL | N |
| 2. Module Boundaries | PASS/FAIL | N |
| ...

## Violations Detail
### [CRITICAL] Gate 3: License — grafana dependency
- File: package.json:15
- Rule: No AGPL dependencies
- Fix: Remove grafana, use React + ECharts

### [WARNING] Gate 1: Spec Reference — missing
- File: backend/app/utils/helpers.py
- Rule: All .py files must have # Spec: comment
- Fix: Add `# Spec: AG-001` header

## Score: {passed}/{total} gates passed
## Risk Level: {LOW|MEDIUM|HIGH|CRITICAL}
```

## Post-Review (MUST execute)

1. COUNT total violations by severity.
2. IF Critical > 0: recommend blocking merge.
3. IF Warning > 3: recommend review before merge.
4. REPORT score and risk level.
