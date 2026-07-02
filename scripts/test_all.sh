#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# ProxySQL Admin WebUI — 全层级自动化测试
# ──────────────────────────────────────────────────────────
# 用法:
#   bash scripts/test_all.sh              # 运行全部
#   bash scripts/test_all.sh --quick      # 仅 L0-L3 (无需 Docker)
#   bash scripts/test_all.sh --api        # 仅 L4-L5 (需要 Docker + 后端)
# ──────────────────────────────────────────────────────────

set -euo pipefail

# Determine script directory (bash & zsh compatible)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASSED=0
FAILED=0
FAILED_LEVELS=()

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}✅ $1${NC}"; PASSED=$((PASSED + 1)); }
log_fail() { echo -e "${RED}❌ $1${NC}"; FAILED=$((FAILED + 1)); FAILED_LEVELS+=("$1"); }

run_level() {
    local name="$1"; shift
    echo -e "\n${CYAN}═══ ${name} ═══${NC}"
    if "$@"; then
        log_pass "$name"
    else
        log_fail "$name"
    fi
}

# ── Parse args ──────────────────────────────────────
MODE="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick) MODE="quick"; shift ;;
        --api)   MODE="api"; shift ;;
        *) shift ;;
    esac
done

echo -e "${CYAN}ProxySQL Admin WebUI — Automated Test Suite${NC}"
echo "Root: $ROOT_DIR | Mode: $MODE"

# ── L0: Syntax Check ─────────────────────────────────
if [[ "$MODE" == "all" || "$MODE" == "quick" ]]; then
    run_level "L0: Python Syntax Check" python3 "$SCRIPT_DIR/test_l0_syntax.py"
fi

# ── L1: Import Check ─────────────────────────────────
if [[ "$MODE" == "all" || "$MODE" == "quick" ]]; then
    run_level "L1: Python Import Check" python3 "$SCRIPT_DIR/test_l1_imports.py"
fi

# ── L2: Static Analysis ──────────────────────────────
if [[ "$MODE" == "all" || "$MODE" == "quick" ]]; then
    run_level "L2a: Ruff (Python)" bash -c "cd '$ROOT_DIR/backend' && ruff check app/ --select E,F821,F822,F823,F901 --ignore E501"
    run_level "L2b: ESLint (TypeScript)" bash -c "cd '$ROOT_DIR/frontend' && npx eslint . --ext ts,tsx --max-warnings 100 2>&1 | tail -5"
fi

# ── L3: Frontend Build ───────────────────────────────
if [[ "$MODE" == "all" || "$MODE" == "quick" ]]; then
    run_level "L3a: TypeScript Check" bash -c "cd '$ROOT_DIR/frontend' && npx tsc --noEmit"
    run_level "L3b: Vite Build" bash -c "cd '$ROOT_DIR/frontend' && npx vite build --logLevel error"
fi

# ── L4: API Smoke Test ───────────────────────────────
if [[ "$MODE" == "all" || "$MODE" == "api" ]]; then
    run_level "L4: API Smoke Test" python3 "$SCRIPT_DIR/test_l4_api_smoke.py"
fi

# ── L5: Full-Chain Integration ───────────────────────
if [[ "$MODE" == "all" || "$MODE" == "api" ]]; then
    run_level "L5: Full-Chain Integration" python3 "$SCRIPT_DIR/test_l5_integration.py"
fi

# ── Summary ──────────────────────────────────────────
echo -e "\n${CYAN}══════════════════════════════════════════════════${NC}"
TOTAL=$((PASSED + FAILED))
echo -e "Result: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC} ($TOTAL levels)"
if [[ ${#FAILED_LEVELS[@]} -gt 0 ]]; then
    for l in "${FAILED_LEVELS[@]}"; do echo -e "  ${RED}❌ $l${NC}"; done
    exit 1
else
    echo -e "${GREEN}✅ All test levels passed!${NC}"
    exit 0
fi
