# ProxySQL Admin WebUI — 贡献指南

> **语言**: 简体中文

感谢您对 ProxySQL Admin WebUI 的关注！本指南将帮助您设置开发环境、了解项目结构，并贡献代码。

---

## 目录

- [开发环境设置](#开发环境设置)
- [项目结构概览](#项目结构概览)
- [编码规范](#编码规范)
- [如何添加新向导](#如何添加新向导)
- [如何添加新 API 端点](#如何添加新-api-端点)
- [如何添加新前端页面](#如何添加新前端页面)
- [测试指南](#测试指南)
- [Pull Request 流程](#pull-request-流程)
- [Commit 消息规范](#commit-消息规范)

---

## 开发环境设置

### 前置条件

- **Python 3.10+**（推荐 3.12+）
- **Node.js 24+**
- **Git**
- **make**

### 初始化开发环境

```bash
# 1. 克隆仓库
git clone https://cnb.cool/xzydm/proxysql-admin-webui.git
cd proxysql-admin-webui

# 2. 安装后端依赖
make install

# 3. 安装前端依赖
cd frontend && npm install && cd ..

# 4. 构建前端（首次需要）
make build-frontend

# 5. 启动开发模式（热重载）
# 终端 1：后端 (http://localhost:8080)
make dev-backend

# 终端 2：前端 (http://localhost:5173，API 代理到 :8080)
make dev-frontend
```

### 代码生成

当 ProxySQL 的 `ProxySQL_Admin_Tables_Definitions.h` 更新后，需要重新生成模型和路由：

```bash
make codegen
```

这会更新：
- `backend/app/generated/models.py` — Pydantic 数据模型
- `backend/app/generated/routes.py` — FastAPI CRUD 路由
- `backend/app/generated/metadata.py` — 表元数据

---

## 项目结构概览

```
proxysql-admin-webui/
├── backend/                       # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py                # FastAPI 入口（同时托管前端静态文件）
│   │   ├── config.py              # 应用配置管理
│   │   ├── database.py            # SQLite 持久化
│   │   ├── api/v1/                # REST API 端点（16 个路由模块）
│   │   │   ├── auth.py            # 认证（登录/刷新/登出/修改密码）
│   │   │   ├── tables.py          # 表管理（CRUD + 分页 + 搜索）
│   │   │   ├── sync.py            # 配置同步（Apply/Save/Discard/Load）
│   │   │   ├── query.py           # SQL 查询执行 + 历史记录
│   │   │   ├── dashboard.py       # 监控数据 + WebSocket 推送
│   │   │   ├── users.py           # 用户管理
│   │   │   ├── servers.py         # 多实例管理 + 连接测试
│   │   │   ├── settings.py        # 系统设置 + 审计日志
│   │   │   ├── wizards.py         # 向导模式（预览/执行/历史/lookup）
│   │   │   ├── templates.py       # 快速部署模板
│   │   │   ├── config_diff.py     # 配置差异对比
│   │   │   ├── clusters.py        # 集群管理
│   │   │   ├── backup.py          # 配置备份/恢复
│   │   │   ├── export.py          # 数据导出（CSV/JSON）
│   │   │   ├── scheduler.py       # 定时任务调度
│   │   │   └── db_manager.py      # 数据库管理（后端 MySQL 直连）
│   │   ├── services/              # 业务逻辑层
│   │   │   ├── proxysql.py        # ProxySQL 连接池与查询
│   │   │   ├── mysql_client.py    # MySQL 后端直连客户端
│   │   │   ├── wizard_engine.py   # 向导引擎核心 + 63 向导注册
│   │   │   ├── wizards/           # 向导具体实现（10 个模块）
│   │   │   ├── sync_service.py    # 配置同步服务
│   │   │   ├── cluster_service.py # 集群管理服务
│   │   │   ├── query_engine.py    # SQL 查询引擎
│   │   │   ├── dashboard_service.py # 监控数据服务
│   │   │   ├── schema_service.py  # Schema 内省服务
│   │   │   ├── cache_service.py   # 缓存服务
│   │   │   └── scheduler_service.py # 定时任务调度服务
│   │   ├── models/                # Pydantic 数据模型
│   │   ├── middleware/            # JWT 认证中间件
│   │   ├── generated/             # 代码生成器输出
│   │   └── utils/                 # 工具函数
│   ├── codegen/                   # 代码生成器源码
│   ├── tests/                     # 测试套件
│   └── requirements.txt
├── frontend/                      # React + Vite 前端
│   ├── src/
│   │   ├── api/                   # API 客户端（11 个命名空间）
│   │   │   └── client.ts          # 所有 API 函数定义
│   │   ├── components/            # 共享组件
│   │   │   ├── layout/            # 布局组件（MainLayout）
│   │   │   ├── ErrorBoundary.tsx  # 错误边界
│   │   │   ├── GlobalSearch.tsx   # 全局搜索（Ctrl+K）
│   │   │   ├── LoadingFallback.tsx # 加载等待组件
│   │   │   ├── PageSkeleton.tsx   # 页面骨架屏
│   │   │   ├── ServerSelector.tsx # 服务器选择器
│   │   │   ├── ThemeToggle.tsx    # 主题切换
│   │   │   └── LanguageSwitcher.tsx # 语言切换
│   │   ├── pages/                 # 页面组件（15 个页面）
│   │   │   ├── LoginPage.tsx      # 登录页
│   │   │   ├── DashboardPage.tsx  # 仪表盘
│   │   │   ├── WizardsPage.tsx    # 配置向导
│   │   │   ├── TemplateWizardPage.tsx # 快速部署模板
│   │   │   ├── TableBrowserPage.tsx # 表浏览器
│   │   │   ├── QueryConsolePage.tsx # SQL 控制台
│   │   │   ├── ConfigSyncPage.tsx # 配置同步
│   │   │   ├── ConfigDiffPage.tsx # 配置差异
│   │   │   ├── ServersPage.tsx    # 服务器管理
│   │   │   ├── UsersPage.tsx      # 用户管理
│   │   │   ├── SettingsPage.tsx   # 系统设置
│   │   │   ├── ClustersPage.tsx   # 集群列表
│   │   │   ├── ClusterDetailPage.tsx # 集群详情
│   │   │   ├── BackupPage.tsx     # 配置备份
│   │   │   └── DatabaseManagerPage.tsx # 数据库管理
│   │   ├── stores/                # Zustand 状态管理
│   │   │   └── authStore.ts       # 认证状态
│   │   ├── hooks/                 # 自定义 React Hooks
│   │   ├── i18n/                  # 国际化资源
│   │   │   └── locales/           # 语言文件（zh-CN, en-US）
│   │   └── main.tsx               # 应用入口
│   ├── package.json
│   └── vite.config.ts
├── docker/                        # Docker 部署配置
├── docs/                          # 文档
│   ├── index.md                   # 用户手册首页
│   ├── getting-started.md         # 快速入门
│   ├── USER_MANUAL.md             # 用户手册
│   ├── WIZARD_GUIDE.md            # 配置向导完整指南
│   ├── DEPLOYMENT.md              # 部署指南
│   ├── configuration.md           # 配置参考
│   └── troubleshooting.md         # 故障排除
├── scripts/                       # 工具脚本
├── Dockerfile                     # 多阶段构建
├── docker-compose.yml             # 生产环境 Docker Compose
├── docker-compose.test.yml        # 测试环境 Docker Compose
├── Makefile
├── README.md
├── CONTRIBUTING.md                # 本文件
├── CHANGELOG.md                   # 变更日志
├── SECURITY.md                    # 安全策略
├── plan.md                        # 测试环境搭建与任务追踪
└── mkdocs.yml                     # MkDocs 文档站点配置
```

---

## 编码规范

### Python 后端

- 遵循 [PEP 8](https://peps.python.org/pep-0008/) 风格指南
- 使用 **类型注解**（Type Hints）标注所有函数参数和返回值
- 使用 `async/await` 进行异步 I/O 操作
- 数据验证使用 Pydantic 模型
- 敏感数据（密码、密钥）使用 Fernet 加密存储

```python
# 好的示例
async def get_server_status(host: str, port: int) -> dict[str, Any]:
    """获取 ProxySQL 服务器状态。"""
    ...
```

### TypeScript 前端

- 使用函数式组件 + React Hooks
- 所有组件使用 TypeScript 严格模式
- 状态管理使用 Zustand
- 国际化使用自定义 `useI18n()` Hook
- API 调用统一通过 `api/client.ts` 中的客户端模块
- 页面级组件使用 `lazy()` + Suspense 代码分割

```tsx
// 好的示例
export default function MyPage() {
  const { t } = useI18n()
  const data = useMyStore((s) => s.data)

  return <div>{t('myPage.title')}</div>
}
```

---

## 如何添加新向导

### 步骤 1：选择分类

确定新向导属于哪个类别，在 `backend/app/services/wizards/` 下找到对应模块：

| 文件 | 类别 | 向导编号范围 |
|------|------|-------------|
| `server.py` | 后端服务器管理 | W03, W06-W08 |
| `user.py` | 后端用户管理 | W10, W14-W15 |
| `routing.py` | 查询路由规则 | W18-W23 |
| `topology.py` | 复制与集群拓扑 | W25-W28 |
| `system.py` | 系统配置 | W32-W42 |
| `firewall.py` | 防火墙与安全 | W43-W45 |
| `ops.py` | 运维与配置同步 | W48-W49, W52 |
| `monitor.py` | 监控与诊断 | W53-W63 |

### 步骤 2：创建向导类

在对应的模块文件中创建一个继承 `BaseWizard` 的类：

```python
from app.services.wizard_engine import BaseWizard, WizardDefinition, WizardField, _quote_val

class MyNewWizard(BaseWizard):
    """WXX: 简短描述。"""

    def validate(self, fields: dict) -> list[str]:
        """验证表单字段，返回错误消息列表。"""
        errors = []
        if not fields.get("required_field"):
            errors.append("required_field is required")
        return errors

    def generate_sql(self, fields: dict) -> list[str]:
        """从表单字段生成 SQL 语句列表。"""
        return [
            f"INSERT INTO some_table (col1, col2) "
            f"VALUES ({_quote_val(fields['col1'])}, {_quote_val(fields['col2'])})"
        ]
```

### 步骤 3：注册向导定义

在同一文件的 `DEFINITIONS` 字典中添加条目：

```python
DEFINITIONS = {
    # ... 已有定义 ...
    "WXX": (WizardDefinition(
        id="WXX",
        category="your_category",
        name="您的向导名称",
        description="向导的简短描述（1-2 句话）",
        icon="your-icon",
        target_table="target_table_name",
        auto_apply_module="MODULE NAME",
        fields=[
            WizardField("field_name", "Field Label", "text", required=True),
            # ... 更多字段 ...
        ],
        status="implemented",
    ), MyNewWizard),
}
```

### 步骤 4：添加前端翻译

在 `frontend/src/i18n/locales/zh-CN.ts` 和 `en-US.ts` 中添加向导名称、描述和字段标签的翻译。

### 字段类型参考

| type 值 | 前端渲染 | 说明 |
|---------|---------|------|
| `text` | `<input type="text">` | 单行文本 |
| `number` | `<input type="number">` | 数字 |
| `password` | `<input type="password">` | 密码（隐藏显示） |
| `textarea` | `<textarea>` | 多行文本 |
| `select` | `<select>` | 下拉选择（需要 options） |
| `radio` | `<input type="radio">` | 单选按钮 |
| `checkbox` | `<input type="checkbox">` | 复选框 |
| `toggle` | 开关组件 | 布尔值切换 |

---

## 如何添加新 API 端点

### 步骤 1：创建路由文件

在 `backend/app/api/v1/` 下创建新文件（如 `my_feature.py`）：

```python
from fastapi import APIRouter, Depends
from app.middleware import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/status")
async def get_status(current_user: User = Depends(get_current_user)):
    """获取功能状态。"""
    return {"status": "ok"}
```

### 步骤 2：注册路由

在 `backend/app/main.py` 中注册新路由：

```python
from app.api.v1 import my_feature

app.include_router(my_feature.router, prefix="/api/v1/my-feature", tags=["My Feature"])
```

### 步骤 3：添加前端 API 客户端

在 `frontend/src/api/client.ts` 中添加新的 API 命名空间：

```typescript
export const myFeatureApi = {
  getStatus: () => apiClient.get('/api/v1/my-feature/status'),
}
```

---

## 如何添加新前端页面

### 步骤 1：创建页面组件

在 `frontend/src/pages/` 下创建新文件（如 `MyNewPage.tsx`）：

```tsx
import { useI18n } from '../i18n'

export default function MyNewPage() {
  const { t } = useI18n()

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">
        {t('myNewPage.title')}
      </h2>
    </div>
  )
}
```

### 步骤 2：添加路由

在 `frontend/src/App.tsx` 中添加 lazy import 和路由：

```tsx
const MyNewPage = lazy(() => import('./pages/MyNewPage'))

// 在 Routes 中添加：
<Route path="my-new-page" element={
  <Suspense fallback={<PageSkeleton />}>
    <MyNewPage />
  </Suspense>
} />
```

### 步骤 3：添加侧边栏导航

在 `frontend/src/components/layout/MainLayout.tsx` 的 `navItems` 数组中添加条目。

### 步骤 4：添加国际化文本

在 `frontend/src/i18n/locales/zh-CN.ts` 和 `en-US.ts` 中添加对应的翻译键。

---

## 测试指南

### 运行测试

```bash
# 运行所有测试
make test

# 运行特定测试文件
cd backend && python -m pytest tests/test_wizards.py -v

# 运行特定测试
cd backend && python -m pytest tests/test_wizards.py::test_w01_add_mysql_server -v

# 生成覆盖率报告
cd backend && python -m pytest --cov=app --cov-report=html
```

### 测试文件组织

```
backend/tests/
├── test_auth.py           # 认证测试
├── test_api_integration.py # API 集成测试
├── test_codegen.py        # 代码生成器测试
├── test_helpers.py        # 工具函数测试
├── test_schema.py         # Schema 测试
├── test_security.py       # 安全测试
├── test_services.py       # 服务层测试
├── test_sync.py           # 配置同步测试
├── test_users.py          # 用户管理测试
├── test_wizards.py        # 向导测试
└── integration/           # Docker Compose 集成测试
```

### 编写测试

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_my_feature():
    """测试我的功能。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 登录获取 token
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        token = resp.json()["access_token"]

        # 测试功能
        resp = await client.get(
            "/api/v1/my-feature/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
```

---

## Pull Request 流程

1. **Fork 仓库** 并创建功能分支：
   ```bash
   git checkout -b feature/my-feature
   ```

2. **编写代码**，遵循编码规范。

3. **添加测试**，确保覆盖率不低于现有水平。

4. **更新文档**：
   - 如果是新功能，更新 `USER_MANUAL.md`
   - 如果是新向导，更新 `WIZARD_GUIDE.md`
   - 如果是 API 变更，更新相关 API 文档
   - 更新 `CHANGELOG.md` 记录变更

5. **运行测试** 确保全部通过：
   ```bash
   make test
   ```

6. **提交代码** 遵循 Commit 消息规范。

7. **创建 Pull Request**：
   - 标题简洁明了
   - 描述变更内容和原因
   - 关联相关 Issue
   - 标注是否需要文档更新

8. **Code Review**：至少需要一位维护者审核。

9. **合并**：使用 Squash Merge 保持主干整洁。

---

## Commit 消息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Type 类型

| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 代码重构 |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖更新 |
| `perf` | 性能优化 |
| `security` | 安全相关 |

### Scope 范围

| Scope | 说明 |
|-------|------|
| `backend` | 后端代码 |
| `frontend` | 前端代码 |
| `wizard` | 向导相关 |
| `api` | API 端点 |
| `sync` | 配置同步 |
| `auth` | 认证相关 |
| `dbm` | 数据库管理 |
| `template` | 快速部署模板 |
| `backup` | 配置备份 |
| `cluster` | 集群管理 |
| `docs` | 文档 |
| `docker` | Docker 部署 |
| `test` | 测试 |
| `i18n` | 国际化 |

### 示例

```
feat(wizard): 添加 W64 新向导 — 批量修改用户密码

新增 BatchChangePasswordWizard，支持一次修改多个后端用户的密码。
- 添加向导类到 user.py
- 注册到 wizard_engine.py
- 更新 WIZARD_GUIDE.md

Closes #123
```

```
fix(backend): 修复配置同步时 PostgreSQL 连接超时

将 aiomysql 连接池超时时间从 10s 增加到 30s。
```

```
docs: 更新用户手册，添加数据库管理章节
```

```
security(backend): 升级 cryptography 到 42.0.0

修复 CVE-2024-XXXX。
```
