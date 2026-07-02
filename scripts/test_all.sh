#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# ProxySQL Admin WebUI — 全层级自动化测试 v2
# ──────────────────────────────────────────────────────────
# 用法:
#   bash scripts/test_all.sh              # 运行全部 L0-L5
#   bash scripts/test_all.sh --quick      # 仅 L0-L3 (无需 Docker/后端)
#   bash scripts/test_all.sh --api        # 仅 L4-L5 (需要 Docker + 后端运行中)
#   bash scripts/test_all.sh --l0         # 仅 L0 语法检查
#   bash scripts/test_all.sh --l0123      # L0+L1+L2+L3
# ──────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASSED=0
FAILED=0
FAILED_LEVELS=()

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}✅ $1${NC}"; PASSED=$((PASSED + 1)); }
log_fail() { echo -e "${RED}❌ $1${NC}"; FAILED=$((FAILED + 1)); FAILED_LEVELS+=("$1"); }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }

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
        --full)  MODE="full"; shift ;;
        --l0)    MODE="l0"; shift ;;
        --l0123) MODE="l0123"; shift ;;
        *) shift ;;
    esac
done

echo -e "${CYAN}ProxySQL Admin WebUI — Automated Test Suite v2${NC}"
echo "Root: $ROOT_DIR | Mode: $MODE"

# ── L0: Syntax Check ─────────────────────────────────
run_l0() {
    echo -e "\n${CYAN}═══ L0: Syntax Check ═══${NC}"

    # L0a: Python syntax
    run_level "L0a: Python Syntax" python3 "$SCRIPT_DIR/test_l0_syntax.py"

    # L0b: TypeScript type check (quick — just tsc)
    echo -e "\n── L0b: TypeScript Type Check ──"
    if command -v npx &>/dev/null; then
        cd "$ROOT_DIR/frontend"
        if npx tsc --noEmit 2>&1 | tail -5; then
            log_pass "L0b: TypeScript Type Check"
        else
            log_fail "L0b: TypeScript Type Check"
        fi
        cd "$ROOT_DIR"
    else
        log_warn "L0b: TypeScript — npx not available, skipping"
    fi
}

# ── L1: Import Check ─────────────────────────────────
run_l1() {
    run_level "L1: Python Import Check" python3 "$SCRIPT_DIR/test_l1_imports.py"
}

# ── L2: Static Analysis ──────────────────────────────
run_l2() {
    run_level "L2: Static Analysis" python3 "$SCRIPT_DIR/test_l2_lint.py"
}

# ── L3: Frontend Build ───────────────────────────────
run_l3() {
    run_level "L3: Frontend Build" python3 "$SCRIPT_DIR/test_l3_frontend.py"
}

# ── L4: API Smoke Test ───────────────────────────────
run_l4() {
    echo -e "\n${YELLOW}L4 requires: Docker (MySQL+ProxySQL) + Backend on :8080${NC}"
    run_level "L4: API Smoke Test" python3 "$SCRIPT_DIR/test_l4_api_smoke.py"
}

# ── L5: Full-Chain Integration ───────────────────────
run_l5() {
    echo -e "\n${YELLOW}L5 requires: Docker (MySQL+ProxySQL) + Backend on :8080${NC}"
    run_level "L5: Full-Chain Integration" python3 "$SCRIPT_DIR/test_l5_integration.py"
}

# ── Execute based on mode ────────────────────────────
case "$MODE" in
    quick|l0123)
        run_l0
        run_l1
        run_l2
        run_l3
        ;;
    api)
        run_l4
        run_l5
        ;;
    l0)
        run_l0
        ;;
    full|all)
        run_l0
        run_l1
        run_l2
        run_l3
        run_l4
        run_l5
        ;;
esac

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
