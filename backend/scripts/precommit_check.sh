#!/bin/bash
# Spec: FS-HARNESS-001 — 4-Pillar Pre-Commit Quality Gate
# Runs: Constraint (lint) → Context (type) → Verification (test) → Feedback (AC)
#
# Exit codes:
#   0 = all pillars passed
#   1 = pillar 1-3 failed (commit blocked)
#
# Auto-fix: Pillar 1 runs ruff --fix automatically. If changes are made,
# they are staged and the check continues.

set -o pipefail

# Ensure uv/npm are in PATH (git hooks may have minimal PATH)
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export PATH="/c/Users/$USER/.local/bin:$PATH"

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

FAILED=0

# ============================================================
# Pillar 1: CONSTRAINT (Lint + Format)
# ============================================================
echo -e "${BLUE}🔍 Pillar 1: CONSTRAINT (Lint)${NC}"

cd "$BACKEND_DIR" || exit 1

# Only check STAGED Python files (incremental lint — don't block on existing issues)
cd "$ROOT_DIR"
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACMR -- '*.py' | grep '^backend/app/' || true)

if [ -n "$STAGED_PY" ]; then
    cd "$BACKEND_DIR"
    # Convert paths: backend/app/foo.py → app/foo.py
    CHECK_FILES=$(echo "$STAGED_PY" | sed 's|^backend/||')

    # Auto-fix lint issues on staged files only
    echo "$CHECK_FILES" | xargs uv run ruff check --fix --quiet 2>/dev/null
    echo "$CHECK_FILES" | xargs uv run ruff format --quiet 2>/dev/null

    # Re-stage auto-fixed files
    cd "$ROOT_DIR"
    echo "$STAGED_PY" | xargs -r git add 2>/dev/null

    # Final lint check on staged files
    cd "$BACKEND_DIR"
    LINT_OUTPUT=$(echo "$CHECK_FILES" | xargs uv run ruff check --quiet 2>&1)
    if [ $? -ne 0 ]; then
        echo "$LINT_OUTPUT" | head -10
        echo -e "${RED}  ❌ Pillar 1 FAILED: lint errors in staged files${NC}"
        FAILED=1
    else
        echo -e "${GREEN}  ✅ Pillar 1 PASSED ($(echo "$STAGED_PY" | wc -l) files checked)${NC}"
    fi
else
    echo -e "${GREEN}  ✅ Pillar 1 SKIPPED (no staged Python files)${NC}"
fi

# ============================================================
# Pillar 2: CONTEXT (Type Check)
# ============================================================
echo -e "${BLUE}🔍 Pillar 2: CONTEXT (Type Check)${NC}"

if [ -n "$STAGED_PY" ]; then
    cd "$BACKEND_DIR"
    # Type check staged files only
    MYPY_OUTPUT=$(echo "$CHECK_FILES" | xargs uv run mypy --ignore-missing-imports --no-error-summary --no-color 2>&1)
    MYPY_EXIT=$?

    if [ $MYPY_EXIT -ne 0 ]; then
        echo "$MYPY_OUTPUT" | head -10
        echo -e "${RED}  ❌ Pillar 2 FAILED: type errors in staged files${NC}"
        FAILED=1
    else
        echo -e "${GREEN}  ✅ Pillar 2 PASSED${NC}"
    fi
else
    echo -e "${GREEN}  ✅ Pillar 2 SKIPPED (no staged Python files)${NC}"
fi

# Frontend type check (if frontend files staged)
cd "$ROOT_DIR"
if git diff --cached --name-only | grep -q "^frontend/"; then
    echo -e "${BLUE}  TypeScript check...${NC}"
    cd "$FRONTEND_DIR"
    npx tsc --noEmit 2>&1 | head -10
    if [ $? -ne 0 ]; then
        echo -e "${RED}  ❌ Pillar 2 FAILED: TypeScript errors${NC}"
        FAILED=1
    else
        echo -e "${GREEN}  ✅ TypeScript PASSED${NC}"
    fi
fi

# ============================================================
# Pillar 3: VERIFICATION (Tests)
# ============================================================
echo -e "${BLUE}🔍 Pillar 3: VERIFICATION (Tests)${NC}"

cd "$BACKEND_DIR"
uv run pytest tests/unit/ -x --tb=short -q --no-header 2>&1 | tail -5
PYTEST_EXIT=${PIPESTATUS[0]}

if [ $PYTEST_EXIT -ne 0 ]; then
    echo -e "${RED}  ❌ Pillar 3 FAILED: test failures${NC}"
    FAILED=1
else
    echo -e "${GREEN}  ✅ Pillar 3 PASSED${NC}"
fi

# Frontend tests (if frontend files staged)
cd "$ROOT_DIR"
if git diff --cached --name-only | grep -q "^frontend/"; then
    echo -e "${BLUE}  Vitest check...${NC}"
    cd "$FRONTEND_DIR"
    npx vitest run --reporter=dot 2>&1 | tail -3
    if [ $? -ne 0 ]; then
        echo -e "${RED}  ❌ Pillar 3 FAILED: frontend test failures${NC}"
        FAILED=1
    fi
fi

# ============================================================
# Pillar 4: FEEDBACK (AC Dashboard — info only, never blocks)
# ============================================================
echo -e "${BLUE}📊 Pillar 4: FEEDBACK (AC Dashboard)${NC}"

cd "$BACKEND_DIR"
uv run python -m scripts.spec_dashboard 2>/dev/null | grep -E "TOTAL|Specs complete|Next" | head -3
echo ""

# ============================================================
# Result
# ============================================================
if [ $FAILED -ne 0 ]; then
    echo -e "${RED}❌ Pre-commit check FAILED — fix errors above and retry${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All 4 pillars passed — commit allowed${NC}"
exit 0
