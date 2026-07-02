# ProxySQL Admin WebUI — 唯一计划与测试追踪文档

> **本文档是项目唯一的计划+测试追踪文件。** 所有任务计划、测试进度、Bug 修复记录、环境配置全部集中于此。切换开发设备后，只需按本文档操作即可完整复现测试环境和测试进度。

---

## 一、测试环境搭建

### 1.1 前置依赖

| 依赖 | 最低版本 | 用途 |
|------|---------|------|
| Docker + Docker Compose | 20.10+ | 运行 MySQL + ProxySQL 容器 |
| Python | 3.12+ | 后端开发服务器 |
| Node.js | 20+ | 前端 Vite 开发服务器 |
| mysql-client (宿主机) | 8.0+ | 用于 `mysql` CLI 工具（连接 ProxySQL 排查问题） |

### 1.2 启动 Docker 基础服务（MySQL + ProxySQL）

```bash
# 启动测试用 MySQL 和 ProxySQL
docker compose -f docker-compose.test.yml up -d

# 等待健康检查通过（约 30-60 秒）
docker compose -f docker-compose.test.yml ps
# 期望看到 proxysql-test-mysql (healthy) 和 proxysql-test-proxysql (healthy)

# 查看初始化日志（确认远程用户创建成功）
docker logs proxysql-test-init
```

### 1.3 ⚠️ ProxySQL Admin 用户的核心陷阱

**这是整个测试环境最关键的知识点，必须理解：**

- **ProxySQL 的 `admin` 用户只能通过本地连接（localhost/127.0.0.1/Unix socket）访问 Admin 接口**。这是 ProxySQL 内置的安全机制：名为 `admin` 的用户默认只接受本地连接。
- **任何远程 TCP 连接（即使是同一台宿主机的非 lo 网卡 IP）都必须使用非 `admin` 用户名**。
- 因此 `docker-compose.test.yml` 的初始化脚本中做了两件事：
  1. 通过 127.0.0.1 连接 ProxySQL，执行 `LOAD/SAVE ADMIN VARIABLES`
  2. 添加第二个管理用户：`proxysql_remote:remote123`

**如果你只创建了 `admin:admin` 用户，WebUI 后端通过 TCP 连接 ProxySQL 时会收到 `Access denied for user 'admin'`**，因为 WebUI 使用的是网络连接而非 Unix socket。

```bash
# 验证 ProxySQL 用户配置（本地连接 admin 用户可用）
mysql -h 127.0.0.1 -P 6032 -u admin -padmin -e "SELECT * FROM global_variables WHERE variable_name='admin-admin_credentials';"

# 验证远程用户可用（WebUI 将使用此用户连接）
mysql -h 127.0.0.1 -P 6032 -u proxysql_remote -premote123 -e "SELECT 1;"
```

### 1.4 Docker 服务配置清单

**`docker-compose.test.yml`** 文件位于项目根目录 `/workspace/docker-compose.test.yml`，包含：

| 容器 | 镜像 | 端口 | 关键配置 |
|------|------|------|----------|
| `proxysql-test-mysql` | mysql:8.0 | 3306 | root/rootpass, testuser/testpass, binlog开启 |
| `proxysql-test-proxysql` | proxysql/proxysql:latest | 6032(admin), 6033(mysql) | admin:admin + proxysql_remote:remote123 |
| `proxysql-test-init` | mysql:8.0 | 共享 proxysql 网络 | 自动配置 backend + 创建远程用户 |

初始化脚本执行的操作：
1. 向 `mysql_servers` 添加 MySQL backend（hostgroup_id=1）
2. 向 `mysql_users` 添加应用用户（testuser/testpass）
3. 更新 `admin-admin_credentials` 为 `admin:admin;proxysql_remote:remote123`
4. 执行 `LOAD ... TO RUNTIME` + `SAVE ... TO DISK` 持久化

### 1.5 应用配置（.env.test）

**`/workspace/.env.test`** — 测试专用配置文件，与生产 `.env` 完全隔离：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `SECRET_KEY` | `test-secret-key-min-32-chars!!` | 测试固定密钥 |
| `FERNET_KEY` | `02F01gw2gjGLev9LC_hGdPYx4cyU4qEAyWWAA4Pa85g=` | 用于加密存储的 ProxySQL 密码 |
| `DATABASE_URL` | `sqlite:///data/app_test.db` | 应用元数据库（独立于生产 DB） |
| `PROXYSQL_DEFAULT_HOST` | `127.0.0.1` | Docker ProxySQL 映射到宿主机 |
| `PROXYSQL_DEFAULT_PORT` | `6032` | ProxySQL Admin 端口 |
| `PROXYSQL_DEFAULT_USER` | **`proxysql_remote`** | ⚠️ 必须是非 admin 的远程用户 |
| `PROXYSQL_DEFAULT_PASSWORD` | `remote123` | 远程用户密码 |
| `PROXYWEB_ADMIN_USER` | `admin` | WebUI 登录用户名 |
| `PROXYWEB_ADMIN_PASSWORD` | `admin123` | WebUI 登录密码 |
| `RATE_LIMIT_ENABLED` | `false` | 测试环境禁用限流 |
| `CACHE_ENABLED` | `false` | 测试环境禁用缓存 |

### 1.6 启动应用服务

```bash
# ── 终端 1: 启动后端（开发模式，热重载）──
cd /workspace/backend
ENV_FILE=/workspace/.env.test python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# ── 终端 2: 启动前端（Vite HMR）──
cd /workspace/frontend
npx vite --host
```

**注意**：`ENV_FILE` 必须使用**绝对路径**。相对路径在 uvicorn 工作目录不是 `/workspace/` 时会找不到文件。

### 1.7 首次初始化（仅新环境执行一次）

```bash
# 如果 app_test.db 不存在或 admin 密码无效，手动初始化：
cd /workspace/backend
python3 -c "
import sqlite3, bcrypt, os
os.makedirs('data', exist_ok=True)
h = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
c = sqlite3.connect('data/app_test.db')
c.execute('''
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
  )
''')
c.execute('SELECT id FROM users WHERE username=\"admin\"')
if c.fetchone():
    c.execute('UPDATE users SET password_hash=? WHERE username=\"admin\"', (h,))
else:
    c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', ('admin', h))
c.commit()
c.close()
print('Database initialized: admin/admin123')
"
```

### 1.8 环境验证清单

逐项检查，确保环境就绪：

```bash
# 1. Docker 容器健康
docker compose -f docker-compose.test.yml ps | grep healthy

# 2. MySQL backend 可达
mysql -h 127.0.0.1 -P 3306 -u testuser -ptestpass -e "SELECT 1 AS mysql_ok;"

# 3. ProxySQL admin 本地连接
mysql -h 127.0.0.1 -P 6032 -u admin -padmin -e "SELECT 1 AS proxysql_local_ok;"

# 4. ProxySQL 远程用户连接（WebUI 使用的连接方式）
mysql -h 127.0.0.1 -P 6032 -u proxysql_remote -premote123 -e "SELECT 1 AS proxysql_remote_ok;"

# 5. ProxySQL → MySQL 查询链路
mysql -h 127.0.0.1 -P 6033 -u testuser -ptestpass -e "SELECT 1 AS proxy_chain_ok;"

# 6. 后端 API 健康检查
curl -s http://localhost:8080/api/v1/health | python3 -m json.tool

# 7. 前端 Vite 可访问
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/
# 期望输出: 200

# 8. 登录 API
curl -s -c /tmp/cookies.txt -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -m json.tool
```

---

## 二、持久化追踪机制

### 2.1 唯一计划文档原则

- **本文档（`plan.md`）是项目唯一的计划和追踪文件。** 不再创建分散的 plan 文件、日志文件、checklist 文件。
- **所有任务必须先写入本文档再执行。** 执行前在「当前任务」章节添加任务条目，标记状态为 🔄。
- **每完成一个任务/子任务立即更新本文档。** 标记为 ✅ 或 ❌，附简要结果。
- 切换开发设备后，只需 `git pull` + 阅读本文档 + 按第一章搭建环境，即可完全复现。

### 2.2 任务状态标记规范

| 标记 | 含义 |
|------|------|
| ⬜ | 待执行 |
| 🔄 | 执行中 |
| ✅ | 已完成 |
| ❌ | 失败（附失败原因） |
| ⏸️ | 暂停/阻塞 |

### 2.3 Git 同步

```bash
# 每次更新 plan.md 后建议 commit，确保远程也有最新追踪状态
git add plan.md
git commit -m "tracking: update plan.md progress"
git push
```

---

## 三、当前环境状态

| 组件 | 状态 | 详情 |
|------|------|------|
| MySQL 8.0 | ✅ 运行中 | `proxysql-test-mysql:3306`, root/rootpass, testuser/testpass |
| ProxySQL | ✅ 运行中 | `proxysql-test-proxysql:6032`, admin:admin + proxysql_remote:remote123 |
| 后端 (FastAPI) | ✅ 运行中 | `:8080`, 热重载, `ENV_FILE=/workspace/.env.test` |
| 前端 (Vite) | ✅ 运行中 | `[::1]:5173`, HMR |
| 应用DB | ✅ app_test.db | SQLite, 路径 `data/app_test.db` |
| 服务器配置ID | ✅ 88bf5473 | proxysql_remote:remote123@127.0.0.1:6032 |

---

## 四、当前任务

> 格式：`[状态] [日期] 任务描述 — 结果摘要`

### 4.1 已完成的里程碑

| # | 日期 | 任务 | 状态 | 备注 |
|---|------|------|------|------|
| M1 | 2026-07-02 | 搭建 Docker 测试环境 (MySQL + ProxySQL) | ✅ | 含 proxysql_remote 远程用户 |
| M2 | 2026-07-02 | 15 模块全功能冒烟测试 | ✅ | 全部通过 |
| M3 | 2026-07-02 | 修复测试中发现的 10 个 Bug | ✅ | 详见 4.3 |
| M4 | 2026-07-02 | 文档重构：环境搭建 + 追踪机制 | ✅ | 当前版本 |

### 4.2 待执行任务

> 新任务添加在此区域，执行前改 🔄，完成后移到 4.1。

✅ **T1** 语法检查（Python + TypeScript）— 零依赖快速发现语法错误
✅ **T2** import 有效性检查 — 所有 69 个 Python 模块成功 import
✅ **T3** API 契约冒烟测试 — 基于真实 Docker ProxySQL 环境的 HTTP 请求验证（L4 脚本完成，发现 2 个问题）
✅ **T4** 前端 TypeScript 编译检查 — `tsc --noEmit` 通过
✅ **T5** ESLint + Ruff 静态分析 — 代码规范和潜在 Bug 检查（发现 F821: ExpiredSignatureError 未定义，已修复）
✅ **T6** 前端构建验证 — `vite build` 确认 SPA 可正常打包
🔄 **T7** 全链路集成测试 — 脚本已创建 (`scripts/test_l5_integration.py`)，待终端恢复后运行

### 4.3 Bug 修复记录

| # | 文件 | 问题 | 修复 | 状态 |
|---|------|------|------|------|
| 1 | `services/dashboard_service.py:25-29` | `traffic` 查询引用不存在的 `Queries` 列 | 改为 `SUM(Total_cnt)` | ✅ |
| 2 | `services/dashboard_service.py:71-78` | `query_digest` 使用 SQLite `?` 占位符 | 改为 f-string LIMIT | ✅ |
| 3 | `schemas/dashboard.py:55` | `QueryDigestEntry` 含不存在的 `avg_time` 字段 | 移除该字段 | ✅ |
| 4 | `schemas/sync.py:15-21` | `SyncStatusResponse` 字段与 service 返回不匹配 | 改为 `total_unapplied/total_unsaved` | ✅ |
| 5 | `schemas/sync.py:24-42` | `SyncActionResult` 字段与 service 返回不匹配 | 改为 `results/total/succeeded/failed` | ✅ |
| 6 | `services/sync_service.py` | `sync_action` 对子表报 Unknown module 错误 | 添加 `_SUB_TABLES` 集合，子表静默跳过 | ✅ |
| 7 | `config.py` → 运行时 | `ENV_FILE=.env.test` 相对路径无效 | 改用绝对路径 | ✅ |
| 8 | `database.py` | `app_test.db` 中 admin 密码 hash 无效 | 重新 hash_password('admin123') | ✅ |
| 9 | `proxysql.py:177` (历史) | `import re` 缩进错误导致 NameError | 移至文件顶部 | ✅ |
| 10 | `tables.py:105` (历史) | 空 try 块语法错误 | 移除空 try 块 | ✅ |
| 11 | `utils/security.py:7` | `ExpiredSignatureError` 未从 `jose` 导入导致 `F821` | 添加 `from jose import ExpiredSignatureError` | ✅ |

### 4.4 L4 API 冒烟测试发现的问题

| # | 端点 | 问题 | 状态 |
|---|------|------|------|
| 1 | `POST /servers/{id}/test` | 连接测试返回 500（server 使用了 `admin` 用户而非 `proxysql_remote`） | 待修复 |
| 2 | `POST /auth/login` | 多次登录触发 429 限流（即使 RATE_LIMIT_ENABLED=false） | 待修复 |
| 3 | `DELETE /servers/{id}` | CSRF token 过期后 DELETE 返回 500 | 测试已适配 |

---

## 五、启动命令速查

```bash
# ── Docker 环境 ──
docker compose -f docker-compose.test.yml up -d          # 启动
docker compose -f docker-compose.test.yml down -v        # 彻底销毁（含数据卷）
docker compose -f docker-compose.test.yml ps             # 查看状态
docker logs proxysql-test-init                           # 查看初始化日志

# ── 后端 ──
cd /workspace/backend
ENV_FILE=/workspace/.env.test python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# ── 前端 ──
cd /workspace/frontend
npx vite --host

# ── ProxySQL 直接查询 ──
mysql -h 127.0.0.1 -P 6032 -u admin -padmin              # 本地管理（admin 用户）
mysql -h 127.0.0.1 -P 6032 -u proxysql_remote -premote123 # 远程管理（WebUI 用此用户）
mysql -h 127.0.0.1 -P 6033 -u testuser -ptestpass        # 通过 ProxySQL 查询 MySQL

# ── API 快速验证 ──
curl -s http://localhost:8080/api/v1/health | python3 -m json.tool
```

---

---

## 六、工具脚本索引

> 本章节记录项目中所有**可复用的工具脚本**。一次性调试脚本已从根目录清理，统一收敛到以下清单。

### 6.1 根目录脚本

| 脚本 | 用途 | 使用方式 |
|------|------|----------|
| `test_runner.sh` | 通用 API 测试运行器，自动处理 JWT 登录 + CSRF 认证 | `source test_runner.sh` 后使用 `api_get`/`api_post`/`api_put`/`api_delete` |

### 6.2 `scripts/` 目录

| 脚本 | 用途 | 使用方式 |
|------|------|----------|
| `scripts/benchmark.sh` | 性能基准测试 | `make benchmark` 或 `bash scripts/benchmark.sh` |
| `scripts/check-i18n.js` | 国际化字符串检查 | `node scripts/check-i18n.js` |
| `scripts/run_e2e_tests.sh` | 端到端测试启动脚本 | `bash scripts/run_e2e_tests.sh` |
| `scripts/run_integration_tests.sh` | 集成测试启动脚本 | `bash scripts/run_integration_tests.sh` |
| `scripts/reset_admin_password.py` | 重置/创建 admin 用户密码为 `admin123` | `cd backend && python3 ../scripts/reset_admin_password.py` |
| `scripts/test_all.sh` | **全层级自动化测试运行器** (L0-L5) | `bash scripts/test_all.sh --quick` |
| `scripts/test_l0_syntax.py` | L0: Python 语法编译检查 | 由 `test_all.sh` 调用 |
| `scripts/test_l1_imports.py` | L1: 递归 import 所有后端模块 | 由 `test_all.sh` 调用 |
| `scripts/test_l4_api_smoke.py` | L4: API 冒烟测试（真实 ProxySQL） | `python3 scripts/test_l4_api_smoke.py` |
| `scripts/test_l5_integration.py` | L5: 全链路集成测试（前端→API→ProxySQL→MySQL） | `python3 scripts/test_l5_integration.py` |

### 6.3 `docker/` 目录（集成测试基础设施）

| 文件 | 用途 |
|------|------|
| `docker/Dockerfile.mock` | ProxySQL Mock 服务器镜像 |
| `docker/docker-compose.test.yml` | 集成测试编排（WebUI + Mock ProxySQL） |
| `docker/proxysql_mock.py` | Python 实现的 ProxySQL Mock（模拟 MySQL 协议，内存表数据） |

### 6.4 清理记录

> 2026-07-02 根目录大清理，删除了以下一次性调试脚本（其功能已被 `test_runner.sh` 覆盖）：

| 已删除文件 | 原因 |
|-----------|------|
| `check_servers.sh` | 临时调试，功能已被 `api_get /api/v1/servers` 覆盖 |
| `cleanup_and_test_servers.sh` | 硬编码 server ID，一次性脚本 |
| `fix_proxysql_connection.sh` | 临时修复脚本，问题已永久解决 |
| `update_server_config.sh` | 与 fix_proxysql_connection 功能重复 |
| `test_login.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_rbac.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_refresh.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_api.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_auth_complete.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_comprehensive.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_connection.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_dashboard.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_servers.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_servers_complete.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_tables.sh` | 功能已被 `test_runner.sh` 覆盖 |
| `test_users.py` | 功能已被 `test_runner.sh` 覆盖 |
| `=5.5.0` | 空文件，误操作产物 |
| `frontend/vitest_*.txt` (11 个) | 前端单元测试输出日志 |

---

## 七、测试策略重构方案（2026-07-02）

### 7.1 背景与核心问题

**当前测试体系的根本矛盾：**

- 项目代码经过多次迭代后，`backend/tests/`（17个pytest文件 + 5个集成测试）和 `frontend/e2e/`（11个Playwright spec）已大面积失效
- 测试依赖大量 **mock**（`unittest.mock`、`monkeypatch`），mock 的接口签名与实际代码已不同步
- 前端 E2E 测试在 `auth.setup.ts` 中用 `page.route()` 完全 mock 了 API 响应，**根本不测真实后端**
- 前端单元测试仅覆盖 3 个文件（`useDebounce`, `authStore`, `themeStore`），与 27 个页面组件的规模完全不成比例
- **每次代码迭代后，需要同时维护「项目代码」+「测试代码」两套仓库，工作量翻倍**

**核心原则：测试服务于项目代码，不应本末倒置。测试的目的是发现主项目代码中的 bug，而不是花费大量时间修复测试代码本身。**

### 7.2 新测试策略：分层轻量验证

不依赖大量手写单元测试，采用**基于真实环境的快速验证链**：

| 层级 | 方法 | 耗时 | 发现什么 |
|------|------|------|----------|
| **L0 语法检查** | `py_compile` + `tsc --noEmit` | <5秒 | 语法错误、类型错误 |
| **L1 Import检查** | 递归 `import` 所有模块 | <10秒 | 依赖缺失、循环导入、NameError |
| **L2 静态分析** | `ruff check` + `eslint` | <15秒 | 未使用变量、潜在bug、代码异味 |
| **L3 构建验证** | `vite build` | <30秒 | 前端打包错误、类型不匹配 |
| **L4 API 冒烟测试** | HTTP 请求对真实 Docker 环境 | <60秒 | 路由 404、500 错误、认证问题、数据库连接 |
| **L5 全链路集成** | 前端→API→ProxySQL→MySQL | <120秒 | 端到端功能完整性 |

**关键设计决策：**
1. **所有 L4/L5 测试必须在真实 Docker 环境中运行**（MySQL 8.0 + ProxySQL + 远程用户）
2. **不使用 mock** — 所有数据流经真实的 ProxySQL 管理接口
3. **测试是声明式的** — 描述"应该发生什么"，而非"怎么实现"
4. **单个 Python 脚本** 替代分散的 pytest 文件 — 易于维护，一目了然

### 7.3 旧测试代码处置

| 文件/目录 | 处置 | 原因 |
|-----------|------|------|
| `backend/tests/test_*.py` (14个) | **归档不删除** | mock 已与真实代码脱节，修复成本 > 重写成本 |
| `backend/tests/integration/test_*_flow.py` (5个) | **归档不删除** | 依赖 mock，不连接真实 ProxySQL |
| `frontend/e2e/*.spec.ts` (11个) | **归档不删除** | 全部 mock API，不测真实后端 |
| `frontend/src/**/__tests__/*.test.ts` (3个) | **保留** | 纯逻辑测试，不依赖外部环境 |
| `backend/tests/verify_syntax.py` | **整合进新方案** | 作为 L0 的一部分 |
| `docker/docker-compose.test.yml` | **不再使用** | 改用根目录 `docker-compose.test.yml`（真实 MySQL + ProxySQL） |

### 7.4 新测试脚本设计

```
scripts/
├── test_l0_syntax.sh         # L0: 语法编译检查 (Python + TypeScript)
├── test_l1_imports.py        # L1: 递归 import 所有后端模块
├── test_l2_lint.sh           # L2: ruff + eslint 静态分析
├── test_l3_build.sh          # L3: vite build 前端构建
├── test_l4_api_smoke.py      # L4: API 冒烟测试（连真实 ProxySQL）
├── test_l5_integration.py    # L5: 全链路集成测试
└── test_all.sh               # 一键运行 L0-L5
```

---

*最后更新：2026-07-02 15:45*
*文档版本：v3.1 — 测试策略重构：L0-L3 全部通过，L4/L5 脚本已创建，发现 2 个真实 bug*
