# Changelog

所有值得注意的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [1.0.0] — 2026-06-22

### 首次正式发布

经过 14 周的开发，ProxySQL Admin WebUI v1.0.0 正式发布。这是一个现代化的 ProxySQL 图形化管理界面，提供了从配置可视化、向导式部署到集群管理的完整功能。

### 新增

#### 仪表盘与监控

- 实时仪表盘：连接数、QPS、连接池状态、数据延迟等核心指标
- WebSocket 实时推送：无需手动刷新，数据自动更新
- 后端服务器拓扑可视化：直观展示主从、Galera、Group Replication 拓扑关系
- 暗色主题：支持亮色/暗色模式切换，持久化偏好

#### 配置向导（63 个向导，W01-W63）

- **后端服务器管理 (W01-W08)**：添加/编辑/批量导入 MySQL/PgSQL 后端、SSL 配置、连接测试
- **后端用户管理 (W09-W15)**：创建/编辑/管理后端用户、前后端分离
- **查询路由规则 (W16-W23)**：读写分离、缓存/重写/镜像规则、限流、日志规则
- **复制与集群拓扑 (W24-W28)**：主从、Group Replication、Galera、Aurora、PgSQL 复制
- **系统配置 (W29-W42)**：连接池参数、查询处理、Admin 用户、集群节点/同步
- **防火墙与安全 (W43-W45)**：用户/规则白名单、SQL 注入防护
- **运维与配置同步 (W46-W52)**：Apply All、Save All、配置备份/恢复、磁盘加载
- **监控与诊断 (W53-W63)**：查询分析、命令/规则统计、连接池/进程面板、集群状态

#### 表浏览器

- 浏览和编辑全部 ProxySQL 配置表（20+ 张表）
- 分页、搜索、排序、内联编辑功能
- 表结构信息展示

#### SQL 查询控制台

- 多目标执行：Admin / MySQL / PostgreSQL 三种查询目标
- 查询历史记录持久化
- SQL 语法高亮
- 结果导出（CSV/JSON）

#### 配置同步

- DISK ↔ MEMORY ↔ RUNTIME 三层配置管理
- 按模块同步（全局变量、查询规则、MySQL 服务器等）
- 配置差异对比：Disk/Memory/Runtime 三层差异可视化，行级对比
- 安全的原子写入

#### 多实例管理

- 添加、编辑、测试多个 ProxySQL 服务器连接
- 一键切换当前管理的实例
- 连接状态实时监控

#### 集群管理

- ProxySQL 原生集群组管理（创建、编辑、删除）
- 集群节点自动发现（读取 proxysql_servers 表）
- 跨节点配置同步（源节点 RUNTIME → 目标节点 MEMORY → LOAD TO RUNTIME → SAVE TO DISK）
- 集群节点状态监控（在线/离线、版本、运行时间、checksum 一致性）
- 集群变量批量配置（admin-cluster_* 系列）
- 集群同步审计日志

#### 认证与安全

- JWT 认证（Access Token + Refresh Token）
- 多用户 + RBAC：Admin / Operator / Viewer 三种角色
- bcrypt 密码哈希
- Fernet 加密存储 ProxySQL 凭证
- CSRF 双提交 Cookie 防护
- SQL 注入防护策略
- 登录暴力破解防护
- 审计日志：记录所有配置变更操作

#### 国际化 (i18n)

- 默认语言：简体中文
- 内置英文翻译
- 支持扩展更多语言
- 语言偏好持久化到 localStorage

#### 部署

- Docker 多阶段构建（Node 前端构建 + Python 运行时）
- Docker Compose 一键部署
- Docker Compose 集成测试环境（含 ProxySQL Mock）
- GitHub Actions CI/CD 流水线（lint、test、build、集成测试、Docker 发布）

#### 文档

- README.md：项目概览、快速开始、功能列表
- TECHNICAL_DOCUMENTATION.md：完整技术架构、API 规范、数据模型、安全设计
- CONTRIBUTING.md：开发环境设置、编码规范、贡献流程
- docs/USER_MANUAL.md：面向最终用户的完整操作指南（11 章）
- docs/WIZARD_GUIDE.md：63 个向导详细参考文档
- docs/DEPLOYMENT.md：生产部署指南（Docker/裸机/K8s）
- SECURITY.md：安全策略和漏洞报告

#### 测试

- 单元测试（13 个测试文件）：auth、api_integration、codegen、helpers、schema、security、services、sync、users、wizards
- 集成测试（Docker Compose + ProxySQL Mock 环境）
- E2E 测试（Playwright，3 个测试文件）
- 代码检查：ruff (Python) + ESLint (TypeScript)

### 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + TailwindCSS |
| 后端 | Python 3.10+ / FastAPI + uvicorn |
| 数据 | SQLite (WAL 模式)、aiosqlite |
| 实时 | WebSocket (FastAPI 原生) |
| 认证 | JWT + bcrypt + Fernet |
| 状态管理 | Zustand |
| 构建 | Docker 多阶段、GitHub Actions |
| 测试 | pytest、Playwright |

### 从参考项目继承

本项目继承并融合了三个参考项目的设计和代码：

- **proxui**：FastAPI CRUD 代码生成管道、三层配置同步 API、uPlot 实时图表方案、优雅降级策略
- **proxyweb**：原子写入 `_atomic_write()`、SQL 注入防护策略、配置 Diff 算法、Docker Compose 测试环境
- **proxysql-admin-ui**：分层架构 (Pages → Services → Models)、企业级认证 RBAC 模型、组件化 UI 设计

---

## 版本规范

本项目遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)：

- **MAJOR**：不兼容的 API 修改
- **MINOR**：向下兼容的功能新增
- **PATCH**：向下兼容的问题修正

---

[1.0.0]: https://cnb.cool/xzydm/proxysql-admin-webui/-/releases/tag/v1.0.0
