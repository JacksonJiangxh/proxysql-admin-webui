# ── Stage 1: build the frontend ──────────────────────────────────
FROM node:24-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: backend runtime (also serves the built frontend) ────
FROM python:3.12-slim

WORKDIR /app

# mysql-client is required by execute_admin_command() which shells out to
# the `mysql` CLI for ProxySQL LOAD/SAVE admin commands.
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

# Copy the built frontend into the image and tell the app where to find it.
# FastAPI serves it same-origin via StaticFiles — no nginx needed.
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
ENV FRONTEND_DIST=/app/frontend/dist

# Persistent data volume
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
