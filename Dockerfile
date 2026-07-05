# ── Stage 1: build the frontend ──────────────────────────────────
FROM node:24-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: backend runtime (also serves the built frontend) ────
FROM python:3.12-slim

# Create non-root user for security (container should never run as root)
RUN groupadd -r proxysql && useradd -r -g proxysql -d /app -s /sbin/nologin proxysql

WORKDIR /app

# mysql-client is required by execute_admin_command() which shells out to
# the `mysql` CLI for ProxySQL LOAD/SAVE admin commands.
# curl is required for the Docker HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy version file and backend source
COPY VERSION ./
COPY backend/ ./

# Copy the built frontend into the image and tell the app where to find it.
# FastAPI serves it same-origin via StaticFiles — no nginx needed.
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
ENV FRONTEND_DIST=/app/frontend/dist

# Persistent data volume
RUN mkdir -p /app/data
VOLUME ["/app/data"]

# Change ownership to non-root user
RUN chown -R proxysql:proxysql /app

# Entrypoint: auto-fix bind mount permissions before starting the app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Health check: verify the API is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health || exit 1

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
