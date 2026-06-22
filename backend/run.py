#!/usr/bin/env python3
"""PyInstaller entry point — produces a single-file binary that bundles the
FastAPI backend together with the React frontend (frontend/dist).

Build command (from repo root):
    cd frontend && npm ci && npm run build && cd ..
    pip install -r backend/requirements.txt pyinstaller
    pyinstaller --onefile \
        --name "proxysql-admin-webui" \
        --add-data "frontend/dist:frontend/dist" \
        backend/run.py

The resulting `dist/proxysql-admin-webui` is a standalone executable.
Run it directly — no Python, Node, or Docker required:

    ./proxysql-admin-webui --host 0.0.0.0 --port 8080
"""
import os
import sys

import uvicorn

from app.main import app


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))

    # Accept --host / --port CLI overrides (optional convenience)
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        else:
            i += 1

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
