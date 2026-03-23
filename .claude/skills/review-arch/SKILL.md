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

## Reference Documents
1. Read `ai-db-monitor-architecture-spec-v3.md` for architecture rules
2. Read `AI_DB_Monitoring_System_PRD_v3.1.md` for requirements
3. Read `ai-db-monitor-license-audit.jsx` for license compliance
4. Read `docs/FRONTEND_DESIGN.md` for design system compliance

## Review Checklist

### 1. Module Boundaries
- [ ] Each module has clear responsibility (single purpose)
- [ ] No circular dependencies between modules
- [ ] Communication between layers follows: Frontend → Backend → Engine
- [ ] Inter-agent communication uses MCP/A2A protocols only

### 2. Dependency Rules
- [ ] Frontend does NOT import from backend or engine
- [ ] Backend does NOT import from frontend
- [ ] Engine does NOT import from frontend or backend
- [ ] Shared types are in a common/shared package

### 3. License Compliance
- [ ] No AGPL dependencies (Grafana)
- [ ] No SSPL/RSALv2 dependencies (Redis 7.4+)
- [ ] No TSL dependencies (TimescaleDB)
- [ ] All dependencies are MIT, Apache 2.0, BSD, or PostgreSQL License

### 4. Design System Compliance (Frontend)
- [ ] Uses design tokens from FRONTEND_DESIGN.md (not hardcoded colors)
- [ ] No 1px solid borders for section dividers
- [ ] No pure black (#000000) backgrounds
- [ ] Typography follows dual-font strategy (Space Grotesk + Inter)
- [ ] Glassmorphism used for floating/modal elements
- [ ] Transitions use `ease-out` only

### 5. Security
- [ ] No hardcoded credentials or API keys
- [ ] SQL queries use parameterized statements
- [ ] Input validation on all external boundaries
- [ ] RBAC checks on all protected endpoints
- [ ] Audit logging for state-changing operations

### 6. Observability
- [ ] OpenTelemetry instrumentation on API endpoints
- [ ] Structured logging (not console.log/print)
- [ ] Health check endpoints exist
- [ ] Metrics exported for Prometheus

### 7. Data Patterns
- [ ] UUID v7 for primary keys
- [ ] Cursor-based pagination (not offset)
- [ ] JSONB for flexible metadata fields
- [ ] Time-series data uses table partitioning
- [ ] All tables have created_at/updated_at

## Output Format
Produce a report with:
1. **PASS/FAIL** summary per category
2. **Violations** with file path, line number, and description
3. **Recommendations** for fixing each violation
4. **Risk Level** (Critical / Warning / Info) per violation
