#!/bin/bash
#
# Run E2E tests for the ProxySQL Admin WebUI.
#
# Usage:
#   ./scripts/run_e2e_tests.sh           # Run all tests (headless)
#   ./scripts/run_e2e_tests.sh --headed   # Run tests with browser visible
#   ./scripts/run_e2e_tests.sh --ui       # Run tests with Playwright UI mode
#
# Prerequisites:
#   - Node.js 18+ installed
#   - Backend running at http://localhost:8000 (or tests will use mocked API responses)
#   - Frontend dev server will be auto-started by Playwright
#
# The tests use page.route() to mock API responses, so they can run
# independently of a real backend. However, for full integration testing,
# start the backend first.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "=== ProxySQL Admin WebUI E2E Test Runner ==="
echo ""

# Navigate to frontend directory
cd "$FRONTEND_DIR"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
  echo "Installing npm dependencies..."
  npm install
fi

# Check if Playwright browsers are installed
if [ ! -d "$HOME/.cache/ms-playwright" ] && [ ! -d "/ms-playwright" ]; then
  echo "Installing Playwright browsers..."
  npx playwright install chromium
  echo ""
fi

# Parse arguments
MODE="headless"
EXTRA_ARGS=""

for arg in "$@"; do
  case "$arg" in
    --headed)
      MODE="headed"
      EXTRA_ARGS="--headed"
      ;;
    --ui)
      MODE="ui"
      EXTRA_ARGS="--ui"
      ;;
    --debug)
      MODE="debug"
      EXTRA_ARGS="--debug"
      ;;
    *)
      EXTRA_ARGS="$EXTRA_ARGS $arg"
      ;;
  esac
done

echo "Running E2E tests in $MODE mode..."
echo ""

if [ "$MODE" = "ui" ]; then
  npx playwright test --ui $EXTRA_ARGS
else
  npx playwright test $EXTRA_ARGS
fi

echo ""
echo "=== E2E tests completed ==="
