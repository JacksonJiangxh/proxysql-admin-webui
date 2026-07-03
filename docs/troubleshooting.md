# 故障排除

## 常见连接问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 无法连接 ProxySQL | 网络不通或端口错误 | 检查 ProxySQL 是否运行，确认管理端口（默认 6032） |
| 认证失败 | 用户名或密码错误 | 检查 ProxySQL 管理用户凭证 |
| 连接超时 | 网络延迟或防火墙 | 检查防火墙规则，确认端口开放 |
| WebSocket 断开 | 网络不稳定 | 等待自动重连，或刷新页面 |

---

## ProxySQL 连接问题

### 1. 确认 ProxySQL 服务正在运行

```bash
systemctl status proxysql
# 或
ps aux | grep proxysql
```

### 2. 测试管理端口连通性

```bash
mysql -h 127.0.0.1 -P 6032 -u admin -p
```

### 3. 检查 ProxySQL 日志

```bash
tail -f /var/lib/proxysql/proxysql.log
```

---

## 配置同步失败

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| Apply 失败 | MEMORY 中有无效配置 | 检查表数据是否有冲突或无效值 |
| Save 失败 | 磁盘空间不足或权限问题 | 检查 `/var/lib/proxysql/` 权限和空间 |
| 配置不一致 | 手动修改了 ProxySQL | 使用配置差异对比功能排查 |
| 重启后配置丢失 | 未执行 Save | 使用 W47 或配置同步页面 Save to Disk |

---

## 日志位置

| 日志类型 | 位置 | 查看方式 |
|---------|------|---------|
| 应用日志 | `backend/logs/` | Docker: `docker compose logs` |
| ProxySQL 日志 | `/var/lib/proxysql/proxysql.log` | `tail -f` 查看 |
| systemd 日志 | journald | `journalctl -u proxysql-admin-webui` |

---

## 数据库损坏

**症状**：启动失败，日志显示 `database disk image is malformed`

**解决方案**：

```bash
# 1. 停止服务
docker compose down

# 2. 尝试修复
sqlite3 data/app.db "PRAGMA integrity_check;"

# 3. 如果修复失败，从备份恢复
gunzip -c /opt/backups/proxysql-admin/app_latest.db.gz > data/app.db

# 4. 重启
docker compose up -d
```

---

## 登录失败（即使密码正确）

**症状**：正确的用户名/密码组合登录失败

**原因**：

1. `SECRET_KEY` 变更：修改加密密钥会使现有 JWT Token 失效
2. 数据库初始化问题

**解决方案**：

```bash
# 检查日志
docker compose logs proxysql-admin-webui | grep -i "auth\|login"

# 查看用户表
docker compose exec proxysql-admin-webui sqlite3 /app/data/app.db \
  "SELECT username, role, is_active FROM users;"
```

---

## 前端页面空白

**症状**：访问 WebUI 看到空白页面

**排查步骤**：

```bash
# 1. 检查前端构建产物
ls -la frontend/dist/index.html

# 2. 在 Docker 中检查
docker compose exec proxysql-admin-webui ls -la /app/frontend/dist/

# 3. 重新构建
make clean
make build-frontend
```

---

## 内存持续增长

**症状**：容器内存使用量随时间增长

**解决方案**：

```bash
# 1. 监控资源使用
docker stats proxysql-admin-webui

# 2. 检查 SQLite WAL 文件大小
ls -lh data/app.db-wal

# 3. 设置资源限制（docker-compose.yml）
deploy:
  resources:
    limits:
      memory: 2G
    reservations:
      memory: 512M

# 4. 定期重启（cron 每周凌晨）
0 3 * * 0 docker compose restart proxysql-admin-webui
```

---

## WebSocket 断连

**症状**：仪表盘显示 WebSocket 断开，nginx 返回 502

**解决方案**：

确保 nginx 配置了 WebSocket 代理支持：

```nginx
location /ws {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400s;  # 24 小时长连接
}
```
