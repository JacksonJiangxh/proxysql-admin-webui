#!/usr/bin/env bash
# run_integration_tests.sh
# =========================
# Orchestrates the integration test suite:
#   1. Starts the Docker Compose test environment
#   2. Waits for all services to be healthy
#   3. Runs the integration tests via pytest
#   4. Stops and cleans up
#
# Usage:
#   ./scripts/run_integration_tests.sh
#
# Environment variables:
#   FERNET_KEY  - Required. Generate with:
#                 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   TEST_MARKER - Optional. pytest marker to filter tests (e.g. "asyncio")
#   TEST_VERBOSE - Set to "1" for verbose output

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Configuration ──────────────────────────────────

: "${FERNET_KEY:?FERNET_KEY environment variable is required. Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"}"
: "${TEST_MARKER:=}"
: "${TEST_VERBOSE:=1}"

DOCKER_COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.test.yml"
COMPOSE_PROJECT_NAME="proxysql-admin-webui-test"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} ProxySQL Admin WebUI - Integration Tests ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ── Cleanup on exit ───────────────────────────────

cleanup() {
    echo ""
    echo -e "${YELLOW}[cleanup] Stopping test environment...${NC}"
    cd "$PROJECT_DIR"
    FERNET_KEY="$FERNET_KEY" docker compose \
        -f "$DOCKER_COMPOSE_FILE" \
        -p "$COMPOSE_PROJECT_NAME" \
        down --volumes --remove-orphans 2>/dev/null || true
    echo -e "${GREEN}[cleanup] Done.${NC}"
}

trap cleanup EXIT INT TERM

# ── Start test environment ────────────────────────

echo -e "${YELLOW}[step 1/4] Starting Docker Compose test environment...${NC}"
cd "$PROJECT_DIR"
FERNET_KEY="$FERNET_KEY" docker compose \
    -f "$DOCKER_COMPOSE_FILE" \
    -p "$COMPOSE_PROJECT_NAME" \
    up -d --build --force-recreate

# ── Wait for services ─────────────────────────────

echo -e "${YELLOW}[step 2/4] Waiting for services to be healthy...${NC}"

MAX_WAIT=60
WAIT_INTERVAL=3
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8080/api/v1/health > /dev/null 2>&1; then
        echo -e "${GREEN}  [OK] proxysql-admin-webui is healthy (http://localhost:8080/api/v1/health)${NC}"
        break
    fi
    echo "  Waiting... (${ELAPSED}s / ${MAX_WAIT}s)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo -e "${RED}[ERROR] Services did not become healthy within ${MAX_WAIT}s${NC}"
    echo "Docker logs:"
    FERNET_KEY="$FERNET_KEY" docker compose \
        -f "$DOCKER_COMPOSE_FILE" \
        -p "$COMPOSE_PROJECT_NAME" \
        logs --tail=50
    exit 1
fi

# Give services a moment to fully stabilize
sleep 2

# ── Run integration tests ─────────────────────────

echo ""
echo -e "${YELLOW}[step 3/4] Running integration tests...${NC}"

cd "$PROJECT_DIR/backend"

PYTEST_ARGS="-v --tb=short"

if [ "${TEST_VERBOSE}" = "1" ]; then
    PYTEST_ARGS="$PYTEST_ARGS -s"
fi

if [ -n "${TEST_MARKER}" ]; then
    PYTEST_ARGS="$PYTEST_ARGS -m ${TEST_MARKER}"
fi

# Run the integration tests (these use the mock server, not Docker services)
echo "  Running: python -m pytest tests/integration/ $PYTEST_ARGS"
echo ""

set +e
python -m pytest tests/integration/ $PYTEST_ARGS
TEST_EXIT_CODE=$?
set -e

# ── Report results ─────────────────────────────────

echo ""
echo -e "${GREEN}========================================${NC}"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN} ALL INTEGRATION TESTS PASSED${NC}"
else
    echo -e "${RED} INTEGRATION TESTS FAILED (exit code: $TEST_EXIT_CODE)${NC}"
fi
echo -e "${GREEN}========================================${NC}"

# ── Cleanup happens in trap ───────────────────────

exit $TEST_EXIT_CODE
