# 快速入门

本指南帮助你在 5 分钟内完成 ProxySQL Admin WebUI 的安装和初始配置。

---

## 1. 什么是 ProxySQL Admin WebUI

ProxySQL Admin WebUI 是一个现代化的 **Web 图形化管理界面**，用于管理 [ProxySQL](https://proxysql.com/) 数据库代理服务器。

**核心能力：**

- 无需手写 SQL 即可完成配置（通过 63 个向导）
- 实时监控连接数、QPS、连接池等关键指标
- 管理多个 ProxySQL 实例
- 支持 MySQL 和 PostgreSQL 后端
- 完整的 DISK/MEMORY/RUNTIME 三层配置同步

---

## 2. 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Linux (任何发行版) | Ubuntu 22.04+ / Debian 12+ |
| Python | 3.10+ | 3.12+ |
| Node.js | 24+ (仅开发模式) | 24+ (latest LTS) |
| 内存 | 512 MB | 2 GB+ |
| 磁盘 | 100 MB | 1 GB+ |
| Docker | 24.0+ | 27.0+ |
| ProxySQL | 2.7+ | 3.0+ |

---

## 3. 安装方式

### 方式一：Docker 部署（推荐生产环境）

```bash
# 拉取 Docker 镜像
docker pull ghcr.io/xzydm/proxysql-admin-webui:latest

# 创建环境变量文件
cp .env.example .env
# 编辑 .env，生成并设置 SECRET_KEY 和 FERNET_KEY

# 启动服务
docker compose up -d

# 访问 http://localhost:8080
```

### 方式二：发行版压缩包部署

从 [GitHub Releases](https://github.com/xzydm/proxysql-admin-webui/releases) 下载对应平台的压缩包：

```bash
# 解压
tar xzf proxysql-admin-webui-v1.0.0-linux-amd64.tar.gz
cd proxysql-admin-webui

# 安装依赖
cd backend && pip install -r requirements.txt && cd ..

# 配置环境变量
cp .env.example .env
vim .env

# 启动
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080

# 访问 http://localhost:8080
```

### 方式三：源码运行（开发环境）

```bash
git clone https://github.com/xzydm/proxysql-admin-webui.git
cd proxysql-admin-webui

make install          # 安装依赖
make build-frontend   # 构建前端
make run              # 启动服务 → http://localhost:8080
```

### 方式四：开发模式（热重载）

```bash
make install

# 终端 1：后端热重载 (:8080，仅提供 API)
make dev-backend

# 终端 2：前端 Vite 热重载 (:5173，API 自动代理)
make dev-frontend

# 访问 http://localhost:5173
```

---

## 4. 首次登录与修改密码

1. 打开浏览器访问 `http://localhost:8080`
2. 使用默认凭证登录：
   - 用户名：`admin`
   - 密码：`admin`
3. **首次登录后立即修改密码**：
   - 点击右上角用户头像 →「修改密码」
   - 输入当前密码和新密码
   - 新密码需满足复杂度要求（至少 8 位，包含大小写字母和数字）

---

## 5. 界面概览

```
┌──────────────────────────────────────────────────────┐
│  顶部导航栏                          [语言] [主题] [用户] │
├──────────┬───────────────────────────────────────────┤
│          │                                           │
│  侧边栏   │              主内容区域                    │
│          │                                           │
│  · 仪表盘 │  显示当前选择的功能页面内容                  │
│  · 服务器  │                                           │
│  · 配置向导│                                           │
│  · 表浏览器│                                           │
│  · SQL控制台│                                          │
│  · 配置同步│                                           │
│  · 集群管理│                                           │
│  · 用户管理│                                           │
│  · 系统设置│                                           │
│          │                                           │
├──────────┴───────────────────────────────────────────┤
│  底部状态栏              当前服务器 │ WebSocket 连接状态    │
└──────────────────────────────────────────────────────┘
```

---

## 6. 下一步

- 阅读[用户手册](USER_MANUAL.md)了解各功能模块的详细操作
- 查阅[配置向导参考](WIZARD_GUIDE.md)了解 63 个向导的完整信息
- 参考[部署指南](DEPLOYMENT.md)进行生产环境部署
