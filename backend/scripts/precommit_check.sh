#!/bin/bash
# Spec: FS-HARNESS-001 — 4-Pillar Pre-Commit Quality Gate (v2 — improved)
#
# Improvements over v1:
#   1. Pillar 3: affected tests only (not full suite) → ~3s instead of ~18s
#   2. Pillar 2: mypy warns only (no block) — existing code has incomplete types
#   3. Multi-agent safe: only checks STAGED files, ignores unstaged changes
#   4. Full test suite runs at /ship time, not every commit
#
# Exit codes:
#   0 = all pillars passed
#   1 = pillar 1 or 3 failed (commit blocked)

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
TOTAL_TIME_START=$(date +%s)

# Detect staged files
cd "$ROOT_DIR"
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACMR -- '*.py' | grep '^backend/' || true)
STAGED_FE=$(git diff --cached --name-only --diff-filter=ACMR | grep '^frontend/src/' || true)

# ============================================================
# Pillar 1: CONSTRAINT (Lint + Format) — BLOCKS on error
# ============================================================
echo -e "${BLUE}[1/4] CONSTRAINT (Lint)${NC}"

STAGED_APP_PY=$(echo "$STAGED_PY" | grep '^backend/app/' || true)
if [ -n "$STAGED_APP_PY" ]; then
    cd "$BACKEND_DIR"
    CHECK_FILES=$(echo "$STAGED_APP_PY" | sed 's|^backend/||')

    # Auto-fix + re-stage
    echo "$CHECK_FILES" | xargs uv run ruff check --fix --quiet 2>/dev/null
    echo "$CHECK_FILES" | xargs uv run ruff format --quiet 2>/dev/null
    cd "$ROOT_DIR"
    echo "$STAGED_APP_PY" | xargs -r git add 2>/dev/null

    # Final check
    cd "$BACKEND_DIR"
    LINT_OUT=$(echo "$CHECK_FILES" | xargs uv run ruff check --quiet 2>&1)
    if [ $? -ne 0 ]; then
        echo "$LINT_OUT" | head -10
        echo -e "${RED}  FAIL: lint errors remain after auto-fix${NC}"
        FAILED=1
    else
        FILE_COUNT=$(echo "$STAGED_APP_PY" | wc -l | tr -d ' ')
        echo -e "${GREEN}  PASS ($FILE_COUNT files)${NC}"
    fi
else
    echo -e "${GREEN}  SKIP (no staged app/*.py)${NC}"
fi

# ============================================================
# Pillar 2: CONTEXT (Type Check) — WARNS only (no block)
# ============================================================
echo -e "${BLUE}[2/4] CONTEXT (Type Check)${NC}"

if [ -n "$STAGED_APP_PY" ]; then
    cd "$BACKEND_DIR"
    MYPY_OUT=$(echo "$CHECK_FILES" | xargs uv run mypy --ignore-missing-imports --no-error-summary --no-color 2>&1)
    MYPY_EXIT=$?
    if [ $MYPY_EXIT -ne 0 ]; then
        echo "$MYPY_OUT" | head -5
        echo -e "${YELLOW}  WARN: type issues (not blocking — fix before /ship)${NC}"
        # NOT setting FAILED=1 — warn only
    else
        echo -e "${GREEN}  PASS${NC}"
    fi
else
    echo -e "${GREEN}  SKIP${NC}"
fi

# Frontend TypeScript — dev/staging: warn only on staged files
# Full tsc check deferred to /ship (production gate)
cd "$ROOT_DIR"
if [ -n "$STAGED_FE" ]; then
    cd "$FRONTEND_DIR"
    TSC_OUT=$(npx tsc --noEmit 2>&1)
    if [ $? -ne 0 ]; then
        # Filter errors to staged files only
        STAGED_ERRORS=""
        for f in $STAGED_FE; do
            MATCH=$(echo "$TSC_OUT" | grep "$(basename "$f")" || true)
            if [ -n "$MATCH" ]; then
                STAGED_ERRORS="$STAGED_ERRORS$MATCH\n"
            fi
        done
        if [ -n "$STAGED_ERRORS" ]; then
            echo -e "$STAGED_ERRORS" | head -5
            echo -e "${YELLOW}  WARN: TypeScript issues in staged files (not blocking — fix before /ship)${NC}"
        else
            echo -e "${GREEN}  PASS (staged files clean, pre-existing errors in other files)${NC}"
        fi
        # NOT setting FAILED=1 — dev/staging is warn only
    else
        echo -e "${GREEN}  PASS (TypeScript)${NC}"
    fi
fi

# ============================================================
# Pillar 3: VERIFICATION (Affected Tests Only) — BLOCKS on failure
# ============================================================
echo -e "${BLUE}[3/4] VERIFICATION (Tests)${NC}"

if [ -n "$STAGED_PY" ]; then
    cd "$BACKEND_DIR"

    # Find test files that correspond to staged source files
    # Strategy: for each staged backend/app/X/Y.py, look for tests/unit/test_*Y*.py
    AFFECTED_TESTS=""
    for src in $STAGED_PY; do
        basename=$(basename "$src" .py)
        # Skip __init__, conftest, etc.
        if [[ "$basename" == "__init__" || "$basename" == "conftest" ]]; then
            continue
        fi
        # Find matching test files
        matches=$(find tests/unit -name "test_*${basename}*" -name "*.py" 2>/dev/null | head -3)
        if [ -n "$matches" ]; then
            AFFECTED_TESTS="$AFFECTED_TESTS $matches"
        fi
    done

    # Also include staged test files directly
    STAGED_TESTS=$(echo "$STAGED_PY" | grep '^backend/tests/' | sed 's|^backend/||' || true)
    AFFECTED_TESTS="$AFFECTED_TESTS $STAGED_TESTS"

    # Deduplicate
    AFFECTED_TESTS=$(echo "$AFFECTED_TESTS" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' ')

    if [ -n "$AFFECTED_TESTS" ]; then
        TEST_COUNT=$(echo "$AFFECTED_TESTS" | wc -w | tr -d ' ')
        PYTEST_OUT=$(uv run pytest $AFFECTED_TESTS -x --tb=short -q --no-header 2>&1)
        PYTEST_EXIT=$?
        echo "$PYTEST_OUT" | tail -3
        if [ $PYTEST_EXIT -ne 0 ]; then
            echo -e "${RED}  FAIL: test failures in affected files${NC}"
            FAILED=1
        else
            echo -e "${GREEN}  PASS ($TEST_COUNT test files, affected only)${NC}"
        fi
    else
        echo -e "${GREEN}  SKIP (no matching test files for staged changes)${NC}"
    fi
else
    echo -e "${GREEN}  SKIP (no staged Python files)${NC}"
fi

# Frontend tests (only if frontend staged)
cd "$ROOT_DIR"
if [ -n "$STAGED_FE" ]; then
    cd "$FRONTEND_DIR"
    VT_OUT=$(npx vitest run --reporter=dot 2>&1)
    if [ $? -ne 0 ]; then
        echo "$VT_OUT" | tail -3
        echo -e "${RED}  FAIL: frontend tests${NC}"
        FAILED=1
    else
        echo -e "${GREEN}  PASS (Vitest)${NC}"
    fi
fi

# ============================================================
# Pillar 4: FEEDBACK (AC Dashboard) — INFO only, never blocks
# ============================================================
echo -e "${BLUE}[4/4] FEEDBACK (AC Dashboard)${NC}"
cd "$BACKEND_DIR"
DASH_OUT=$(uv run python -m scripts.spec_dashboard 2>/dev/null | grep -E "TOTAL|Specs complete|Next" | head -3)
echo "$DASH_OUT"

# ============================================================
# Result
# ============================================================
TOTAL_TIME_END=$(date +%s)
ELAPSED=$((TOTAL_TIME_END - TOTAL_TIME_START))

echo ""
if [ $FAILED -ne 0 ]; then
    echo -e "${RED}BLOCKED (${ELAPSED}s) — fix errors above and retry${NC}"
    exit 1
fi

echo -e "${GREEN}PASSED (${ELAPSED}s) — commit allowed${NC}"
exit 0
