#!/usr/bin/env bash
# =========================================================================
# ProxySQL Admin WebUI — 本地 Docker 构建与测试脚本
# =========================================================================
# 参考 .cnb.yml 中 docker-amd64 / docker-arm64 job 的构建流程，
# 在本地开发环境中：
#   1. 构建 Docker 镜像（类似流水线中的 docker build）
#   2. 启动容器进行冒烟测试（验证镜像能否正常运行）
#   3. 提供清理选项
#
# 使用方法：
#   chmod +x scripts/docker-local-test.sh
#   ./scripts/docker-local-test.sh          # 构建 + 启动 + 健康检查
#   ./scripts/docker-local-test.sh --clean  # 停止容器并删除镜像
#   ./scripts/docker-local-test.sh --rebuild # 重新构建并启动
# =========================================================================

set -euo pipefail

# ── 颜色输出 ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 配置（对应 .cnb.yml 中 docker-amd64 job 的参数） ──────────────
IMAGE_NAME="${IMAGE_NAME:-proxysql-admin-webui}"
IMAGE_TAG="${IMAGE_TAG:-local-test}"
CONTAINER_NAME="${CONTAINER_NAME:-proxysql-admin-webui-test}"
HOST_PORT="${HOST_PORT:-8080}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"

# 完整镜像引用
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

# ── 辅助函数 ──────────────────────────────────────────────────────

# 检查 Docker 是否可用
check_docker() {
    if ! command -v docker &>/dev/null; then
        log_error "Docker 未安装或不在 PATH 中，请先安装 Docker。"
        exit 1
    fi
    if ! docker info &>/dev/null; then
        log_error "Docker daemon 未运行或无权限访问。"
        exit 1
    fi
}

# 清理旧的测试容器和镜像
clean() {
    log_info "正在清理测试环境..."

    # 停止并删除容器
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "停止容器: ${CONTAINER_NAME}"
        docker stop "${CONTAINER_NAME}" 2>/dev/null || true
        docker rm "${CONTAINER_NAME}" 2>/dev/null || true
        log_ok "容器已删除"
    else
        log_info "容器 ${CONTAINER_NAME} 不存在，跳过"
    fi

    # 删除镜像
    if docker image inspect "${FULL_IMAGE}" &>/dev/null; then
        log_info "删除镜像: ${FULL_IMAGE}"
        docker rmi "${FULL_IMAGE}" 2>/dev/null || true
        log_ok "镜像已删除"
    else
        log_info "镜像 ${FULL_IMAGE} 不存在，跳过"
    fi
}

# 构建 Docker 镜像（对应 .cnb.yml docker-amd64 job 的 build-and-push stage）
build() {
    log_info "开始构建 Docker 镜像..."
    echo ""
    echo "  ┌─────────────────────────────────────────────────────────┐"
    echo "  │  镜像名称 : ${FULL_IMAGE}"
    echo "  │  Dockerfile : ${DOCKERFILE}"
    echo "  │  构建上下文 : $(pwd)"
    echo "  │  当前架构   : $(uname -m)"
    echo "  └─────────────────────────────────────────────────────────┘"
    echo ""

    # 对应 .cnb.yml 中的：
    #   docker build -t "${IMAGE}:${VERSION}-amd64" -f Dockerfile .
    docker build \
        -t "${FULL_IMAGE}" \
        -f "${DOCKERFILE}" \
        .

    log_ok "镜像构建完成: ${FULL_IMAGE}"

    # 显示镜像大小
    echo ""
    docker image inspect "${FULL_IMAGE}" --format '  镜像大小: {{.Size}} bytes' | \
        awk '{printf "  镜像大小: %.1f MB\n", $3/1024/1024}'
}

# 确保 .env 文件存在
ensure_env() {
    if [ ! -f ".env" ]; then
        log_warn "未找到 .env 文件，将从 .env.example 复制..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_ok "已从 .env.example 复制到 .env"
            log_warn "⚠ 请检查 .env 中的配置，特别是 SECRET_KEY 和 FERNET_KEY！"
        else
            log_error ".env.example 文件不存在，无法创建 .env"
            exit 1
        fi
    else
        log_ok ".env 文件已存在"
    fi
}

# 启动容器并等待健康检查通过
start_and_check() {
    log_info "启动测试容器..."

    # 先确保端口没有被占用
    if lsof -Pi :${HOST_PORT} -sTCP:LISTEN -t &>/dev/null; then
        log_warn "端口 ${HOST_PORT} 已被占用，尝试使用其他端口..."
        # 找到占用端口的进程
        local pid
        pid=$(lsof -Pi :${HOST_PORT} -sTCP:LISTEN -t 2>/dev/null || true)
        if [ -n "${pid}" ]; then
            log_warn "占用进程 PID: ${pid}，请手动处理或指定其他端口: HOST_PORT=9090 $0"
            exit 1
        fi
    fi

    # 启动容器
    docker run -d \
        --name "${CONTAINER_NAME}" \
        -p "${HOST_PORT}:8080" \
        --env-file .env \
        --restart no \
        "${FULL_IMAGE}"

    log_ok "容器已启动: ${CONTAINER_NAME}"

    # 等待健康检查通过（对应 Dockerfile 中的 HEALTHCHECK）
    log_info "等待容器健康检查通过（最多 60 秒）..."
    local attempt=0
    local max_attempts=30
    local wait_seconds=2
    local health_status

    while [ ${attempt} -lt ${max_attempts} ]; do
        health_status=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")

        case "${health_status}" in
            healthy)
                log_ok "容器健康检查通过！"
                return 0
                ;;
            unhealthy)
                log_error "容器健康检查失败！"
                log_error "查看容器日志: docker logs ${CONTAINER_NAME}"
                return 1
                ;;
            starting)
                attempt=$((attempt + 1))
                printf "\r  等待中... (${attempt}/${max_attempts})  状态: ${health_status}"
                sleep ${wait_seconds}
                ;;
            *)
                # 容器可能还在启动中，状态还没出现
                attempt=$((attempt + 1))
                printf "\r  等待中... (${attempt}/${max_attempts})  状态: ${health_status}"
                sleep ${wait_seconds}
                ;;
        esac
    done

    log_error "健康检查超时（${max_attempts} 次尝试后仍未通过）"
    log_error "查看容器日志: docker logs ${CONTAINER_NAME}"
    return 1
}

# 冒烟测试：验证 API 端点是否正常响应
smoke_test() {
    log_info "执行冒烟测试..."

    local base_url="http://localhost:${HOST_PORT}"

    # 测试健康检查端点
    log_info "测试 GET /api/v1/health ..."
    local health_response
    health_response=$(curl -s -o /dev/null -w "%{http_code}" "${base_url}/api/v1/health" || echo "000")
    if [ "${health_response}" = "200" ]; then
        log_ok "健康检查端点返回 200 OK"
    else
        log_error "健康检查端点返回 ${health_response}"
        return 1
    fi

    # 测试 API 文档
    log_info "测试 GET /docs ..."
    local docs_response
    docs_response=$(curl -s -o /dev/null -w "%{http_code}" "${base_url}/docs" || echo "000")
    if [ "${docs_response}" = "200" ]; then
        log_ok "API 文档端点返回 200 OK"
    else
        log_warn "API 文档端点返回 ${docs_response}（可能正常，FastAPI docs 有时需要 JS）"
    fi

    # 测试 OpenAPI schema
    log_info "测试 GET /openapi.json ..."
    local schema_response
    schema_response=$(curl -s -o /dev/null -w "%{http_code}" "${base_url}/openapi.json" || echo "000")
    if [ "${schema_response}" = "200" ]; then
        log_ok "OpenAPI schema 端点返回 200 OK"
    else
        log_error "OpenAPI schema 端点返回 ${schema_response}"
        return 1
    fi

    # 测试前端静态文件（验证前端是否正确嵌入）
    log_info "测试 GET / (前端首页) ..."
    local frontend_response
    frontend_response=$(curl -s -o /dev/null -w "%{http_code}" "${base_url}/" || echo "000")
    if [ "${frontend_response}" = "200" ]; then
        log_ok "前端首页返回 200 OK"
    else
        log_error "前端首页返回 ${frontend_response}"
        return 1
    fi

    echo ""
    log_ok "所有冒烟测试通过！"
}

# 显示容器信息
show_info() {
    echo ""
    echo "  ╔═══════════════════════════════════════════════════════════╗"
    echo "  ║           Docker 镜像本地测试 — 运行中                    ║"
    echo "  ╠═══════════════════════════════════════════════════════════╣"
    echo "  ║                                                           ║"
    echo "  ║  容器名称  : ${CONTAINER_NAME}"
    echo "  ║  镜像      : ${FULL_IMAGE}"
    echo "  ║  访问地址  : http://localhost:${HOST_PORT}"
    echo "  ║  API 文档  : http://localhost:${HOST_PORT}/docs"
    echo "  ║  OpenAPI   : http://localhost:${HOST_PORT}/openapi.json"
    echo "  ║                                                           ║"
    echo "  ║  查看日志  : docker logs -f ${CONTAINER_NAME}"
    echo "  ║  进入容器  : docker exec -it ${CONTAINER_NAME} /bin/bash"
    echo "  ║  停止容器  : docker stop ${CONTAINER_NAME}"
    echo "  ║  清理全部  : $0 --clean"
    echo "  ║                                                           ║"
    echo "  ╚═══════════════════════════════════════════════════════════╝"
    echo ""
}

# ── 主流程 ────────────────────────────────────────────────────────

main() {
    echo ""
    echo "  ╔═══════════════════════════════════════════════════════════╗"
    echo "  ║     ProxySQL Admin WebUI — Docker 本地构建测试            ║"
    echo "  ╚═══════════════════════════════════════════════════════════╝"
    echo ""

    # 确保在项目根目录执行
    if [ ! -f "Dockerfile" ]; then
        log_error "请在项目根目录下运行此脚本（需要找到 Dockerfile）"
        exit 1
    fi

    check_docker

    case "${1:-build}" in
        --clean|clean)
            clean
            log_ok "清理完成！"
            ;;
        --rebuild|rebuild)
            clean
            ensure_env
            build
            start_and_check && smoke_test && show_info
            ;;
        --build-only)
            ensure_env
            build
            ;;
        *)
            # 默认流程: 构建 → 启动 → 健康检查 → 冒烟测试
            ensure_env
            build
            start_and_check && smoke_test && show_info
            ;;
    esac
}

main "$@"
