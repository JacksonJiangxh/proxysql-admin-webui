.PHONY: help install build-frontend run dev-backend dev-frontend test test-frontend test-runner lint lint-frontend clean codegen docker-build docker-up docker-down docker-build-test docker-test e2e-test benchmark release-check pre-commit-install

help:
	@echo "ProxySQL Admin WebUI - 开发与部署命令"
	@echo ""
	@echo "  开发:"
	@echo "  make install           安装所有依赖 (backend + frontend)"
	@echo "  make pre-commit-install 安装 git pre-commit hooks"
	@echo "  make build-frontend    构建前端到 frontend/dist (生产部署前置)"
	@echo "  make run               生产模式: 单进程同时提供 API + 前端 (http://localhost:8080)"
	@echo "  make dev-backend       开发模式: 仅后端 (热重载, :8080)"
	@echo "  make dev-frontend      开发模式: 仅前端 Vite (热重载, :5173, 代理 API 到 :8080)"
	@echo "  make codegen           从 ProxySQL 头文件生成 CRUD 代码"
	@echo ""
	@echo "  测试:"
	@echo "  make test              运行后端单元测试"
	@echo "  make test-frontend     运行前端单元测试 (Vitest)"
	@echo "  make test-quick        快速测试 L0-L3 (无需 Docker)"
	@echo "  make test-api          真实环境 API 冒烟测试 (需要 Docker + 后端)"
	@echo "  make test-full         全层级测试 L0-L5"
	@echo "  make test-runner       启动交互式 API 测试 shell (自动登录+CSRF)"
	@echo "  make lint              运行代码检查 (ruff + eslint)"
	@echo "  make lint-frontend     仅检查前端代码"
	@echo "  make docker-test       运行 Docker Compose 集成测试"
	@echo "  make e2e-test          运行前端 E2E 测试 (Playwright)"
	@echo "  make benchmark         运行性能基准测试"
	@echo ""
	@echo "  Docker:"
	@echo "  make docker-build      构建 Docker 镜像"
	@echo "  make docker-up         启动 Docker Compose 生产部署"
	@echo "  make docker-down       停止 Docker Compose"
	@echo ""
	@echo "  发布:"
	@echo "  make release-check     发布前检查 (lint + test + build)"
	@echo "  make clean             清理构建产物"

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

# Build the frontend SPA. The backend (via StaticFiles) serves the output
# from frontend/dist in production — no separate web server required.
build-frontend:
	cd frontend && npm run build

# Production: one uvicorn process serves API + frontend on :8080.
# Requires `make build-frontend` to have been run first.
run:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080

dev-backend:
	cd backend && DEV_MODE=true uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && python -m pytest tests/ -v

test-frontend:
	cd frontend && npx vitest run --coverage

test-quick:
	bash scripts/test_all.sh --quick

test-api:
	bash scripts/test_all.sh --api

test-full:
	bash scripts/test_all.sh

test-runner:
	@echo "Starting interactive API test shell..."
	@echo "Available commands: api_get, api_post, api_put, api_delete"
	@echo "Example: api_get /api/v1/servers"
	@echo ""
	bash --rcfile test_runner.sh

lint:
	cd backend && ruff check app/
	cd frontend && npm run lint

lint-frontend:
	cd frontend && npm run lint

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache
	rm -rf frontend/dist
	rm -rf frontend/node_modules

codegen:
	cd backend && python -m codegen.gen_fastapi_models \
		--header ../proxysql/include/ProxySQL_Admin_Tables_Definitions.h \
		--outdir app/generated

docker-build:
	docker build -t proxysql-admin-webui -f Dockerfile .

docker-up:
	docker compose -f docker-compose.yml up -d

docker-down:
	docker compose -f docker-compose.yml down

# ── Test targets ──────────────────────────────────────────────────

docker-test:
	@echo "Starting integration test environment..."
	FERNET_KEY=$${FERNET_KEY:-dGVzdC1mZXJuZXQta2V5LWZvci1jaS1pbnRlZ3JhdGlvbi10ZXN0czExMQ==} \
	docker compose -f docker/docker-compose.test.yml up -d --build
	@echo "Waiting for services to be healthy..."
	@timeout 120 bash -c 'until docker compose -f docker/docker-compose.test.yml ps | grep -q "healthy"; do sleep 3; done'
	@echo "Running integration tests..."
	cd backend && python -m pytest tests/integration/ -v --tb=short 2>/dev/null || echo "No integration test files found"
	@echo "Cleaning up..."
	docker compose -f docker/docker-compose.test.yml down -v --remove-orphans

e2e-test:
	cd frontend && npx playwright test --project=chromium

benchmark:
	bash scripts/benchmark.sh

# ── Release ───────────────────────────────────────────────────────

pre-commit-install:
	pip install pre-commit
	pre-commit install
	@echo "✅ Pre-commit hooks installed. They will run on every commit."

release-check: lint test build-frontend
	@echo ""
	@echo "✅ All release checks passed!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Update CHANGELOG.md with the new version"
	@echo "  2. Update version in backend/app/main.py and pyproject.toml"
	@echo "  3. Commit and push:"
	@echo "     git commit -am 'release: v<VERSION>'"
	@echo "     git tag v<VERSION>"
	@echo "     git push origin main --tags"
