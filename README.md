# ProxySQL Admin WebUI

<p align="center">
  <strong>现代化的 ProxySQL 图形化管理界面</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://cnb.cool/xzydm/proxysql-admin-webui/-/releases"><img src="https://img.shields.io/badge/release-v1.0.0-blue" alt="Release"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/node-24+-green.svg" alt="Node.js 24+">
  <img src="https://img.shields.io/badge/docker-24.0+-2496ED.svg" alt="Docker 24.0+">
</p>

<p align="center">
  <a href="https://jacksonjiangxh.github.io/proxysql-admin-webui/"><strong>📖 用户手册</strong></a>
  &nbsp;·&nbsp;
  <a href="#快速开始">🚀 快速开始</a>
  &nbsp;·&nbsp;
  <a href="#镜像仓库">📦 Docker 镜像</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/JacksonJiangxh/proxysql-admin-webui/releases">📋 发行版</a>
</p>

---

## 简介

**ProxySQL Admin WebUI** 是一个现代化的 Web 图形化管理界面，通过 ProxySQL 的 MySQL 协议管理端口（默认 6032）提供配置可视化、实时监控和运维操作。

> 📖 **完整用户手册请访问：** https://jacksonjiangxh.github.io/proxysql-admin-webui/

### 核心架构

```
浏览器 (React SPA) ──HTTP/WebSocket──▶ FastAPI 单进程 (:8080) ──MySQL 协议──▶ ProxySQL Admin (:6032)
                                           │                                     ──▶ MySQL/PostgreSQL 后端
                                           └─ 同源托管前端静态文件
```

**单进程部署**：FastAPI 同时提供 REST/WebSocket API 和前端静态文件，无需额外反向代理。支持裸机运行和容器化两种部署方式。

---

## 快速开始

### 前置条件

- Python 3.10+ / Node.js 24+（裸机运行）
- Docker 24.0+（容器部署）
- ProxySQL 2.7+ 实例（完整功能需要）

### Docker 一键部署（推荐）

```bash
docker pull docker.cnb.cool/xzydm/proxysql-admin-webui:latest

# 创建环境变量
cp .env.example .env
# 编辑 .env，修改 SECRET_KEY 和 FERNET_KEY

# 启动
docker compose up -d

# 访问 http://localhost:8080
# 默认登录：admin / admin
```

### 裸机运行

```bash
make install          # 安装依赖
make build-frontend   # 构建前端
make run              # 启动服务 → http://localhost:8080
```

### 开发模式（热重载）

```bash
make install
make dev-backend      # 终端1：后端 :8080
make dev-frontend     # 终端2：前端 :5173 → http://localhost:5173
```

---

## 功能特性

| 模块 | 说明 |
|------|------|
| 📊 **仪表盘** | 实时监控连接数、QPS、连接池状态，WebSocket 推送 |
| 🧙 **配置向导** | 63 个引导式表单（W01-W63），无需手写 SQL |
| 📋 **表浏览器** | 查看/编辑所有 ProxySQL 配置表，分页、搜索、排序、内联编辑 |
| 💻 **SQL 控制台** | 专家模式，支持 Admin / MySQL / PostgreSQL 多目标执行 |
| 🔄 **配置同步** | DISK ↔ MEMORY ↔ RUNTIME 三层管理，按模块同步 |
| 🔍 **配置差异** | Disk / Memory / Runtime 三层差异可视化，行级对比 |
| 🖥️ **多实例管理** | 管理多个 ProxySQL 服务器，连接测试，一键切换 |
| 🌐 **集群管理** | ProxySQL 原生集群组管理，跨节点配置同步，状态监控 |
| 🔐 **JWT 认证** | 多用户 + RBAC（Admin / Operator / Viewer） |
| 📝 **审计日志** | 记录所有配置变更，按时间查询和清理 |
| 🌍 **国际化** | 默认中文，内置英文，支持扩展更多语言 |
| 🎨 **暗色主题** | 亮色/暗色模式切换，偏好持久化 |

---

## 文档

| 文档 | 链接 | 说明 |
|------|------|------|
| 📖 用户手册 | https://jacksonjiangxh.github.io/proxysql-admin-webui/ | 面向最终用户的完整操作指南 |
| 🤝 贡献指南 | [CONTRIBUTING.md](CONTRIBUTING.md) | 开发环境设置、编码规范、PR 流程 |
| 📋 变更日志 | [CHANGELOG.md](CHANGELOG.md) | 版本发布历史和变更记录 |

---

## 镜像仓库

预构建的 Docker 镜像：

```
docker.cnb.cool/xzydm/proxysql-admin-webui:latest     # 最新稳定版
docker.cnb.cool/xzydm/proxysql-admin-webui:v1.0.0     # 指定版本
docker.cnb.cool/xzydm/proxysql-admin-webui:1           # 主版本号
```

也可从 GitHub Container Registry 拉取：

```
ghcr.io/jacksonjiangxh/proxysql-admin-webui:latest
```

支持的架构：`linux/amd64`、`linux/arm64`

---

## 许可证

本项目基于 [MIT License](LICENSE) 开源。

Copyright (c) 2026 JacksonJiangxh
