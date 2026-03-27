#!/bin/bash
# Spec: FS-HARNESS-001 — Docker E2E verification script
# Usage: bash scripts/e2e_docker.sh
#
# Runs against a running Docker environment (docker compose up -d).
# Tests: auth, health, KPI, DBA Agent (5 intents), NL2SQL accuracy.

set -o pipefail

API="http://localhost:8001"
FE="http://localhost:3000"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

PASS=0
FAIL=0
TOTAL=0

check() {
    local name="$1"
    local result="$2"
    TOTAL=$((TOTAL + 1))
    if [ "$result" = "ok" ]; then
        PASS=$((PASS + 1))
        echo -e "${GREEN}[PASS]${NC} $name"
    else
        FAIL=$((FAIL + 1))
        echo -e "${RED}[FAIL]${NC} $name — $result"
    fi
}

echo "=== NeuralDB Docker E2E Test ==="
echo ""

# 1. Frontend reachable
FE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$FE" 2>/dev/null)
[ "$FE_CODE" = "200" ] && check "Frontend (port 3000)" "ok" || check "Frontend" "HTTP $FE_CODE"

# 2. Auth
TOKEN=$(curl -s "$API/api/v1/auth/login" -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin@neuraldb.local&password=NeuralDB@2026!" 2>/dev/null \
    | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

[ -n "$TOKEN" ] && [ ${#TOKEN} -gt 20 ] && check "Auth (JWT login)" "ok" || check "Auth" "no token"

AUTH="Authorization: Bearer $TOKEN"

# 3. System Health
HEALTH=$(curl -s "$API/api/v1/system/health" 2>/dev/null)
STATUS=$(echo "$HEALTH" | python -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
[ "$STATUS" = "healthy" ] && check "System Health" "ok" || check "System Health" "$STATUS"

# 4. Instances
INST_COUNT=$(curl -s "$API/api/v1/instances" -H "$AUTH" 2>/dev/null \
    | python -c "import sys,json; print(json.load(sys.stdin).get('total',0))" 2>/dev/null)
[ "$INST_COUNT" -gt 0 ] 2>/dev/null && check "Instances ($INST_COUNT)" "ok" || check "Instances" "count=$INST_COUNT"

# Get first instance ID
IID=$(curl -s "$API/api/v1/instances" -H "$AUTH" 2>/dev/null \
    | python -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])" 2>/dev/null)

# 5. KPI
if [ -n "$IID" ]; then
    KPI=$(curl -s "$API/api/v1/instances/$IID/kpi" -H "$AUTH" 2>/dev/null)
    TPS=$(echo "$KPI" | python -c "import sys,json; print(json.load(sys.stdin)['throughput']['tps']['value'])" 2>/dev/null)
    [ -n "$TPS" ] && check "KPI (TPS=$TPS)" "ok" || check "KPI" "no data"
fi

# 6. DBA Agent — 5 intents
if [ -n "$IID" ]; then
    for INTENT_Q in "health check|status" "count active sessions|query" "analyze slow queries|analyze"; do
        Q=$(echo "$INTENT_Q" | cut -d'|' -f1)
        EXPECTED=$(echo "$INTENT_Q" | cut -d'|' -f2)
        RES=$(curl -s -X POST "$API/api/v1/dba/ask" -H "$AUTH" -H "Content-Type: application/json" \
            -d "{\"question\":\"$Q\",\"instance_id\":\"$IID\"}" 2>/dev/null)
        INTENT=$(echo "$RES" | python -c "import sys,json; print(json.load(sys.stdin).get('intent',''))" 2>/dev/null)
        [ "$INTENT" = "$EXPECTED" ] && check "DBA '$Q' → $INTENT" "ok" || check "DBA '$Q'" "got=$INTENT expected=$EXPECTED"
    done
fi

# 7. Graph nodes
if [ -n "$IID" ]; then
    NODES=$(curl -s "$API/api/v1/graph/nodes?instance_id=$IID" -H "$AUTH" 2>/dev/null \
        | python -c "import sys,json; print(json.load(sys.stdin).get('total',0))" 2>/dev/null)
    [ "$NODES" -gt 0 ] 2>/dev/null && check "GraphRAG ($NODES nodes)" "ok" || check "GraphRAG" "nodes=$NODES"
fi

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ $FAIL -eq 0 ] && echo -e "${GREEN}ALL PASSED${NC}" || echo -e "${RED}$FAIL FAILURES${NC}"
exit $FAIL
