# ProxySQL Admin WebUI — 配置向导完整指南

> **版本**: v1.0.0  
> **更新日期**: 2026-07-04  
> **向导总数**: 70 个（W01-W70），全部已实现  
> **模板**: 1 个快速部署模板（T01），支持 5 种架构模式  
> **语言**: 简体中文

---

## 目录

- [1. 向导系统介绍](#1-向导系统介绍)
- [2. 向导引擎架构（简化）](#2-向导引擎架构简化)
- [3. 完整向导目录](#3-完整向导目录)
  - [3.1 后端服务器管理 (W01-W08, W64-W65)](#31-后端服务器管理-w01-w08-w64-w65)
  - [3.2 后端用户管理 (W09-W15, W66-W68)](#32-后端用户管理-w09-w15-w66-w68)
  - [3.3 查询路由规则 (W16-W23, W69)](#33-查询路由规则-w16-w23-w69)
  - [3.4 复制与集群拓扑 (W24-W28, W70)](#34-复制与集群拓扑-w24-w28-w70)
  - [3.5 系统配置 (W29-W42)](#35-系统配置-w29-w42)
  - [3.6 防火墙与安全 (W43-W45)](#36-防火墙与安全-w43-w45)
  - [3.7 运维与配置同步 (W46-W52)](#37-运维与配置同步-w46-w52)
  - [3.8 监控与诊断 (W53-W63)](#38-监控与诊断-w53-w63)
- [4. 快速部署模板 (T01)](#4-快速部署模板t01)
- [5. 向导使用最佳实践](#5-向导使用最佳实践)
- [6. 常见向导组合（工作流）](#6-常见向导组合工作流)

---

## 1. 向导系统介绍

向导系统是 ProxySQL Admin WebUI 的核心功能之一。它将复杂的 ProxySQL SQL 配置操作封装为**引导式表单**，用户只需填写表单参数即可完成配置，无需记忆 SQL 语法和表结构。

### 向导特点

- **表单驱动**：通过直观的表单字段（文本框、下拉选择、开关、数字输入等）收集参数
- **SQL 预览**：提交前可预览系统将生成的所有 SQL 语句
- **自动同步**：支持自动 Apply（LOAD TO RUNTIME）和自动 Save（SAVE TO DISK）
- **历史记录**：每次执行的操作都会被记录，便于审计和回溯
- **表单验证**：前端和后端双重验证，防止无效参数

### 向导操作流程

```
选择向导 → 填写表单参数 → 预览 SQL → 确认执行 → (可选)自动 Apply → (可选)自动 Save
```

---

## 2. 向导引擎架构（简化）

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (React SPA)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ 向导列表页    │  │ 动态表单组件  │  │ SQL 预览面板      │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
└─────────┼─────────────────┼────────────────────┼────────────┘
          │                 │                    │
          ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                     后端 (FastAPI)                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   Wizard Engine                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │   │
│  │  │ BaseWizard   │  │ validate()  │  │ generate_sql()│ │   │
│  │  │ (抽象基类)   │  │ 表单验证    │  │ SQL 生成      │ │   │
│  │  └─────────────┘  └─────────────┘  └──────────────┘ │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │   │
│  │  │ execute()    │  │ preview_sql()│  │ 自动 Apply    │ │   │
│  │  │ 执行 SQL    │  │ 预览 SQL    │  │ 自动 Save     │ │   │
│  │  └─────────────┘  └─────────────┘  └──────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 ProxySQL Admin (:6032)                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**核心类说明：**

- **`WizardField`**：定义向导表单的单个字段（名称、类型、默认值、验证规则）
- **`WizardDefinition`**：定义向导的元数据（ID、分类、名称、描述、字段列表、目标表）
- **`BaseWizard`**：所有向导的抽象基类，定义了 `validate()` 和 `generate_sql()` 接口
- **`WizardEngine`**：向导注册中心和调度器，管理所有 70 个向导

---

## 3. 完整向导目录

### 3.1 后端服务器管理 (W01-W08, W64-W65)

#### W01 — 添加 MySQL 后端服务器

- **类别**：后端服务器管理
- **用途**：向 `mysql_servers` 表添加一个新的 MySQL 后端服务器
- **何时使用**：需要将新的 MySQL 实例加入 ProxySQL 代理池
- **前置条件**：MySQL 服务已运行且网络可达

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| hostgroup_id | number | 是 | 0 | 主机组 ID |
| hostname | text | 是 | — | 服务器地址（如 10.0.0.1） |
| port | number | 是 | 3306 | 端口号（1-65535） |
| status | radio | 是 | ONLINE | ONLINE / OFFLINE_SOFT / OFFLINE_HARD |
| weight | number | 否 | 1 | 权重（0-10000000） |
| max_connections | number | 否 | 1000 | 最大连接数 |
| max_replication_lag | number | 否 | 0 | 最大复制延迟（秒） |
| use_ssl | toggle | 否 | 0 | 是否启用 SSL |
| max_latency_ms | number | 否 | 0 | 最大延迟（毫秒） |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_servers (hostgroup_id, hostname, port, status, weight, max_connections, max_replication_lag, use_ssl, max_latency_ms, comment)
VALUES (0, '10.0.0.1', 3306, 'ONLINE', 1, 1000, 0, 0, 0, 'primary-db')
```

**相关向导**：W03（批量导入）、W04（编辑服务器）、W05（上下线）、W08（连接测试）

---

#### W02 — 添加 PostgreSQL 后端服务器

- **类别**：后端服务器管理
- **用途**：向 `pgsql_servers` 表添加一个新的 PostgreSQL 后端服务器
- **何时使用**：需要将 PostgreSQL 实例加入 ProxySQL 代理池
- **前置条件**：PostgreSQL 服务已运行且网络可达

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| hostgroup_id | number | 是 | 0 | 主机组 ID |
| hostname | text | 是 | — | 服务器地址 |
| port | number | 是 | 5432 | 端口号 |
| status | radio | 是 | ONLINE | 状态 |
| weight | number | 否 | 1 | 权重 |
| max_connections | number | 否 | 1000 | 最大连接数 |
| use_ssl | toggle | 否 | 0 | 是否启用 SSL |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO pgsql_servers (hostgroup_id, hostname, port, status, weight, max_connections, use_ssl, comment)
VALUES (0, '10.0.0.1', 5432, 'ONLINE', 1, 1000, 0, 'pg-primary')
```

**相关向导**：W28（PgSQL 复制）、W10（创建 PgSQL 用户）

---

#### W03 — 批量导入后端服务器

- **类别**：后端服务器管理
- **用途**：通过 CSV/文本粘贴批量导入多个后端服务器
- **何时使用**：需要一次性添加大量后端服务器
- **前置条件**：准备 CSV 格式的服务器列表

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| target_table | select | 否 | mysql_servers | 目标表（mysql_servers / pgsql_servers） |
| csv_data | textarea | 是 | — | CSV 数据（每行：hg,host,port,status,weight,maxconn,comment） |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_servers (hostgroup_id, hostname, port, status, weight, max_connections, comment)
VALUES (0, '10.0.0.1', 3306, 'ONLINE', 1, 1000, 'primary')
```
（每行输入生成一条 INSERT）

**相关向导**：W01（添加单台服务器）

---

#### W04 — 编辑后端服务器属性

- **类别**：后端服务器管理
- **用途**：修改已有 MySQL 后端服务器的属性（权重、最大连接数等）
- **何时使用**：需要调整服务器权重或连接参数
- **前置条件**：目标服务器已存在于 `mysql_servers` 表

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| hostgroup_id | number | 是 | — | 主机组（标识符） |
| hostname | text | 是 | — | 主机名（标识符） |
| port | number | 是 | 3306 | 端口（标识符） |
| weight | number | 否 | — | 权重 |
| max_connections | number | 否 | — | 最大连接数 |
| max_replication_lag | number | 否 | — | 最大复制延迟 |
| max_latency_ms | number | 否 | — | 最大延迟 |
| compression | number | 否 | — | 压缩 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
UPDATE mysql_servers SET weight = 5, max_connections = 2000
WHERE hostgroup_id = 0 AND hostname = '10.0.0.1' AND port = 3306
```

**相关向导**：W01（添加服务器）、W05（上下线）

---

#### W05 — 服务器上下线

- **类别**：后端服务器管理
- **用途**：将后端服务器设置为 ONLINE、OFFLINE_SOFT 或 OFFLINE_HARD
- **何时使用**：需要临时下线服务器进行维护
- **前置条件**：目标服务器已存在

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| hostgroup_id | number | 是 | — | 主机组 |
| hostname | text | 是 | — | 主机名 |
| port | number | 是 | 3306 | 端口 |
| status | radio | 是 | ONLINE | ONLINE / OFFLINE_SOFT / OFFLINE_HARD |

**三种下线模式说明：**
- **OFFLINE_SOFT**：不再接受新连接，但等待现有连接完成
- **OFFLINE_HARD**：立即断开所有连接
- **ONLINE**：恢复在线状态

**生成 SQL 示例：**
```sql
UPDATE mysql_servers SET status = 'OFFLINE_SOFT'
WHERE hostgroup_id = 0 AND hostname = '10.0.0.1' AND port = 3306
```

**相关向导**：W01（添加服务器）、W04（编辑服务器）

---

#### W06 — 后端服务器 SSL 参数

- **类别**：后端服务器管理
- **用途**：为后端服务器配置 SSL/TLS 连接参数（`mysql_servers_ssl_params` 表）
- **何时使用**：需要加密 ProxySQL 与后端 MySQL 之间的连接
- **前置条件**：已准备 SSL 证书文件

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| hostgroup_id | number | 是 | — | 主机组 |
| hostname | text | 是 | — | 主机名 |
| port | number | 是 | 3306 | 端口 |
| ssl_ca | text | 否 | — | SSL CA 证书路径 |
| ssl_cert | text | 否 | — | SSL 证书路径 |
| ssl_key | text | 否 | — | SSL 私钥路径 |
| ssl_cipher | text | 否 | — | SSL 加密套件 |
| tls_version | text | 否 | — | TLS 版本 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_servers_ssl_params (hostgroup_id, hostname, port, ssl_ca, ssl_cert, ssl_key, ssl_cipher, tls_version)
VALUES (0, '10.0.0.1', 3306, '/etc/ssl/ca.pem', '/etc/ssl/cert.pem', '/etc/ssl/key.pem', 'ECDHE-RSA-AES128-GCM-SHA256', 'TLSv1.2')
```

**相关向导**：W01（添加服务器）、W41（SSL/TLS 全局变量）

---

#### W07 — 主机组属性

- **类别**：后端服务器管理
- **用途**：配置主机组级别的属性（`mysql_hostgroup_attributes` 表）
- **何时使用**：需要为主机组设置多路复用、连接预热等行为
- **前置条件**：主机组已存在

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| hostgroup_id | number | 是 | — | 主机组 ID |
| max_num_online_servers | number | 否 | — | 最大在线服务器数 |
| autocommit | toggle | 否 | — | 自动提交 |
| free_connections_pct | number | 否 | — | 空闲连接百分比 |
| multiplex | number | 否 | — | 多路复用开关 |
| connection_warming | toggle | 否 | — | 连接预热 |
| init_connect | text | 否 | — | 初始连接 SQL |
| throttle_connections_per_sec | number | 否 | — | 每秒连接限速 |
| servers_defaults | text | 否 | — | 服务器默认值 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_hostgroup_attributes (hostgroup_id, max_num_online_servers, multiplex, connection_warming)
VALUES (0, 5, 1, 1)
ON CONFLICT(hostgroup_id) DO UPDATE SET max_num_online_servers=excluded.max_num_online_servers, multiplex=excluded.multiplex, connection_warming=excluded.connection_warming
```

**相关向导**：W01（添加服务器）、W32（多路复用变量）

---

#### W08 — 后端连接测试

- **类别**：后端服务器管理
- **用途**：测试后端服务器连接状态并查看连接池信息（只读）
- **何时使用**：验证后端服务器连通性
- **前置条件**：后端服务器已在 ProxySQL 中配置

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| hostgroup | number | 否 | — | 主机组（可选） |
| hostname | text | 否 | — | 主机名（可选，空=全部） |
| port | number | 否 | — | 端口（可选） |

**生成 SQL 示例：**
```sql
SELECT hostgroup, srv_host, srv_port, status, ConnUsed, ConnFree, ConnOK, ConnERR, Queries, Latency_us
FROM stats_mysql_connection_pool WHERE hostgroup = 0 AND srv_host = '10.0.0.1' AND srv_port = 3306
```

**相关向导**：W57（连接池监控）

---

#### W64 — 删除 MySQL 后端服务器

- **类别**：后端服务器管理
- **用途**：从 `mysql_servers` 表永久删除一台 MySQL 后端服务器
- **何时使用**：服务器永久下线、替换或清理
- **前置条件**：确认服务器不再需要

> ⚠ **危险操作**：删除后不可恢复（除非有 W48 备份）。建议先用 W05 设置为 OFFLINE_SOFT 观察一段时间。

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| hostgroup_id | number | 是 | — | 主机组 |
| hostname | text | 是 | — | 主机名 |
| port | number | 是 | 3306 | 端口 |
| confirm_delete | checkbox | 是 | false | 确认删除（安全确认） |

**生成 SQL 示例：**
```sql
DELETE FROM mysql_servers WHERE hostgroup_id = 0 AND hostname = '10.0.0.1' AND port = 3306
```

**相关向导**：W01（添加服务器）、W05（上下线）、W48（配置备份）

---

#### W65 — 删除 PostgreSQL 后端服务器

- **类别**：后端服务器管理
- **用途**：从 `pgsql_servers` 表永久删除一台 PostgreSQL 后端服务器
- **何时使用**：PostgreSQL 服务器永久下线或替换
- **前置条件**：确认服务器不再需要

> ⚠ **危险操作**：删除后不可恢复。

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| hostgroup_id | number | 是 | — | 主机组 |
| hostname | text | 是 | — | 主机名 |
| port | number | 是 | 5432 | 端口 |
| confirm_delete | checkbox | 是 | false | 确认删除 |

**生成 SQL 示例：**
```sql
DELETE FROM pgsql_servers WHERE hostgroup_id = 0 AND hostname = '10.0.0.1' AND port = 5432
```

**相关向导**：W02（添加 PG 服务器）、W48（配置备份）

---

### 3.2 后端用户管理 (W09-W15, W66-W68)

#### W09 — 创建 MySQL 后端用户

- **类别**：后端用户管理
- **用途**：在 `mysql_users` 表中创建用于后端连接的用户
- **何时使用**：需要添加新的 MySQL 后端认证用户
- **前置条件**：后端 MySQL 服务器中已创建对应账号

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| username | text | 是 | — | 用户名 |
| password | password | 是 | — | 密码 |
| default_hostgroup | number | 是 | 0 | 默认主机组 |
| default_schema | text | 否 | — | 默认数据库 |
| active | toggle | 否 | 1 | 是否激活 |
| max_connections | number | 否 | 10000 | 最大连接数 |
| transaction_persistent | toggle | 否 | 1 | 事务持久化 |
| fast_forward | toggle | 否 | 0 | 快速转发 |
| schema_locked | toggle | 否 | 0 | 锁定 Schema |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_users (username, password, active, use_ssl, default_hostgroup, default_schema, schema_locked, transaction_persistent, fast_forward, backend, frontend, max_connections, comment)
VALUES ('app_user', 'secure_password', 1, 0, 0, '', 0, 1, 0, 1, 1, 10000, 'Application user')
```

**相关向导**：W11（编辑用户）、W12（修改密码）、W13（启用/禁用）

---

#### W10 — 创建 PostgreSQL 后端用户

- **类别**：后端用户管理
- **用途**：在 `pgsql_users` 表中创建用于 PostgreSQL 后端连接的用户
- **何时使用**：需要添加 PgSQL 后端认证用户
- **前置条件**：后端 PostgreSQL 中已创建对应角色

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| username | text | 是 | — | 用户名 |
| password | password | 是 | — | 密码 |
| default_hostgroup | number | 是 | 0 | 默认主机组 |
| active | toggle | 否 | 1 | 是否激活 |
| max_connections | number | 否 | 10000 | 最大连接数 |
| transaction_persistent | toggle | 否 | 1 | 事务持久化 |
| fast_forward | toggle | 否 | 0 | 快速转发 |
| frontend | toggle | 否 | 1 | 前端认证 |
| backend | toggle | 否 | 1 | 后端认证 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO pgsql_users (username, password, active, default_hostgroup, max_connections, transaction_persistent, fast_forward, frontend, backend, comment)
VALUES ('pg_user', 'secure_password', 1, 0, 10000, 1, 0, 1, 1, 'PostgreSQL app user')
```

**相关向导**：W02（添加 PgSQL 服务器）

---

#### W11 — 编辑后端用户属性

- **类别**：后端用户管理
- **用途**：修改已有 MySQL 后端用户的属性
- **何时使用**：需要调整用户的默认主机组、最大连接数等
- **前置条件**：用户已存在于 `mysql_users` 表

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| username | text | 是 | — | 用户名（标识符） |
| default_hostgroup | number | 否 | — | 默认主机组 |
| default_schema | text | 否 | — | 默认数据库 |
| max_connections | number | 否 | — | 最大连接数 |
| transaction_persistent | toggle | 否 | — | 事务持久化 |
| schema_locked | toggle | 否 | — | 锁定 Schema |
| active | toggle | 否 | — | 是否激活 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
UPDATE mysql_users SET default_hostgroup = 1, max_connections = 20000
WHERE username = 'app_user'
```

**相关向导**：W09（创建用户）、W12（修改密码）

---

#### W12 — 修改后端用户密码

- **类别**：后端用户管理
- **用途**：更新已有 MySQL 后端用户的密码
- **何时使用**：需要更新后端数据库密码时
- **前置条件**：用户已存在

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| username | text | 是 | — | 用户名 |
| new_password | password | 是 | — | 新密码 |

**生成 SQL 示例：**
```sql
UPDATE mysql_users SET password = 'new_secure_password'
WHERE username = 'app_user'
```

**相关向导**：W09（创建用户）、W11（编辑用户）

---

#### W13 — 启用/禁用后端用户

- **类别**：后端用户管理
- **用途**：切换 MySQL 后端用户的激活状态
- **何时使用**：需要临时禁用某个用户
- **前置条件**：用户已存在

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| username | text | 是 | — | 用户名 |
| active | toggle | 是 | 1 | 激活状态（0=禁用, 1=启用） |

**生成 SQL 示例：**
```sql
UPDATE mysql_users SET active = 0 WHERE username = 'app_user'
```

**相关向导**：W09（创建用户）

---

#### W14 — LDAP 用户映射

- **类别**：后端用户管理
- **用途**：配置 LDAP 用户映射（`mysql_ldap_mapping` 表），用于企业 LDAP 认证
- **何时使用**：企业环境需要 LDAP 集成
- **前置条件**：LDAP 服务器已部署且可达

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| priority | number | 否 | 1 | 优先级 |
| frontend_entity | text | 是 | — | 前端实体（LDAP 用户/组） |
| backend_entity | text | 是 | — | 后端实体（MySQL 用户） |
| active | toggle | 否 | 1 | 是否激活 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_ldap_mapping (priority, frontend_entity, backend_entity, active, comment)
VALUES (1, 'cn=db_users,dc=company,dc=com', 'app_user', 1, 'LDAP mapping for DB users')
```

**相关向导**：W09（创建用户）

---

#### W15 — ProxySQL 用户方向控制

- **类别**：后端用户管理
- **用途**：控制 `mysql_users` 条目的 `frontend`/`backend` 方向标记
- **何时使用**：需要独立控制前端方向（客户端连接 ProxySQL）和后端方向（ProxySQL 连接 MySQL）的开关状态
- **前置条件**：理解 ProxySQL 的 frontend/backend 是方向控制而非用户名映射。**同一用户名会原样转发到后端 MySQL，ProxySQL 不会做用户名转换。**

> ⚠ **重要澄清**：`frontend=1, backend=0` 单独配置是**无效的**——用户能认证但无法执行任何查询。因为 ProxySQL 始终用客户端提供的用户名去连接后端 MySQL。如果后端 MySQL 上不存在该用户，查询会失败。

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| user_type | select | 是 | both | Both / Backend Only / Split Directions |
| username | text | 是 | — | 用户名 |
| password | password | 是 | — | 密码 |
| default_hostgroup | number | 否 | 0 | 默认主机组 |
| active | toggle | 否 | 1 | 是否激活 |
| max_connections | number | 否 | 10000 | 最大连接数 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
-- Both（标准用户，默认）：frontend=1 backend=1
INSERT INTO mysql_users (username, password, active, default_hostgroup, frontend, backend, max_connections, comment)
VALUES ('app_user', 'password', 1, 0, 1, 1, 10000, '')

-- Backend Only（ProxySQL→MySQL 连接池，客户端不可见）
INSERT INTO mysql_users (username, password, active, default_hostgroup, frontend, backend, max_connections, comment)
VALUES ('app_user', 'password', 1, 0, 0, 1, 10000, 'backend-only')

-- Split Directions（同一用户名拆两行，可独立开关）
INSERT INTO mysql_users (username, password, active, default_hostgroup, frontend, backend, max_connections, comment)
VALUES ('app_user', 'password', 1, 0, 1, 0, 10000, 'frontend direction')
INSERT INTO mysql_users (username, password, active, default_hostgroup, frontend, backend, max_connections, comment)
VALUES ('app_user', 'password', 1, 0, 0, 1, 10000, 'backend direction')
```

**相关向导**：W09（创建用户）

---

#### W66 — 删除 MySQL 后端用户

- **类别**：后端用户管理
- **用途**：从 ProxySQL 永久删除 MySQL 用户记录及关联的 LDAP 映射和快速路由条目
- **何时使用**：不再需要该用户访问 ProxySQL
- **前置条件**：先用 W13 禁用用户确认无影响

> ⚠ **危险操作**：此操作同时清理 `mysql_users`、`mysql_ldap_mapping`、`mysql_query_rules_fast_routing` 中关联该用户的所有记录。不会删除后端 MySQL 上实际的用户账号。

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| username | text | 是 | — | 要删除的用户名 |
| confirm_delete | checkbox | 是 | false | 确认删除 |

**生成 SQL 示例：**
```sql
DELETE FROM mysql_users WHERE username = 'app_user';
DELETE FROM mysql_ldap_mapping WHERE backend_entity = 'app_user';
DELETE FROM mysql_query_rules_fast_routing WHERE username = 'app_user';
```

**相关向导**：W09（创建用户）、W13（禁用用户）、W69（删除查询规则）

---

#### W67 — 删除 PostgreSQL 后端用户

- **类别**：后端用户管理
- **用途**：从 ProxySQL 永久删除 PostgreSQL 用户记录
- **何时使用**：不再需要该用户

> ⚠ **危险操作**：不会删除后端 PostgreSQL 上实际的角色（需单独处理）。

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| username | text | 是 | — | 用户名 |
| confirm_delete | checkbox | 是 | false | 确认删除 |

**生成 SQL 示例：**
```sql
DELETE FROM pgsql_users WHERE username = 'pg_user'
```

**相关向导**：W10（创建 PG 用户）

---

#### W68 — 删除 LDAP 用户映射

- **类别**：后端用户管理
- **用途**：删除 LDAP 用户到 MySQL 后端的映射关系
- **何时使用**：LDAP 集成变更

> ⚠ 只删除映射关系，不影响 LDAP 或 MySQL 账号本身。

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| priority | number | 是 | — | 优先级 |
| frontend_entity | text | 是 | — | 前端实体 |
| backend_entity | text | 是 | — | 后端实体 |
| confirm_delete | checkbox | 是 | false | 确认删除 |

**生成 SQL 示例：**
```sql
DELETE FROM mysql_ldap_mapping WHERE priority = 1 AND frontend_entity = 'cn=db_users' AND backend_entity = 'app_user'
```

**相关向导**：W14（添加映射）、W66（删除用户）

---

### 3.3 查询路由规则 (W16-W23, W69)

#### W16 — 读写分离快速设置

- **类别**：查询路由规则
- **用途**：一键创建完整的读写分离路由规则集
- **何时使用**：需要快速配置读写分离
- **前置条件**：已配置读/写主机组

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| writer_hostgroup | number | 是 | 0 | 写主机组 |
| reader_hostgroup | number | 是 | 1 | 读主机组 |
| check_type | select | 否 | read_only | 检查类型 |
| cluster_name | text | 否 | cluster1 | 集群名称 |
| base_rule_id | number | 否 | 10 | 基础规则 ID |
| rule_select_for_update | checkbox | 否 | true | SELECT FOR UPDATE → Writer |
| rule_dml | checkbox | 否 | true | INSERT/UPDATE/DELETE → Writer |
| rule_select | checkbox | 否 | true | SELECT → Reader |
| rule_transaction | checkbox | 否 | true | Transaction → Writer |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_replication_hostgroups (writer_hostgroup, reader_hostgroup, check_type, comment)
VALUES (0, 1, 'read_only', 'cluster1');

INSERT INTO mysql_query_rules (rule_id, active, match_digest, destination_hostgroup, apply, comment)
VALUES (10, 1, '^SELECT.*FOR UPDATE', 0, 1, 'RW-Split: SELECT FOR UPDATE');

INSERT INTO mysql_query_rules (rule_id, active, match_digest, destination_hostgroup, apply, comment)
VALUES (20, 1, '^(INSERT|UPDATE|DELETE|REPLACE)', 0, 1, 'RW-Split: DML');

INSERT INTO mysql_query_rules (rule_id, active, match_digest, destination_hostgroup, apply, comment)
VALUES (30, 1, '^SELECT', 1, 1, 'RW-Split: SELECT');
```

**相关向导**：W17（添加查询规则）、W24（主从复制配置）

---

#### W17 — 添加查询路由规则

- **类别**：查询路由规则
- **用途**：通过简化表单添加单条 `mysql_query_rules` 规则
- **何时使用**：需要添加自定义路由规则
- **前置条件**：了解正则表达式匹配语法

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| rule_id | number | 是 | — | 规则 ID |
| active | toggle | 否 | 1 | 是否激活 |
| match_digest | text | 否 | — | 匹配摘要（正则） |
| match_pattern | text | 否 | — | 匹配模式（正则） |
| username | text | 否 | — | 限制用户名 |
| schemaname | text | 否 | — | 限制数据库名 |
| destination_hostgroup | number | 是 | — | 目标主机组 |
| apply | toggle | 否 | 1 | 命中后停止匹配 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_query_rules (rule_id, active, match_digest, destination_hostgroup, apply, comment)
VALUES (100, 1, '^SELECT.*FROM users', 1, 1, 'Route users table reads to reader hostgroup')
```

**相关向导**：W16（读写分离）、W18-W23（各类规则）

---

#### W18 — 查询缓存规则

- **类别**：查询路由规则
- **用途**：配置查询结果缓存（`cache_ttl`、`cache_empty_result`、`cache_timeout`）
- **何时使用**：需要对特定查询启用缓存
- **前置条件**：ProxySQL 查询缓存功能已启用（W31）

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| rule_id | number | 是 | — | 规则 ID |
| active | toggle | 否 | 1 | 是否激活 |
| match_digest | text | 否 | — | 匹配摘要 |
| match_pattern | text | 否 | — | 匹配模式 |
| username | text | 否 | — | 限制用户名 |
| schemaname | text | 否 | — | 限制数据库名 |
| cache_ttl | number | 否 | 5000 | 缓存 TTL（毫秒） |
| cache_empty_result | toggle | 否 | 0 | 缓存空结果 |
| cache_timeout | number | 否 | 1000 | 缓存超时（毫秒） |
| apply | toggle | 否 | 1 | 命中后停止 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_query_rules (rule_id, active, match_digest, cache_ttl, cache_empty_result, cache_timeout, apply, comment)
VALUES (200, 1, '^SELECT', 5000, 0, 1000, 1, 'Cache SELECT queries for 5s')
```

**相关向导**：W31（缓存全局变量）

---

#### W19 — 查询重写规则

- **类别**：查询路由规则
- **用途**：配置查询重写（`match_pattern` → `replace_pattern`）
- **何时使用**：需要修改客户端发送的 SQL 语句
- **前置条件**：熟悉正则表达式

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| rule_id | number | 是 | — | 规则 ID |
| active | toggle | 否 | 1 | 是否激活 |
| match_pattern | text | 是 | — | 匹配模式（正则） |
| replace_pattern | text | 是 | — | 替换模式 |
| username | text | 否 | — | 限制用户名 |
| schemaname | text | 否 | — | 限制数据库名 |
| destination_hostgroup | number | 否 | — | 目标主机组 |
| apply | toggle | 否 | 1 | 命中后停止 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_query_rules (rule_id, active, match_pattern, replace_pattern, apply, comment)
VALUES (300, 1, 'SELECT \* FROM old_table', 'SELECT * FROM new_table', 1, 'Rewrite old_table to new_table')
```

**相关向导**：W17（添加查询规则）

---

#### W20 — 查询超时/限流规则

- **类别**：查询路由规则
- **用途**：配置查询超时、延迟和重试次数
- **何时使用**：需要限制慢查询或保护后端资源
- **前置条件**：了解目标查询的特征

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| rule_id | number | 是 | — | 规则 ID |
| active | toggle | 否 | 1 | 是否激活 |
| match_digest | text | 否 | — | 匹配摘要 |
| match_pattern | text | 否 | — | 匹配模式 |
| timeout | number | 否 | 0 | 超时时间（毫秒，0=禁用） |
| delay | number | 否 | 0 | 延迟（毫秒，0=无） |
| retries | number | 否 | 0 | 重试次数（0=无） |
| destination_hostgroup | number | 否 | — | 目标主机组 |
| apply | toggle | 否 | 1 | 命中后停止 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_query_rules (rule_id, active, match_digest, timeout, retries, apply, comment)
VALUES (400, 1, '^SELECT.*FROM large_table', 10000, 2, 1, 'Timeout large table queries at 10s with 2 retries')
```

**相关向导**：W17（添加查询规则）

---

#### W21 — 查询镜像规则

- **类别**：查询路由规则
- **用途**：将查询流量镜像到测试主机组（`mirror_hostgroup`）
- **何时使用**：需要在测试环境重现生产流量
- **前置条件**：测试主机组已配置

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| rule_id | number | 是 | — | 规则 ID |
| active | toggle | 否 | 1 | 是否激活 |
| match_digest | text | 否 | — | 匹配摘要 |
| match_pattern | text | 否 | — | 匹配模式 |
| mirror_hostgroup | number | 是 | — | 镜像目标主机组 |
| mirror_flagOUT | number | 否 | — | 镜像标志 OUT |
| apply | toggle | 否 | 0 | 命中后停止（通常不停止） |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_query_rules (rule_id, active, match_digest, mirror_hostgroup, apply, comment)
VALUES (500, 1, '^SELECT', 99, 0, 'Mirror all SELECTs to test hostgroup')
```

**相关向导**：W17（添加查询规则）

---

#### W22 — 快速路由表

- **类别**：查询路由规则
- **用途**：配置 O(1) 快速路由（`mysql_query_rules_fast_routing` 表）
- **何时使用**：需要基于用户名/数据库名进行 O(1) 路由
- **前置条件**：了解快速路由的工作机制

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | add | Add / Delete / List |
| username | text | 是 | — | 用户名 |
| schemaname | text | 否 | — | 数据库名 |
| flagIN | number | 否 | 0 | 标志 IN |
| destination_hostgroup | number | 是 | — | 目标主机组 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_query_rules_fast_routing (username, schemaname, flagIN, destination_hostgroup, comment)
VALUES ('analytics_user', '', 0, 2, 'Route analytics user directly to hostgroup 2')
```

**相关向导**：W17（添加查询规则）

---

#### W23 — 查询日志规则

- **类别**：查询路由规则
- **用途**：为特定查询启用日志记录（`log=1`）
- **何时使用**：需要审计或调试特定查询
- **前置条件**：了解目标查询的摘要或模式

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| rule_id | number | 是 | — | 规则 ID |
| active | toggle | 否 | 1 | 是否激活 |
| match_digest | text | 否 | — | 匹配摘要 |
| match_pattern | text | 否 | — | 匹配模式 |
| username | text | 否 | — | 限制用户名 |
| schemaname | text | 否 | — | 限制数据库名 |
| destination_hostgroup | number | 否 | — | 目标主机组 |
| apply | toggle | 否 | 1 | 命中后停止 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_query_rules (rule_id, active, match_digest, log, apply, comment)
VALUES (600, 1, '^UPDATE', 1, 1, 'Log all UPDATE queries')
```

**相关向导**：W17（添加查询规则）、W33（日志事件变量）

---

#### W69 — 删除查询路由规则

- **类别**：查询路由规则
- **用途**：从 `mysql_query_rules` 表中按 rule_id 永久删除一条规则
- **何时使用**：不再需要的路由、缓存、重写或日志规则
- **前置条件**：先用 W55 确认规则未被使用

> ⚠ **危险操作**：删除关键规则（如读写分离中的 SELECT 路由）可能导致查询路由异常。

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| rule_id | number | 是 | — | 要删除的规则 ID |
| confirm_delete | checkbox | 是 | false | 确认删除 |

**生成 SQL 示例：**
```sql
DELETE FROM mysql_query_rules WHERE rule_id = 100
```

**相关向导**：W17（添加规则）、W55（规则命中统计）、W66（删除用户）

---

### 3.4 复制与集群拓扑 (W24-W28, W70)

#### W24 — 配置主从复制

- **类别**：复制与集群拓扑
- **用途**：注册传统异步复制的主从主机组（`mysql_replication_hostgroups`）
- **何时使用**：使用传统 MySQL 主从复制架构
- **前置条件**：主从复制已配置且运行正常

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| writer_hostgroup | number | 是 | — | 写主机组 |
| reader_hostgroup | number | 是 | — | 读主机组 |
| check_type | select | 否 | read_only | read_only / innodb_read_only / super_read_only / 组合 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_replication_hostgroups (writer_hostgroup, reader_hostgroup, check_type, comment)
VALUES (0, 1, 'read_only', 'primary-replica')
```

**相关向导**：W16（读写分离）、W25（Group Replication）

---

#### W25 — 配置 Group Replication

- **类别**：复制与集群拓扑
- **用途**：配置 MySQL Group Replication 主机组（`mysql_group_replication_hostgroups`）
- **何时使用**：使用 MySQL Group Replication（MGR）架构
- **前置条件**：MGR 集群已部署

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| writer_hostgroup | number | 是 | — | 写主机组 |
| backup_writer_hostgroup | number | 否 | — | 备用写主机组 |
| reader_hostgroup | number | 是 | — | 读主机组 |
| offline_hostgroup | number | 是 | — | 离线主机组 |
| active | toggle | 否 | 1 | 是否激活 |
| max_writers | number | 否 | 1 | 最大写入节点数 |
| writer_is_also_reader | select | 否 | 2 | 写入节点是否也作为读节点 |
| max_transactions_behind | number | 否 | 100 | 最大落后事务数 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_group_replication_hostgroups (writer_hostgroup, backup_writer_hostgroup, reader_hostgroup, offline_hostgroup, active, max_writers, writer_is_also_reader, max_transactions_behind, comment)
VALUES (0, 10, 1, 999, 1, 1, 2, 100, 'group-replication')
```

**相关向导**：W24（主从复制）、W26（Galera）

---

#### W26 — 配置 Galera 集群

- **类别**：复制与集群拓扑
- **用途**：配置 Galera 集群主机组（`mysql_galera_hostgroups`）
- **何时使用**：使用 Percona XtraDB Cluster 或 MariaDB Galera Cluster
- **前置条件**：Galera 集群已部署

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| writer_hostgroup | number | 是 | — | 写主机组 |
| backup_writer_hostgroup | number | 否 | — | 备用写主机组 |
| reader_hostgroup | number | 是 | — | 读主机组 |
| offline_hostgroup | number | 是 | — | 离线主机组 |
| active | toggle | 否 | 1 | 是否激活 |
| max_writers | number | 否 | 1 | 最大写入节点数 |
| writer_is_also_reader | select | 否 | 2 | 写入节点是否也作为读节点 |
| max_transactions_behind | number | 否 | 100 | 最大落后事务数 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_galera_hostgroups (writer_hostgroup, backup_writer_hostgroup, reader_hostgroup, offline_hostgroup, active, max_writers, writer_is_also_reader, max_transactions_behind, comment)
VALUES (0, 10, 1, 999, 1, 1, 2, 100, 'galera-cluster')
```

**相关向导**：W25（Group Replication）、W24（主从复制）

---

#### W27 — 配置 AWS Aurora 集群

- **类别**：复制与集群拓扑
- **用途**：配置 AWS Aurora 集群主机组（`mysql_aws_aurora_hostgroups`）
- **何时使用**：使用 Amazon Aurora MySQL
- **前置条件**：Aurora 集群已创建，域名解析正常

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| writer_hostgroup | number | 是 | — | 写主机组 |
| reader_hostgroup | number | 是 | — | 读主机组 |
| active | toggle | 否 | 1 | 是否激活 |
| domain_name | text | 是 | — | Aurora 集群域名 |
| aurora_port | number | 否 | 3306 | Aurora 端口 |
| max_lag_ms | number | 否 | 600000 | 最大延迟（毫秒） |
| check_interval_ms | number | 否 | 1000 | 检查间隔（毫秒） |
| check_timeout_ms | number | 否 | 800 | 检查超时（毫秒） |
| new_reader_weight | number | 否 | 1000 | 新读节点权重 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_aws_aurora_hostgroups (writer_hostgroup, reader_hostgroup, active, domain_name, aurora_port, max_lag_ms, check_interval_ms, check_timeout_ms, new_reader_weight, comment)
VALUES (0, 1, 1, 'my-cluster.cluster-xxx.region.rds.amazonaws.com', 3306, 600000, 1000, 800, 1000, 'aws-aurora')
```

**相关向导**：W24（主从复制）

---

#### W28 — 配置 PostgreSQL 复制

- **类别**：复制与集群拓扑
- **用途**：配置 PostgreSQL 主备复制主机组（`pgsql_replication_hostgroups`）
- **何时使用**：使用 PostgreSQL 流复制或逻辑复制
- **前置条件**：PostgreSQL 复制已配置

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| writer_hostgroup | number | 是 | — | 写主机组 |
| reader_hostgroup | number | 是 | — | 读主机组 |
| check_type | select | 否 | read_only | 检查类型 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO pgsql_replication_hostgroups (writer_hostgroup, reader_hostgroup, check_type, comment)
VALUES (0, 1, 'read_only', 'pgsql-replication')
```

**相关向导**：W02（添加 PgSQL 服务器）、W10（创建 PgSQL 用户）

---

#### W70 — 删除复制/集群配置

- **类别**：复制与集群拓扑
- **用途**：从 ProxySQL 永久删除复制/集群主机组配置
- **何时使用**：不再需要的集群架构
- **前置条件**：确认不再需要自动故障转移

> ⚠ **危险操作**：删除后自动 read_only 检测和故障转移将停止。服务器仍在主机组中但不会自动切换。

**支持的复制表：**

| 表名 | 说明 |
|------|------|
| mysql_replication_hostgroups | MySQL 传统主从复制 |
| mysql_group_replication_hostgroups | MySQL Group Replication |
| mysql_galera_hostgroups | Galera Cluster |
| mysql_aws_aurora_hostgroups | AWS Aurora |
| pgsql_replication_hostgroups | PostgreSQL 复制 |

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| target_table | select | 是 | — | 复制表类型 |
| writer_hostgroup | number | 是 | — | 写主机组 |
| reader_hostgroup | number（仅复制类） | 否 | — | 读主机组（主从/PgSQL 复制需要） |
| confirm_delete | checkbox | 是 | false | 确认删除 |

**生成 SQL 示例：**
```sql
DELETE FROM mysql_replication_hostgroups WHERE writer_hostgroup = 0 AND reader_hostgroup = 1
```

**相关向导**：W24-W28（各类复制配置）、W16（读写分离）、W69（删除查询规则）

---

### 3.5 系统配置 (W29-W42)

#### W29 — 连接池变量

- **类别**：系统配置
- **用途**：配置 MySQL 连接池相关全局变量（`max_connections`、`connect_timeout_*` 等）
- **何时使用**：需要调整连接池大小或超时参数
- **前置条件**：了解当前连接使用情况

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"mysql-max_connections": "2048"}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = '2048' WHERE variable_name = 'mysql-max_connections';
UPDATE global_variables SET variable_value = '10000' WHERE variable_name = 'mysql-connect_timeout_server';
```

**相关向导**：W07（主机组属性）、W32（多路复用变量）

---

#### W30 — 查询处理变量

- **类别**：系统配置
- **用途**：配置查询处理器变量（`query_digests`、`threshold_query_length` 等）
- **何时使用**：需要调整查询摘要或分析行为
- **前置条件**：了解查询处理参数含义

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"mysql-query_digests": "true"}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = 'true' WHERE variable_name = 'mysql-query_digests';
UPDATE global_variables SET variable_value = '2048' WHERE variable_name = 'mysql-threshold_query_length';
```

**相关向导**：W53（查询分析）

---

#### W31 — 查询缓存全局变量

- **类别**：系统配置
- **用途**：配置查询缓存全局参数（`query_cache_size_MB` 等）
- **何时使用**：需要启用或调整查询缓存
- **前置条件**：了解缓存对性能的影响

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"mysql-query_cache_size_MB": "256"}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = '256' WHERE variable_name = 'mysql-query_cache_size_MB';
```

**相关向导**：W18（查询缓存规则）

---

#### W32 — 多路复用变量

- **类别**：系统配置
- **用途**：配置多路复用相关变量（`multiplexing`、`max_transaction_time` 等）
- **何时使用**：需要启用或调整连接多路复用
- **前置条件**：理解多路复用的限制和适用场景

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"mysql-multiplexing": "true"}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = 'true' WHERE variable_name = 'mysql-multiplexing';
```

**相关向导**：W07（主机组属性）、W29（连接池变量）

---

#### W33 — 日志与事件变量

- **类别**：系统配置
- **用途**：配置事件日志和审计日志变量
- **何时使用**：需要调整日志行为
- **前置条件**：了解日志配置参数

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"mysql-eventslog_filename": "events.log"}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = 'events.log' WHERE variable_name = 'mysql-eventslog_filename';
```

**相关向导**：W23（查询日志规则）

---

#### W34 — 监控变量

- **类别**：系统配置
- **用途**：配置 MySQL 监控相关变量（`mysql-monitor_*`）
- **何时使用**：需要调整监控行为（检查间隔、监控用户等）
- **前置条件**：后端有监控用户

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"mysql-monitor_username": "monitor", "mysql-monitor_password": "monitor"}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = 'monitor' WHERE variable_name = 'mysql-monitor_username';
UPDATE global_variables SET variable_value = 'monitor' WHERE variable_name = 'mysql-monitor_password';
UPDATE global_variables SET variable_value = '1000' WHERE variable_name = 'mysql-monitor_ping_interval';
```

**相关向导**：W29（连接池变量）

---

#### W35 — ProxySQL Admin 用户管理

- **类别**：系统配置
- **用途**：管理 ProxySQL 管理接口的用户凭证（`admin-admin_credentials` / `admin-stats_credentials`）
- **何时使用**：需要添加或修改 ProxySQL 管理员用户
- **前置条件**：拥有修改全局变量的权限

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | list | List / Add / Remove / Set |
| target | select | 否 | admin_credentials | admin_credentials / stats_credentials |
| username | text | 否 | — | 用户名（add/remove 时使用） |
| password | password | 否 | — | 密码（add 时使用） |
| credentials | text | 否 | — | 完整凭证字符串（set 时使用） |

**生成 SQL 示例：**
```sql
-- List
SELECT variable_value FROM global_variables WHERE variable_name = 'admin-admin_credentials';

-- Add
UPDATE global_variables SET variable_value = variable_value || ',newuser:newpass'
WHERE variable_name = 'admin-admin_credentials';

-- Set
UPDATE global_variables SET variable_value = 'admin:admin,newuser:newpass'
WHERE variable_name = 'admin-admin_credentials';
```

**相关向导**：W36（网络接口变量）

---

#### W36 — 网络接口变量

- **类别**：系统配置
- **用途**：配置管理接口变量（`admin-mysql_ifaces`、`admin-web_enabled`、`admin-restapi_enabled` 等）
- **何时使用**：需要修改管理接口绑定地址或启用 Web/REST API
- **前置条件**：了解修改的影响（可能断开当前连接）

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"admin-mysql_ifaces": "0.0.0.0:6032"}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = '0.0.0.0:6032' WHERE variable_name = 'admin-mysql_ifaces';
```

**相关向导**：W35（Admin 用户管理）

---

#### W37 — 集群节点管理

- **类别**：系统配置
- **用途**：添加/删除 ProxySQL 集群节点（`proxysql_servers` 表）
- **何时使用**：需要配置 ProxySQL 原生集群
- **前置条件**：目标节点网络可达

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | add | Add / Remove / List |
| hostname | text | 否 | — | 主机名 |
| port | number | 否 | 6032 | 端口 |
| weight | number | 否 | 1 | 权重 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
-- Add
INSERT INTO proxysql_servers (hostname, port, weight, comment)
VALUES ('proxysql-2.example.com', 6032, 1, 'Cluster node 2');

-- Remove
DELETE FROM proxysql_servers WHERE hostname = 'proxysql-2.example.com' AND port = 6032;
```

**相关向导**：W38（集群同步变量）

---

#### W38 — 集群同步变量

- **类别**：系统配置
- **用途**：配置 ProxySQL 集群同步参数（`admin-cluster_*` 变量）
- **何时使用**：需要调整集群同步行为
- **前置条件**：集群节点已配置（W37）

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"admin-cluster_username": "admin", "admin-cluster_password": "admin"}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = 'admin' WHERE variable_name = 'admin-cluster_username';
UPDATE global_variables SET variable_value = 'admin' WHERE variable_name = 'admin-cluster_password';
UPDATE global_variables SET variable_value = '1000' WHERE variable_name = 'admin-cluster_check_interval_ms';
```

**相关向导**：W37（集群节点管理）

---

#### W39 — 调度任务管理

- **类别**：系统配置
- **用途**：管理 ProxySQL 调度器任务（`scheduler` 表）
- **何时使用**：需要定期执行脚本任务
- **前置条件**：脚本文件存在且可执行

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | add | Add / Update / Delete / List |
| id | number | 否 | — | 任务 ID（update/delete 时使用） |
| active | toggle | 否 | 1 | 是否激活 |
| interval_ms | number | 否 | 1000 | 间隔（毫秒，100-100000000） |
| filename | text | 否 | — | 脚本路径 |
| arg1-arg5 | text | 否 | — | 参数 1-5 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO scheduler (active, interval_ms, filename, arg1, comment)
VALUES (1, 60000, '/usr/local/bin/health_check.sh', '--timeout=30', 'Health check every minute')
```

**相关向导**：W40（REST API 路由）

---

#### W40 — REST API 路由管理

- **类别**：系统配置
- **用途**：管理 ProxySQL 自定义 REST API 端点（`restapi_routes` 表）
- **何时使用**：需要通过 ProxySQL REST API 暴露自定义端点
- **前置条件**：`admin-restapi_enabled` 已启用

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | add | Add / Update / Delete / List |
| id | number | 否 | — | 路由 ID（update/delete 时使用） |
| active | toggle | 否 | 1 | 是否激活 |
| timeout_ms | number | 否 | 1000 | 超时（毫秒） |
| method | select | 否 | GET | GET / POST |
| uri | text | 否 | — | URI 路径 |
| script | text | 否 | — | 脚本路径 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO restapi_routes (active, timeout_ms, method, uri, script, comment)
VALUES (1, 1000, 'GET', '/custom/status', '/usr/local/bin/status.sh', 'Custom status endpoint')
```

**相关向导**：W39（调度任务管理）

---

#### W41 — SSL/TLS 后端连接变量

- **类别**：系统配置
- **用途**：配置后端 SSL 连接的全局变量（`mysql-ssl_p2s_*`）
- **何时使用**：需要全局启用 ProxySQL 到后端的 SSL 连接
- **前置条件**：SSL 证书已准备

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"mysql-ssl_p2s_ca": "", "mysql-ssl_p2s_cert": ""}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = '/etc/ssl/ca.pem' WHERE variable_name = 'mysql-ssl_p2s_ca';
UPDATE global_variables SET variable_value = '/etc/ssl/cert.pem' WHERE variable_name = 'mysql-ssl_p2s_cert';
```

**相关向导**：W06（单服务器 SSL 参数）

---

#### W42 — 字符集与版本变量

- **类别**：系统配置
- **用途**：配置默认字符集和服务器版本伪装变量
- **何时使用**：需要设置默认字符集或伪装 MySQL 版本
- **前置条件**：了解字符集兼容性

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| variables | textarea (JSON) | 是 | `{"mysql-default_charset": "utf8mb4", "mysql-server_version": "8.0.30"}` | 变量名→值的 JSON 映射 |

**生成 SQL 示例：**
```sql
UPDATE global_variables SET variable_value = 'utf8mb4' WHERE variable_name = 'mysql-default_charset';
UPDATE global_variables SET variable_value = '8.0.30' WHERE variable_name = 'mysql-server_version';
```

**相关向导**：W30（查询处理变量）

---

### 3.6 防火墙与安全 (W43-W45)

#### W43 — 防火墙用户白名单

- **类别**：防火墙与安全
- **用途**：管理防火墙用户白名单（`mysql_firewall_whitelist_users` 表）
- **何时使用**：需要启用 ProxySQL 防火墙并配置受信任用户
- **前置条件**：防火墙功能已启用（W45）

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | add | Add / Update / Delete / List |
| id | number | 否 | — | ID（update/delete 时使用） |
| active | toggle | 否 | 1 | 是否激活 |
| username | text | 否 | — | 用户名 |
| client_address | text | 否 | — | 客户端地址（如 10.0.0.%） |
| mode | select | 否 | OFF | OFF / DETECTING / PROTECTING |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_firewall_whitelist_users (active, username, client_address, mode, comment)
VALUES (1, 'app_user', '10.0.0.%', 'PROTECTING', 'Allow app_user from 10.0.0.x')
```

**三种模式说明：**
- **OFF**：禁用防火墙
- **DETECTING**：检测模式（记录但不阻止）
- **PROTECTING**：保护模式（阻止未白名单的查询）

**相关向导**：W44（规则白名单）、W45（SQL 注入防护）

---

#### W44 — 防火墙规则白名单

- **类别**：防火墙与安全
- **用途**：管理防火墙规则白名单（`mysql_firewall_whitelist_rules` 表）
- **何时使用**：需要精细控制允许的 SQL 模式
- **前置条件**：防火墙已启用，用户白名单已配置

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | add | Add / Update / Delete / List |
| id | number | 否 | — | ID（update/delete 时使用） |
| active | toggle | 否 | 1 | 是否激活 |
| username | text | 否 | — | 用户名 |
| client_address | text | 否 | — | 客户端地址 |
| schemaname | text | 否 | — | 数据库名 |
| flagIN | number | 否 | 0 | 标志 IN |
| digest | text | 否 | — | 查询摘要 |
| comment | text | 否 | — | 备注 |

**生成 SQL 示例：**
```sql
INSERT INTO mysql_firewall_whitelist_rules (active, username, client_address, schemaname, flagIN, digest, comment)
VALUES (1, 'app_user', '10.0.0.%', 'app_db', 0, '0x1234ABCD', 'Allow specific query for app_user')
```

**相关向导**：W43（用户白名单）

---

#### W45 — SQL 注入防护

- **类别**：防火墙与安全
- **用途**：启用/禁用自动 SQL 注入检测和防火墙
- **何时使用**：需要保护后端数据库免受 SQL 注入攻击
- **前置条件**：理解防火墙功能

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | enable | Enable / Disable / Status |

**生成 SQL 示例：**
```sql
-- Enable
UPDATE global_variables SET variable_value = 'true' WHERE variable_name = 'mysql-automatic_detect_sqli';
UPDATE global_variables SET variable_value = 'true' WHERE variable_name = 'mysql-firewall_whitelist_enabled';

-- Status check
SELECT variable_name, variable_value FROM global_variables
WHERE variable_name IN ('mysql-automatic_detect_sqli', 'mysql-firewall_whitelist_enabled', 'mysql-firewall_whitelist_errormsg');
```

**相关向导**：W43（用户白名单）、W44（规则白名单）

---

### 3.7 运维与配置同步 (W46-W52)

#### W46 — Apply All 配置变更

- **类别**：运维与配置同步
- **用途**：一键将所有模块的配置从 MEMORY 加载到 RUNTIME
- **何时使用**：完成批量配置修改后需要一次性生效
- **前置条件**：MEMORY 层有未应用的变更

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | apply | Apply to Runtime / Save to Disk |

**生成 SQL 示例：**
```sql
LOAD MYSQL SERVERS TO RUNTIME;
LOAD MYSQL USERS TO RUNTIME;
LOAD MYSQL QUERY RULES TO RUNTIME;
LOAD MYSQL VARIABLES TO RUNTIME;
LOAD ADMIN VARIABLES TO RUNTIME;
```

**相关向导**：W47（Save All）、W50（Load from Disk）

---

#### W47 — Save All 到磁盘

- **类别**：运维与配置同步
- **用途**：一键将所有模块的配置从 RUNTIME 持久化到 DISK
- **何时使用**：确认所有变更正确后持久化
- **前置条件**：RUNTIME 层配置正确

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| action | select | 是 | save | Save to Disk / Apply to Runtime |

**生成 SQL 示例：**
```sql
SAVE MYSQL SERVERS TO DISK;
SAVE MYSQL USERS TO DISK;
SAVE MYSQL QUERY RULES TO DISK;
SAVE MYSQL VARIABLES TO DISK;
SAVE ADMIN VARIABLES TO DISK;
```

**相关向导**：W46（Apply All）、W48（配置备份）

---

#### W48 — 配置备份

- **类别**：运维与配置同步
- **用途**：导出当前 ProxySQL 配置（所有配置表数据）
- **何时使用**：变更前备份、定期备份、迁移配置
- **前置条件**：无

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| modules | textarea (JSON) | 否 | `""` (空=全部) | 要备份的模块列表，如 `["mysql_servers", "mysql_users"]` |

**生成 SQL 示例：**
```sql
SELECT * FROM mysql_servers;
SELECT * FROM mysql_users;
SELECT * FROM mysql_query_rules;
-- ... 所有白名单中的配置表
```

**允许备份的表：** `mysql_servers`、`mysql_users`、`mysql_query_rules`、`mysql_replication_hostgroups`、`mysql_group_replication_hostgroups`、`mysql_galera_hostgroups`、`mysql_aws_aurora_hostgroups`、`global_variables`、`scheduler`、`proxysql_servers`、`restapi_routes`、`pgsql_servers`、`pgsql_users`、`pgsql_query_rules`、`pgsql_replication_hostgroups`、`mysql_query_rules_fast_routing`、`mysql_hostgroup_attributes`、`mysql_servers_ssl_params`、`mysql_ldap_mapping`、`mysql_firewall_whitelist_users`、`mysql_firewall_whitelist_rules`、`mysql_collations`

**相关向导**：W49（配置恢复）

---

#### W49 — 配置恢复

- **类别**：运维与配置同步
- **用途**：从 JSON 备份恢复 ProxySQL 配置
- **何时使用**：回滚错误配置、从备份恢复
- **前置条件**：有 W48 导出的备份数据

> **警告**：此操作是破坏性的，将清空目标表并重新插入备份数据。

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| backup_data | textarea (JSON) | 是 | — | 备份数据（`{table: [rows]}` 格式） |
| confirm_restore | checkbox | 是 | false | 确认恢复（破坏性操作） |

**生成 SQL 示例：**
```sql
DELETE FROM mysql_servers;
INSERT INTO mysql_servers (hostgroup_id, hostname, port, status, weight, max_connections, ...) VALUES (0, '10.0.0.1', 3306, 'ONLINE', 1, 1000, ...);
```

**相关向导**：W48（配置备份）

---

#### W50 — 从磁盘加载所有配置

- **类别**：运维与配置同步
- **用途**：将所有配置模块从 DISK 加载到 MEMORY
- **何时使用**：ProxySQL 重启后或需要从磁盘恢复配置
- **前置条件**：磁盘上有保存的配置

**输入字段：** 无

**生成 SQL 示例：**
```sql
LOAD MYSQL SERVERS FROM DISK;
LOAD MYSQL USERS FROM DISK;
LOAD MYSQL QUERY RULES FROM DISK;
LOAD MYSQL VARIABLES FROM DISK;
LOAD ADMIN VARIABLES FROM DISK;
```

**相关向导**：W46（Apply All）、W47（Save All）

---

#### W51 — 重置统计信息

- **类别**：运维与配置同步
- **用途**：重置 ProxySQL 统计计数器
- **何时使用**：性能测试前后、清理历史统计数据
- **前置条件**：无

**输入字段：** 无

**生成 SQL 示例：**
```sql
SELECT STATS_RESET()
```

**相关向导**：W53-W63（各类监控向导）

---

#### W52 — 刷新查询缓存

- **类别**：运维与配置同步
- **用途**：清空 ProxySQL 查询缓存
- **何时使用**：后端数据变更后需要刷新缓存
- **前置条件**：查询缓存已启用

**输入字段：** 无

**生成 SQL 示例：**
```sql
SELECT FLUSH_QUERY_CACHE()
```

**相关向导**：W18（缓存规则）、W31（缓存全局变量）

---

### 3.8 监控与诊断 (W53-W63)

#### W53 — 慢查询/高频查询分析

- **类别**：监控与诊断
- **用途**：从 `stats_mysql_query_digest` 分析和排名查询（只读）
- **何时使用**：需要找出慢查询或高频查询进行优化
- **前置条件**：`query_digests` 已启用

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| sort_by | select | 否 | sum_time | sum_time / count_star / avg_time / sum_rows_affected |
| limit | number | 否 | 20 | Top N（1-500） |
| hostgroup | number | 否 | — | 主机组（可选） |
| schemaname | text | 否 | — | 数据库名（可选） |
| username | text | 否 | — | 用户名（可选） |

**生成 SQL 示例：**
```sql
SELECT hostgroup, schemaname, username, digest, digest_text, count_star, sum_time, min_time, max_time, avg_time, sum_rows_affected, sum_rows_sent, first_seen, last_seen
FROM stats_mysql_query_digest
ORDER BY sum_time DESC LIMIT 20
```

**返回数据：** top_queries、by_schema、by_command 三个维度

**相关向导**：W54（命令统计）、W55（规则命中统计）

---

#### W54 — 查询命令统计

- **类别**：监控与诊断
- **用途**：查看每种 SQL 命令的执行统计（`stats_mysql_commands_counters`）（只读）
- **何时使用**：分析查询负载分布
- **前置条件**：无

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| sort_by | select | 否 | Total_Time_us | Total_Time_us / Total_cnt |

**生成 SQL 示例：**
```sql
SELECT Command, Total_Time_us, Total_cnt, cnt_100us, cnt_500us, cnt_1ms, cnt_5ms, cnt_10ms, cnt_50ms, cnt_100ms, cnt_500ms, cnt_1s, cnt_5s, cnt_10s
FROM stats_mysql_commands_counters ORDER BY Total_Time_us DESC
```

**相关向导**：W53（慢查询分析）

---

#### W55 — 查询规则命中统计

- **类别**：监控与诊断
- **用途**：显示每条查询规则的命中次数（`stats_mysql_query_rules`）（只读）
- **何时使用**：验证路由规则是否按预期工作
- **前置条件**：查询规则已配置

**输入字段：** 无

**生成 SQL 示例：**
```sql
SELECT r.rule_id, r.active, r.match_digest, r.destination_hostgroup, r.apply, r.comment, s.hits
FROM mysql_query_rules r
LEFT JOIN stats_mysql_query_rules s ON r.rule_id = s.rule_id
ORDER BY s.hits DESC
```

**相关向导**：W17-W23（各类查询规则）

---

#### W56 — 查询错误分析

- **类别**：监控与诊断
- **用途**：分析后端错误统计（`stats_mysql_errors`）（只读）
- **何时使用**：排查后端连接或查询错误
- **前置条件**：无

**输入字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | number | 否 | 50 | 返回行数限制（1-500） |

**生成 SQL 示例：**
```sql
SELECT hostgroup, hostname, port, username, schemaname, errno, count_star, first_seen, last_seen, last_error
FROM stats_mysql_errors ORDER BY count_star DESC LIMIT 50
```

**返回数据：** errors、by_hostgroup 两个维度

**相关向导**：W57（连接池监控）

---

#### W57 — 连接池监控

- **类别**：监控与诊断
- **用途**：可视化连接池使用情况（`stats_mysql_connection_pool`）（只读）
- **何时使用**：监控连接池健康状态
- **前置条件**：无

**输入字段：** 无

**生成 SQL 示例：**
```sql
SELECT hostgroup, srv_host, srv_port, status, ConnUsed, ConnFree, ConnOK, ConnERR, MaxConnUsed, Queries, Queries_GTID_sync, Bytes_data_sent, Bytes_data_recv, Latency_us
FROM stats_mysql_connection_pool ORDER BY hostgroup, srv_host
```

**返回数据：** connection_pool、summary 两个维度

**相关向导**：W08（连接测试）、W58（进程列表）

---

#### W58 — 实时进程列表

- **类别**：监控与诊断
- **用途**：显示当前活跃会话（`stats_mysql_processlist`）（只读）
- **何时使用**：排查锁等待、长时间运行查询
- **前置条件**：无

**输入字段：** 无

**生成 SQL 示例：**
```sql
SELECT ThreadID, SessionID, user, db, cli_host, cli_port, hostgroup, srv_host, srv_port, command, time_ms, info
FROM stats_mysql_processlist ORDER BY time_ms DESC
```

**相关向导**：W57（连接池监控）、W59（用户连接统计）

---

#### W59 — 用户连接统计

- **类别**：监控与诊断
- **用途**：显示每个用户的连接统计（`stats_mysql_users`）（只读）
- **何时使用**：分析用户级别的连接分布
- **前置条件**：无

**输入字段：** 无

**生成 SQL 示例：**
```sql
SELECT username, frontend_connections, frontend_max_connections
FROM stats_mysql_users ORDER BY frontend_connections DESC
```

**相关向导**：W58（进程列表）

---

#### W60 — 后端拓扑可视化

- **类别**：监控与诊断
- **用途**：可视化主机组拓扑和读写分离流程（只读）
- **何时使用**：查看整体架构拓扑
- **前置条件**：后端服务器已配置

**输入字段：** 无

**生成 SQL 示例：**
```sql
-- 服务器列表
SELECT hostgroup_id, hostname, port, status, weight, max_connections, max_replication_lag, use_ssl, comment
FROM mysql_servers ORDER BY hostgroup_id, hostname;

-- 复制主机组
SELECT writer_hostgroup, reader_hostgroup, check_type, comment FROM mysql_replication_hostgroups;

-- 连接池状态
SELECT hostgroup, srv_host, srv_port, status, ConnUsed, ConnFree, Latency_us FROM stats_mysql_connection_pool;
```

**返回数据：** servers、replication_hostgroups、pool_status 三个维度

**相关向导**：W16（读写分离）、W24（主从复制）

---

#### W61 — 全局状态面板

- **类别**：监控与诊断
- **用途**：显示全局状态和内存指标（只读）
- **何时使用**：查看 ProxySQL 整体运行状态
- **前置条件**：无

**输入字段：** 无

**生成 SQL 示例：**
```sql
SELECT Variable_Name, Variable_Value FROM stats_mysql_global ORDER BY Variable_Name;
SELECT Variable_Name, Variable_Value FROM stats_memory_metrics ORDER BY Variable_Name;
SELECT SUM(ConnUsed) as used, SUM(ConnFree) as free, SUM(ConnOK) as ok, SUM(ConnERR) as error FROM stats_mysql_connection_pool;
```

**返回数据：** global_status、memory_metrics、connections 三个维度

**相关向导**：W57（连接池监控）

---

#### W62 — GTID 同步状态

- **类别**：监控与诊断
- **用途**：查看每个后端的 GTID 执行状态（`stats_mysql_gtid_executed`）（只读）
- **何时使用**：验证复制一致性（MySQL GTID 模式）
- **前置条件**：后端使用 GTID 复制

**输入字段：** 无

**生成 SQL 示例：**
```sql
SELECT hostname, port, gtid_executed FROM stats_mysql_gtid_executed
```

**相关向导**：W24（主从复制）、W25（Group Replication）

---

#### W63 — ProxySQL 集群状态

- **类别**：监控与诊断
- **用途**：查看 ProxySQL 集群节点状态和配置一致性（只读）
- **何时使用**：监控集群健康状态
- **前置条件**：集群已配置

**输入字段：** 无

**生成 SQL 示例：**
```sql
SELECT hostname, port, weight, comment, response_time_ms, last_check_ms, check_type FROM stats_proxysql_servers_metrics;
SELECT hostname, port, name, version, epoch, checksum FROM stats_proxysql_servers_checksums;
SELECT hostname, port, weight, comment, status FROM stats_proxysql_servers_status;
```

**返回数据：** cluster_metrics、cluster_checksums、cluster_status 三个维度

**相关向导**：W37（集群节点管理）、W38（集群同步变量）

---

## 4. 快速部署模板（T01）

除了 70 个独立向导外，系统还提供了一个**快速部署模板**，将多个向导串联为一个完整的工作流。

### 4.1 模板概述

**T01 — MySQL 快速部署模板** 一键配置完整的 ProxySQL + MySQL 代理架构。选择架构模式后，模板自动引导完成以下步骤：

| 步骤 | 对应向导 | 说明 |
|------|---------|------|
| 1 | W01 | 添加 MySQL 后端服务器 |
| 2 | W09 | 创建 ProxySQL 用户 |
| 3 | W16 | 配置读写分离规则 |
| 4 | W34 | 配置监控用户和参数 |
| 5 | W29 | 配置连接池参数 |
| 6 | W24/W25/W26 | 配置拓扑结构（根据架构模式） |

### 4.2 支持的架构模式

| 模式 | 对应拓扑步骤 | 说明 |
|------|------------|------|
| 单主从复制 | W24_sp | 传统一主一从/多从异步复制 |
| 多主多从复制 | W24_mp | 多写入节点+读取副本 |
| MGR 单主模式 | W25_sp | MySQL Group Replication 单主 |
| MGR 多主模式 | W25_mp | MySQL Group Replication 多主 |
| Galera 集群 | W26_gc | Galera/PXC 同步复制集群 |

### 4.3 全局配置继承

模板支持**共享配置**机制：监控用户名/密码、连接池参数等只需在全局配置区填写一次，会自动继承到所有相关步骤。继承的字段会标记并允许修改。

### 4.4 模板使用流程

```
选择架构模式 → 填写全局配置 → 逐步填写各组件 → 跳过不需要的步骤 → 一键提交全部
```

---

## 5. 向导使用最佳实践

### 4.1 生产环境操作建议

1. **先预览再执行**：始终在预览 SQL 确认无误后再执行
2. **逐步执行**：对于影响面大的操作，关闭自动 Apply，手动确认后逐步生效
3. **变更前备份**：使用 W48 备份当前配置，以便出问题时回滚
4. **测试环境验证**：先在测试环境执行，确认效果后再到生产环境

### 4.2 安全建议

1. **密码字段**：向导中的密码字段在后端传输时加密，但建议不要在公共网络中使用
2. **防火墙模式**：先使用 DETECTING 模式观察，确认无误后再切换到 PROTECTING
3. **审计日志**：所有向导执行都会被记录，定期检查审计日志

### 4.3 性能建议

1. **批量操作**：使用 W03（批量导入）代替逐个执行 W01
2. **一键操作**：使用 W46/W47 进行批量同步，而非逐个模块操作
3. **监控优先**：配置变更后使用 W53-W63 监控效果

### 4.4 常见错误处理

| 错误 | 可能原因 | 解决方案 |
|------|---------|---------|
| 向导执行失败 | SQL 语法或约束冲突 | 检查预览的 SQL，确认数据格式 |
| 配置未生效 | 未执行 Apply | 使用 W46 或配置同步页面 Apply |
| 重启后配置丢失 | 未执行 Save | 使用 W47 或配置同步页面 Save |

---

## 6. 常见向导组合（工作流）

### 工作流 1：新集群初始化

```
W01/W03 → 添加后端服务器
W09/W12 → 创建用户和设置密码
W24      → 配置主从复制
W16      → 配置读写分离
W46      → Apply All
W47      → Save All
W48      → 备份配置
```

### 工作流 2：添加只读副本

```
W01      → 添加新的只读服务器到 reader_hostgroup
W04      → 调整权重
W46      → Apply
W47      → Save
```

### 工作流 3：启用安全防护

```
W45      → 启用 SQL 注入检测
W43      → 添加受信任用户
W44      → 添加允许的查询规则
W46      → Apply All
W47      → Save All
```

### 工作流 4：性能调优

```
W53      → 分析慢查询
W20      → 设置超时/限流规则
W18      → 配置查询缓存
W31      → 调整缓存大小
W29      → 调整连接池参数
W46      → Apply All
```

### 工作流 5：集群扩展

```
W37      → 添加新集群节点
W38      → 配置集群同步参数
W46      → Apply
W47      → Save
W63      → 验证集群状态
```

### 工作流 6：灾难恢复

```
W49      → 从备份恢复配置
W50      → 从磁盘加载
W46      → Apply All
W08      → 测试后端连接
W57      → 验证连接池状态
```

### 工作流 7：使用模板快速部署

```
T01      → 选择架构模式 → 填写全局配置 → 逐步配置 → 一键提交全部
W46      → Apply All（模板已自动执行，可选手动确认）
W47      → Save to Disk
W08      → 测试后端连接
W57      → 验证连接池状态
```
