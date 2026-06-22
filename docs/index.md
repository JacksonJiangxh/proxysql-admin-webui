# ProxySQL Admin WebUI

<p align="center">
  <strong>现代化的 ProxySQL 图形化管理界面</strong>
</p>

<p align="center">
  <strong>版本 v1.0.0</strong>
</p>

---

## 简介

**ProxySQL Admin WebUI** 是一个现代的 Web 图形化管理界面，用于管理 [ProxySQL](https://proxysql.com/) 数据库代理服务器。它通过 ProxySQL 的 MySQL 管理端口（默认 6032）提供配置可视化、实时监控和运维操作。

### 核心能力

- 🧙 **无需手写 SQL** — 通过 63 个配置向导完成所有操作
- 📊 **实时监控** — 连接数、QPS、连接池等关键指标，WebSocket 实时推送
- 🖥️ **多实例管理** — 同时管理多个 ProxySQL 实例
- 🗄️ **双数据库支持** — MySQL 和 PostgreSQL 后端
- 🔄 **三层配置同步** — 完整的 DISK / MEMORY / RUNTIME 三层管理
- 🔐 **企业级安全** — JWT 认证 + RBAC + 审计日志 + CSRF 防护

### 适用场景

| 场景 | 说明 |
|------|------|
| 🏢 **生产运维** | 日常配置管理、监控、故障排查 |
| 🔧 **快速部署** | Docker 一键部署，3 分钟上手 |
| 📊 **性能分析** | 慢查询分析、连接池监控、规则命中统计 |
| 🌐 **集群管理** | 多 ProxySQL 节点统一管理、配置同步 |
| 🛡️ **安全合规** | SQL 注入防护、审计日志、多角色权限 |

---

## 快速导航

| 章节 | 说明 |
|------|------|
| [快速入门](getting-started.md) | 安装、登录、界面概览 |
| [用户手册](USER_MANUAL.md) | 各功能模块详细操作指南 |
| [配置向导参考](WIZARD_GUIDE.md) | 63 个向导完整说明 |
| [安装与部署](DEPLOYMENT.md) | Docker / 裸机 / Kubernetes 部署 |
| [配置参考](configuration.md) | 环境变量和参数详解 |
| [故障排除](troubleshooting.md) | 常见问题及解决方案 |

---

## 系统要求

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

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + TailwindCSS |
| 后端 | Python 3.10+ / FastAPI + uvicorn |
| 数据 | SQLite (WAL 模式)、aiosqlite |
| 实时 | WebSocket (FastAPI 原生) |
| 认证 | JWT + bcrypt + Fernet |
| 状态管理 | Zustand |
| 构建 | Docker 多阶段 |
| CI/CD | GitHub Actions |
| 测试 | pytest、Playwright |
