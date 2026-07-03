#!/bin/sh
# ── Docker Entrypoint ──────────────────────────────────────────────
# 自适应处理 bind mount 权限问题：
# 当宿主机目录挂载到 /app/data 时，目录的 owner 可能不属于
# proxysql 用户，导致无法写入数据库文件。
#
# 策略：
#   1. 以 root 启动容器（ENTRYPOINT 阶段是 root）
#   2. 确保 /app/data 的 owner 是 proxysql
#   3. 用 gosu 降权到 proxysql 用户运行 uvicorn
#
# 如果宿主机 bind mount 的目录没有写权限，chown 会失败，
# 但此时至少有一个清晰的错误提示。

set -e

DATA_DIR="/app/data"

# 确保 data 目录存在
mkdir -p "$DATA_DIR" 2>/dev/null || true

# 以 root 身份修复 data 目录权限
if [ "$(id -u)" = "0" ]; then
    # 尝试 chown — 对 bind mount 可能因宿主机权限而失败
    if ! chown proxysql:proxysql "$DATA_DIR" 2>/dev/null; then
        echo "[entrypoint] WARNING: Cannot chown $DATA_DIR. This may happen with"
        echo "  bind mounts on hosts that restrict ownership changes. Checking"
        echo "  if the directory is at least writable by the proxysql user..."
    fi

    # 验证 proxysql 用户是否能写入
    if ! su -s /bin/sh -c "touch '$DATA_DIR/.write_test' && rm -f '$DATA_DIR/.write_test'" proxysql 2>/dev/null; then
        echo ""
        echo "ERROR: /app/data is not writable by the proxysql user."
        echo ""
        echo "  This happens when a bind mount directory on the host has"
        echo "  permissions that don't match the container user. To fix:"
        echo ""
        echo "    mkdir -p ./app_data"
        echo "    chown -R 1000:1000 ./app_data   # or match the proxysql uid"
        echo ""
        echo "  Or use a Docker named volume instead of bind mount:"
        echo "    volumes:"
        echo "      - app_data:/app/data"
        exit 1
    fi

    echo "[entrypoint] Permissions OK, starting as proxysql user ..."
    exec su -s /bin/sh -c 'exec "$@"' _ proxysql "$@"
fi

# 非 root（兼容性回退）
echo "[entrypoint] Not running as root, starting directly ..."
exec "$@"
