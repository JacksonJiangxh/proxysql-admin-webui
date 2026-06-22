# 配置参考

本文档列出 ProxySQL Admin WebUI 的所有环境变量和配置参数。

---

## 环境变量

所有配置通过 `.env` 文件或系统环境变量设置。

| 变量 | 必须 | 默认值 | 说明 |
|------|:----:|--------|------|
| `SECRET_KEY` | **是** | — | JWT 签名密钥，至少 32 字符，用于签发和验证 JWT Token |
| `FERNET_KEY` | **是** | — | 凭证加密密钥（Fernet 格式），用于加密存储 ProxySQL 管理密码 |
| `DATABASE_URL` | 否 | `sqlite:///data/app.db` | 数据库连接字符串，默认使用 SQLite |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 否 | `60` | JWT 访问令牌过期时间（分钟），超时后需重新登录 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 否 | `7` | JWT 刷新令牌过期时间（天） |
| `CORS_ORIGINS` | 否 | `http://localhost:5173` | CORS 允许的来源域名，多个用逗号分隔 |
| `LOG_LEVEL` | 否 | `INFO` | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `PROXYSQL_DEFAULT_HOST` | 否 | `127.0.0.1` | 默认 ProxySQL 管理接口的 IP 地址 |
| `PROXYSQL_DEFAULT_PORT` | 否 | `6032` | 默认 ProxySQL 管理接口的端口 |
| `PROXYWEB_ADMIN_USER` | 否 | `admin` | 初始管理员用户名（仅首次初始化时生效） |
| `PROXYWEB_ADMIN_PASSWORD` | 否 | `admin` | 初始管理员密码（仅首次初始化时生效，生产必须修改） |
| `FRONTEND_DIST` | 否 | `/app/frontend/dist` | 前端静态文件路径（Docker 容器已预设） |

---

## 生成安全密钥

在部署前，必须生成安全的 `SECRET_KEY` 和 `FERNET_KEY`：

```bash
# 生成 SECRET_KEY（64 位十六进制随机字符串）
python3 -c "import secrets; print(secrets.token_hex(32))"

# 生成 FERNET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

!!! warning "安全提醒"
    **绝不**将 `.env` 文件提交到 Git 仓库。生产环境应使用密钥管理服务（如 HashiCorp Vault、AWS Secrets Manager）。

---

## Docker Compose 配置示例

```yaml
services:
  proxysql-admin-webui:
    image: ghcr.io/xzydm/proxysql-admin-webui:latest
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
```

---

## 初始管理员账号

首次启动时，系统会根据 `PROXYWEB_ADMIN_USER` 和 `PROXYWEB_ADMIN_PASSWORD` 创建初始管理员账号：

- 用户名：`admin`（默认）
- 密码：`admin`（默认）
- 角色：`Admin`（最高权限）

!!! danger "生产环境"
    生产环境必须修改默认密码！首次登录后请立即通过「用户管理」页面修改密码。

---

## 密码策略

内置密码复杂度要求：

- 最小长度：8 位
- 最大登录尝试次数：5 次（超过锁定）
- 会话空闲超时：30 分钟

---

## 速率限制

| 端点类型 | 限制 | 说明 |
|---------|------|------|
| 登录接口 | 5 次/分钟 | 防止暴力破解 |
| API 接口 | 100 次/分钟 | 防止 API 滥用 |

---

## SSL / TLS 配置

### 后端 SSL 连接

通过 W06（后端服务器 SSL 参数）向导为单个后端服务器配置 SSL/TLS 连接参数。

通过 W41（SSL/TLS 后端连接变量）向导配置全局 SSL 参数：
- `mysql-ssl_p2s_ca`：CA 证书路径
- `mysql-ssl_p2s_cert`：客户端证书路径
- `mysql-ssl_p2s_key`：客户端私钥路径

### 前端 HTTPS

推荐使用 nginx 反向代理 + Let's Encrypt 配置 HTTPS。详见[部署指南 - HTTPS / TLS 配置](DEPLOYMENT.md#https--tls-配置)。
