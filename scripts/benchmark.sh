#!/usr/bin/env bash
# ── ProxySQL Admin WebUI Performance Benchmark ────────────────────────────
# Measures endpoint response times to track performance improvements.
# Usage:
#   ./scripts/benchmark.sh [BASE_URL]
#
# Requirements:
#   - curl (for basic testing)
#   - ab (Apache Bench, optional, for load testing)
#
# Example:
#   ./scripts/benchmark.sh http://localhost:8080
#   ./scripts/benchmark.sh http://localhost:8080 | tee results.txt
# ──────────────────────────────────────────────────────────────────────────

set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
LOGIN_URL="${BASE_URL}/api/v1/auth/login"
HEALTH_URL="${BASE_URL}/api/v1/health"
DASHBOARD_URL="${BASE_URL}/api/v1/dashboard/snapshot"
WIZARDS_URL="${BASE_URL}/api/v1/wizards/definitions"
TABLES_URL="${BASE_URL}/api/v1/tables"
SERVERS_URL="${BASE_URL}/api/v1/servers"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ── Configuration ────────────────────────────────────────────────────────
CREDENTIALS='{"username":"admin","password":"admin123"}'
TOTAL_REQUESTS=50
CONCURRENCY=5

# ── Helper Functions ─────────────────────────────────────────────────────

time_endpoint() {
    local method="${1:-GET}"
    local url="$2"
    local data="${3:-}"
    local label="$4"

    printf "${CYAN}%-45s${NC} " "[$method] $label"
    local start_ms end_ms elapsed
    start_ms=$(date +%s%3N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1000))')

    local http_code
    if [ "$method" = "POST" ] || [ "$method" = "PUT" ]; then
        http_code=$(curl -s -o /dev/null -w "%{http_code}" \
            -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -d "$data" 2>/dev/null)
    else
        http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
    fi

    end_ms=$(date +%s%3N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1000))')
    elapsed=$((end_ms - start_ms))

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 400 ]; then
        printf "${GREEN}%3dms${NC} (HTTP %s)\n" "$elapsed" "$http_code"
    else
        printf "${RED}%3dms${NC} (HTTP %s)\n" "$elapsed" "$http_code"
    fi
}

# ── Main ─────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  ProxySQL Admin WebUI - Performance Benchmark"
echo "  Target: ${BASE_URL}"
echo "  Date:   $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════════════"
echo ""

# ── Section 1: Single-Request Latency ────────────────────────────────────
echo "┌── Single Request Latency (warm-up + measure) ──────────────────────┐"
echo "│  Each endpoint is called twice: first warms caches, second shows  │"
echo "│  the cached response time.                                        │"
echo "└────────────────────────────────────────────────────────────────────┘"
echo ""

# Health (no auth)
time_endpoint "GET" "$HEALTH_URL" "" "Health Check (warm)"
time_endpoint "GET" "$HEALTH_URL" "" "Health Check (cached)"

# Login
time_endpoint "POST" "$LOGIN_URL" "$CREDENTIALS" "Login (warm)"
time_endpoint "POST" "$LOGIN_URL" "$CREDENTIALS" "Login (cached)"

# Get auth token for authenticated endpoints
TOKEN=$(curl -s -X POST "$LOGIN_URL" \
    -H "Content-Type: application/json" \
    -d "$CREDENTIALS" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
    AUTH_HEADER="Authorization: Bearer $TOKEN"

    # Authenticated endpoints
    time_endpoint "GET" "$DASHBOARD_URL" "" "Dashboard Snapshot (warm)"
    time_endpoint "GET" "$DASHBOARD_URL" "" "Dashboard Snapshot (cached)"

    time_endpoint "GET" "$WIZARDS_URL" "" "Wizard Definitions (warm)"
    time_endpoint "GET" "$WIZARDS_URL" "" "Wizard Definitions (cached)"

    time_endpoint "GET" "$TABLES_URL" "" "Tables List (warm)"
    time_endpoint "GET" "$TABLES_URL" "" "Tables List (cached)"

    time_endpoint "GET" "$SERVERS_URL" "" "Servers List (warm)"
    time_endpoint "GET" "$SERVERS_URL" "" "Servers List (cached)"
else
    echo ""
    printf "${YELLOW}Warning: Could not obtain auth token.${NC}\n"
    printf "${YELLOW}Ensure the server is running and credentials are correct.${NC}\n"
    printf "${YELLOW}Authenticated endpoints will be skipped.${NC}\n"
    echo ""
fi

echo ""
echo "────────────────────────────────────────────────────────────────────"
echo ""

# ── Section 2: Load Test (if ab is available) ────────────────────────────
if command -v ab &> /dev/null; then
    echo "┌── Load Test (Apache Bench) ───────────────────────────────────────┐"
    echo "│  ${TOTAL_REQUESTS} requests, ${CONCURRENCY} concurrent                           │"
    echo "└────────────────────────────────────────────────────────────────────┘"
    echo ""

    echo "--- Health Check ---"
    ab -n "$TOTAL_REQUESTS" -c "$CONCURRENCY" "$HEALTH_URL" 2>&1 | grep -E "(Requests per second|Time per request|Failed requests|Transfer rate)"

    if [ -n "$TOKEN" ]; then
        echo ""
        echo "--- Dashboard Snapshot ---"
        ab -n "$TOTAL_REQUESTS" -c "$CONCURRENCY" -H "$AUTH_HEADER" "$DASHBOARD_URL" 2>&1 | grep -E "(Requests per second|Time per request|Failed requests|Transfer rate)"

        echo ""
        echo "--- Wizard Definitions ---"
        ab -n "$TOTAL_REQUESTS" -c "$CONCURRENCY" -H "$AUTH_HEADER" "$WIZARDS_URL" 2>&1 | grep -E "(Requests per second|Time per request|Failed requests|Transfer rate)"
    fi
else
    echo "Apache Bench (ab) not found. Install with: apt-get install apache2-utils"
    echo "Skipping load test section."
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  Benchmark complete."
echo "════════════════════════════════════════════════════════════════════"
echo ""
