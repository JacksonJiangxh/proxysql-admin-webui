# ProxySQL Admin WebUI — 生产部署指南

> **语言**: 简体中文 | **版本**: v1.0.0 | **更新日期**: 2026-06-22

本文档描述在生产环境中部署 ProxySQL Admin WebUI 的推荐方案。

---

## 目录

- [架构概览](#架构概览)
- [部署前准备](#部署前准备)
- [方式一：Docker Compose 部署（推荐）](#方式一docker-compose-部署推荐)
- [方式二：裸机部署](#方式二裸机部署)
- [方式三：Kubernetes 部署](#方式三kubernetes-部署)
- [HTTPS / TLS 配置](#https--tls-配置)
- [环境变量参考](#环境变量参考)
- [备份与恢复](#备份与恢复)
- [健康监控](#健康监控)
- [升级流程](#升级流程)
- [安全加固](#安全加固)
- [性能调优](#性能调优)
- [常见问题排查](#常见问题排查)

---

## 架构概览

```
                           ┌──────────────────────────────────┐
                           │     ProxySQL Admin WebUI         │
  Browser ──HTTPS──▶ Nginx ──HTTP──▶ uvicorn (:8080)          │
                           │         ├─ REST / WebSocket API  │
                           │         └─ StaticFiles (SPA)     │
                           │                │                 │
                           │                │ MySQL Protocol  │
                           │                ▼                 │
                           │    ProxySQL Admin (:6032)        │
                           └──────────────────────────────────┘
                                           │
                               ┌───────────┼───────────┐
                               ▼           ▼           ▼
                           MySQL-1     MySQL-2     PostgreSQL
```

**关键设计**：
- **单进程部署**：FastAPI 进程同时提供 API 和前端静态文件，无需额外的 nginx 容器
- 前端 React SPA 构建后嵌入后端镜像，同源部署，无跨域问题
- **可选用外部 nginx**：仅当需要 HTTPS 终止、限流或额外安全头时添加

---

## 部署前准备

### 硬件要求

| 环境 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| 最小 | 1 vCPU | 512 MB | 1 GB |
| 推荐（生产） | 2 vCPU | 2 GB | 20 GB SSD |

### 软件要求

- **Docker 24.0+** + Docker Compose v2（推荐方式）
- 或 **Python 3.10+** + Node.js 24+（裸机方式）
- **ProxySQL 2.5+** 实例（管理端口 6032 可访问）

### 网络要求

| 组件 | 端口 | 方向 | 说明 |
|------|------|------|------|
| Browser → WebUI | 8080（或 443） | 入站 | 管理界面访问 |
| WebUI → ProxySQL | 6032 | 出站 | ProxySQL 管理连接 |

### 密码生成

在 `SECRET_KEY` 和 `FERNET_KEY` 中设置安全密钥：

```bash
# 生成随机 SECRET_KEY（64 字符）
python3 -c "import secrets; print(secrets.token_hex(32))"

# 生成 FERNET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 方式一：Docker Compose 部署（推荐）

### 1. 创建项目目录

```bash
mkdir -p /opt/proxysql-admin-webui/data
cd /opt/proxysql-admin-webui
```

### 2. 创建环境变量文件

```bash
cat > .env << 'EOF'
# ── 安全密钥（必须修改！）──────────────────────────
SECRET_KEY=<使用上方命令生成>
FERNET_KEY=<使用上方命令生成>

# ── 数据库 ─────────────────────────────────────────
DATABASE_URL=sqlite:///data/app.db

# ── 认证 ───────────────────────────────────────────
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# ── 日志 ───────────────────────────────────────────
LOG_LEVEL=INFO

# ── ProxySQL 默认连接 ─────────────────────────────
PROXYSQL_DEFAULT_HOST=127.0.0.1
PROXYSQL_DEFAULT_PORT=6032

# ── 初始管理员 ─────────────────────────────────────
PROXYWEB_ADMIN_USER=admin
PROXYWEB_ADMIN_PASSWORD=<设置强密码>
EOF
```

### 3. 创建 Docker Compose 文件

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  proxysql-admin-webui:
    image: ghcr.io/your-org/proxysql-admin-webui:latest
    # 或本地构建：build: ...
    ports:
      - "8080:8080"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/v1/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

volumes:
  data:
EOF
```

### 4. 启动服务

```bash
docker compose up -d

# 验证服务状态
docker compose ps
curl http://localhost:8080/api/v1/health
```

### 5. 使用外部 nginx 反向代理（可选）

```bash
cat > docker-compose.override.yml << 'EOF'
version: '3.8'

services:
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - proxysql-admin-webui
    restart: unless-stopped

  proxysql-admin-webui:
    ports:
      - "127.0.0.1:8080:8080"  # 仅本地访问
EOF
```

---

## 方式二：裸机部署

### 1. 安装依赖

```bash
# Python 3.10+
python3 --version

# Node.js 24+
node --version

# 系统依赖（ProxySQL 管理命令需要 mysql CLI）
# Debian/Ubuntu:
apt-get install -y default-mysql-client

# RHEL/CentOS:
yum install -y mysql
```

### 2. 克隆仓库并安装

```bash
git clone https://github.com/your-org/proxysql-admin-webui.git
cd proxysql-admin-webui

# 安装后端依赖
cd backend && pip install -r requirements.txt && cd ..

# 安装前端依赖并构建
cd frontend && npm ci && npm run build && cd ..
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，修改所有密钥和密码
vim .env
```

### 4. 启动服务

```bash
# 生产模式（单进程，API + 前端）
make run

# 或使用 systemd 管理（推荐）
```

### 5. systemd 服务配置

```bash
sudo cat > /etc/systemd/system/proxysql-admin-webui.service << 'EOF'
[Unit]
Description=ProxySQL Admin WebUI
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/proxysql-admin-webui/backend
EnvironmentFile=/opt/proxysql-admin-webui/.env
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# 安全加固
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/proxysql-admin-webui/data
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now proxysql-admin-webui
```

---

## 方式三：Kubernetes 部署

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: proxysql-admin-webui
  labels:
    app: proxysql-admin-webui
spec:
  replicas: 1
  selector:
    matchLabels:
      app: proxysql-admin-webui
  template:
    metadata:
      labels:
        app: proxysql-admin-webui
    spec:
      containers:
        - name: webui
          image: ghcr.io/your-org/proxysql-admin-webui:1.0.0
          ports:
            - containerPort: 8080
          env:
            - name: DATABASE_URL
              value: "sqlite:///data/app.db"
            envFrom:
            - secretRef:
                name: proxysql-admin-secrets
          volumeMounts:
            - name: data
              mountPath: /app/data
          livenessProbe:
            httpGet:
              path: /api/v1/health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /api/v1/health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: proxysql-admin-data

---
apiVersion: v1
kind: Service
metadata:
  name: proxysql-admin-webui
spec:
  selector:
    app: proxysql-admin-webui
  ports:
    - port: 8080
      targetPort: 8080

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: proxysql-admin-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi

---
apiVersion: v1
kind: Secret
metadata:
  name: proxysql-admin-secrets
type: Opaque
stringData:
  SECRET_KEY: "<生成的安全密钥>"
  FERNET_KEY: "<生成的 Fernet key>"
  PROXYWEB_ADMIN_USER: "admin"
  PROXYWEB_ADMIN_PASSWORD: "<强密码>"
```

### 部署命令

```bash
kubectl apply -f kubernetes/
kubectl get pods -l app=proxysql-admin-webui

# 创建 Ingress（需配合 cert-manager）
kubectl apply -f - << 'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: proxysql-admin-webui
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
    - hosts:
        - proxysql-admin.example.com
      secretName: proxysql-admin-tls
  rules:
    - host: proxysql-admin.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: proxysql-admin-webui
                port:
                  number: 8080
EOF
```

---

## HTTPS / TLS 配置

### 使用 Let's Encrypt + Certbot

```bash
# 安装 certbot
apt-get install -y certbot python3-certbot-nginx

# 获取证书
certbot certonly --nginx -d proxysql-admin.example.com

# 证书自动续期检查
certbot renew --dry-run
```

### nginx 反向代理配置

```nginx
# /etc/nginx/sites-available/proxysql-admin
server {
    listen 80;
    server_name proxysql-admin.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name proxysql-admin.example.com;

    ssl_certificate     /etc/letsencrypt/live/proxysql-admin.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/proxysql-admin.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # 安全头
    add_header X-Content-Type-Options    "nosniff" always;
    add_header X-Frame-Options           "DENY" always;
    add_header X-XSS-Protection          "1; mode=block" always;
    add_header Referrer-Policy           "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # 客户端最大 body 大小（上传配置）
    client_max_body_size 10m;

    # WebSocket 支持
    location /ws {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 环境变量参考

完整列表见 [配置参考](configuration.md)。

| 变量 | 必须 | 默认值 | 说明 |
|------|:----:|--------|------|
| `SECRET_KEY` | **是** | — | JWT 签名密钥，至少 32 字符 |
| `FERNET_KEY` | **是** | — | 凭证加密密钥（Fernet 格式） |
| `DATABASE_URL` | 否 | `sqlite:///data/app.db` | 数据库连接 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 否 | `60` | JWT 访问令牌过期时间 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 否 | `7` | JWT 刷新令牌过期时间 |
| `LOG_LEVEL` | 否 | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR) |
| `PROXYSQL_DEFAULT_HOST` | 否 | `127.0.0.1` | 默认 ProxySQL 主机 |
| `PROXYSQL_DEFAULT_PORT` | 否 | `6032` | 默认 ProxySQL 端口 |
| `PROXYWEB_ADMIN_USER` | 否 | — | 初始管理员用户名 |
| `PROXYWEB_ADMIN_PASSWORD` | 否 | — | 初始管理员密码 |
| `FRONTEND_DIST` | 否 | `/app/frontend/dist` | 前端静态文件路径（Docker 已预设） |

---

## 备份与恢复

### 备份内容

需要备份的数据：

| 数据 | 位置 | 方式 |
|------|------|------|
| SQLite 数据库 | `data/app.db` | 文件复制 |
| ProxySQL 配置 | ProxySQL 实例 | `SAVE CONFIG TO DISK` 后备份 `proxysql.db` |

### 自动备份脚本

```bash
#!/bin/bash
# /opt/proxysql-admin-webui/scripts/backup.sh

BACKUP_DIR="/opt/backups/proxysql-admin"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# 备份 SQLite 数据库（使用 sqlite3 .backup 确保一致性）
sqlite3 /opt/proxysql-admin-webui/data/app.db \
  ".backup '$BACKUP_DIR/app_$TIMESTAMP.db'"

# 压缩
gzip "$BACKUP_DIR/app_$TIMESTAMP.db"

# 清理旧备份
find "$BACKUP_DIR" -name "*.db.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: app_$TIMESTAMP.db.gz"
```

### 恢复

```bash
# 1. 停止服务
docker compose down
# 或 systemctl stop proxysql-admin-webui

# 2. 恢复数据库
gunzip -c /opt/backups/proxysql-admin/app_20260622_120000.db.gz \
  > /opt/proxysql-admin-webui/data/app.db

# 3. 启动服务
docker compose up -d
```

---

## 健康监控

### 健康检查端点

```bash
# 基础健康检查
curl http://localhost:8080/api/v1/health
# 响应：{"status": "healthy", "version": "1.0.0"}

# 数据库状态检查
curl http://localhost:8080/api/v1/health/db
```

### Prometheus 监控（示例）

虽然内置不暴露 Prometheus 指标，但可通过健康检查和日志进行监控：

```yaml
# prometheus scrape 配置
scrape_configs:
  - job_name: 'proxysql-admin-webui'
    metrics_path: '/api/v1/health'
    static_configs:
      - targets: ['localhost:8080']
```

### 告警建议

| 检查项 | 阈值 | 严重性 |
|--------|------|--------|
| HTTP 200 健康检查失败 | 连续 3 次 | Critical |
| 响应时间 > 2s | 持续 5 分钟 | Warning |
| WebSocket 连接失败 | 任意 | Warning |
| ProxySQL 连接失败 | 任意 | Critical |
| 磁盘空间 < 20% | 任意 | Warning |

### Docker 健康检查

已在 `docker-compose.yml` 示例中配置：

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/api/v1/health"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 10s
```

---

## 升级流程

### Docker 部署升级

```bash
# 1. 备份数据
./scripts/backup.sh

# 2. 拉取新镜像
docker compose pull

# 3. 滚动更新（零停机）
docker compose up -d

# 4. 验证
curl http://localhost:8080/api/v1/health
docker compose logs -f --tail=50
```

### 裸机部署升级

```bash
# 1. 备份
./scripts/backup.sh

# 2. 拉取最新代码
git pull origin main

# 3. 更新依赖
cd backend && pip install -r requirements.txt && cd ..
cd frontend && npm ci && npm run build && cd ..

# 4. 重启服务
sudo systemctl restart proxysql-admin-webui

# 5. 验证
curl http://localhost:8080/api/v1/health
sudo journalctl -u proxysql-admin-webui -f
```

### 回滚

```bash
# Docker
docker compose down
# 恢复数据备份
gunzip -c /opt/backups/proxysql-admin/app_PREVIOUS.db.gz \
  > /opt/proxysql-admin-webui/data/app.db
# 回滚到指定版本
docker compose up -d proxysql-admin-webui:1.0.0  # 或修改 image tag

# 裸机
git checkout v1.0.0  # 回滚到指定 tag
# 重新构建并重启
```

---

## 安全加固

### 1. 密钥管理

- **绝不**将 `.env` 提交到 Git
- 使用 `secrets` 管理工具（HashiCorp Vault、AWS Secrets Manager 等）
- 定期轮换 `SECRET_KEY`（会导致所有用户需重新登录）
- `FERNET_KEY` 轮换需重新加密所有存储的密码

### 2. 网络安全

- 将 WebUI 绑定到 `127.0.0.1`，通过 nginx 反向代理暴露
- 使用防火墙限制对 8080 端口的访问
- ProxySQL 管理端口（6032）仅允许 WebUI 所在主机访问
- 启用 HTTPS，禁用 HTTP

### 3. 容器安全

```yaml
# docker-compose.yml 安全加固
services:
  proxysql-admin-webui:
    # ...
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    # 指定非 root 用户（需镜像支持）
    user: "1000:1000"
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # 仅当绑定 <1024 端口时需要
```

### 4. 应用安全

- 密码使用 bcrypt（后端）和 Fernet（ProxySQL 凭证）双重加密
- 会话过期策略：访问令牌 480 分钟（8 小时）+ 刷新令牌 7 天

### 5. 定时安全审计

```bash
# 依赖漏洞扫描
cd backend && safety check

# 代码安全扫描
cd backend && bandit -r app/

# Docker 镜像扫描
docker scan proxysql-admin-webui:latest
```

---

## 性能调优

### uvicorn Workers

对于高并发场景，增加 worker 进程数：

```bash
# 生产模式（多 worker）
cd backend && uvicorn app.main:app \
  --host 0.0.0.0 --port 8080 \
  --workers 4 \
  --limit-concurrency 100 \
  --backlog 2048
```

> **注意**：使用多 worker 时，WebSocket 需要 sticky session 或 Redis 作为 message broker。

### Docker Compose 资源限制

```yaml
services:
  proxysql-admin-webui:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### ProxySQL 连接池

在 WebUI 中配置以下系统变量以优化连接：

- `admin-checksum_mysql_query_rules`：启用规则变更检测
- `mysql-connect_timeout_server`：后端连接超时（建议 3000ms）
- `mysql-max_connections`：最大连接数（建议根据后端容量调整）

---

## 常见问题排查

### 1. 无法连接 ProxySQL

**症状**：WebUI 显示"无法连接到 ProxySQL 服务器"

**排查**：
```bash
# 检查 ProxySQL 是否运行
mysql -h <proxy-host> -P 6032 -u admin -p

# 检查网络连通性
nc -zv <proxy-host> 6032

# 检查 WebUI 环境变量
echo $PROXYSQL_DEFAULT_HOST
echo $PROXYSQL_DEFAULT_PORT
```

### 2. 数据库损坏

**症状**：启动失败，日志显示 `database disk image is malformed`

**解决**：
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

### 3. 登录失败（即使密码正确）

**症状**：正确的用户名/密码组合登录失败

**排查**：
```bash
# 检查 SECRET_KEY 是否变更（变更加密密钥会使 jwt token 失效）
docker compose logs proxysql-admin-webui | grep "SECRET_KEY"

# 重置默认管理员密码
docker compose exec proxysql-admin-webui python -c "
from app.database import get_db, init_db
from app.models.user import User
import asyncio

async def reset():
    db = await get_db()
    # 重新创建 admin 用户
    await init_db(db)

asyncio.run(reset())
"
```

### 4. 前端页面空白

**症状**：访问 WebUI 看到空白页

**排查**：
```bash
# 检查前端构建产物
ls -la frontend/dist/index.html

# 检查 FRONTEND_DIST 环境变量
docker compose exec proxysql-admin-webui ls /app/frontend/dist/

# 重新构建
make build-frontend
```

### 5. 内存持续增长

**症状**：容器内存使用量随时间增长

**排查**：
```bash
# Docker 资源限制
docker stats proxysql-admin-webui

# 检查 SQLite WAL 文件
ls -lh data/app.db-wal

# 重试：定期重启服务
# 长时间运行后，可通过 cron 定时重启（如每周凌晨）
```

### 6. WebSocket 断连

**症状**：仪表盘显示 WebSocket 断开并被 nginx 返回 502

**排查**：
```bash
# 确保 nginx 配置了 WebSocket 支持（proxy_read_timeout）
grep -A5 "location /ws" /etc/nginx/sites-available/proxysql-admin

# 增加超时（仪表盘链接可能保持长时间）
proxy_read_timeout 86400s;  # 24 小时
```

---

## 日志管理

### 查看日志

```bash
# Docker
docker compose logs -f proxysql-admin-webui --tail=100

# systemd
sudo journalctl -u proxysql-admin-webui -f

# 裸机（stdout）
make run 2>&1 | tee /var/log/proxysql-admin-webui/app.log
```

### 日志轮转（裸机）

```bash
cat > /etc/logrotate.d/proxysql-admin-webui << 'EOF'
/var/log/proxysql-admin-webui/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
```

---

## 附录：快速部署检查清单

- [ ] 生成 `SECRET_KEY` 和 `FERNET_KEY`
- [ ] 创建 `.env` 文件，修改所有默认值
- [ ] 确保 ProxySQL 管理端口（6032）可访问
- [ ] 选择部署方式（Docker / 裸机 / K8s）
- [ ] 配置 HTTPS 反向代理（推荐 nginx + Let's Encrypt）
- [ ] 设置防火墙规则
- [ ] 配置自动备份（cron 或 systemd timer）
- [ ] 设置健康监控和告警
- [ ] 验证登录和基本功能
- [ ] 文档化部署信息（IP、端口、密钥存放位置）
