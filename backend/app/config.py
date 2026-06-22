"""Application configuration management.

.env file search order (first match wins):
    1. ENV_FILE environment variable (explicit path)
    2. ./.env   — current working directory   (binary, docker, dev)
    3. ../.env  — project root relative to this file  (dev fallback)

Environment variables already set in the process (e.g. via docker compose
`env_file:`) take precedence over values from the .env file.
"""
import os
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent  # backend/app/
DATA_DIR = _BASE_DIR.parent / "data"          # backend/data/


def _find_env_file() -> Path | None:
    """Locate the .env file using the standardised search order."""
    # 1. explicit override via ENV_FILE env var
    if p := os.getenv("ENV_FILE"):
        path = Path(p)
        if path.is_file():
            return path

    # 2. current working directory — works for:
    #    • binary: user places .env next to the executable
    #    • Docker (docker compose `working_dir: /app`) → /app/.env
    #    • dev: running from project root
    cwd_env = Path.cwd() / ".env"
    if cwd_env.is_file():
        return cwd_env

    # 3. fallback: one level above this file (project root)
    #    e.g. proxysql-admin-webui/.env when __file__ is backend/app/config.py
    project_env = _BASE_DIR.parent / ".env"
    if project_env.is_file():
        return project_env

    return None


# Load .env file — only sets variables that are not already present in
# os.environ (i.e. explicitly set env vars always win).
_ENV_FILE = _find_env_file()
if _ENV_FILE is not None:
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if key not in os.environ:
                    os.environ[key] = val


class Settings:
    """Application settings loaded from environment variables."""

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production-min-32-chars!!")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/app.db")

    # CORS
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:8080,http://localhost:5173").split(",")
        if origin.strip()
    ]

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ProxySQL defaults
    PROXYSQL_DEFAULT_HOST: str = os.getenv("PROXYSQL_DEFAULT_HOST", "127.0.0.1")
    PROXYSQL_DEFAULT_PORT: int = int(os.getenv("PROXYSQL_DEFAULT_PORT", "6032"))

    # Encryption key for stored credentials (must be set via environment variable)
    FERNET_KEY: str = os.getenv("FERNET_KEY", "")
    if not FERNET_KEY:
        from cryptography.fernet import Fernet
        FERNET_KEY = Fernet.generate_key().decode()
        import warnings
        warnings.warn(
            "FERNET_KEY not set. Auto-generated a temporary key. "
            "Set FERNET_KEY environment variable for production use.",
            RuntimeWarning,
        )

    # Rate limiting
    LOGIN_RATE_LIMIT: str = "5/minute"
    API_RATE_LIMIT: str = "100/minute"
    # TODO: integrate slowapi or a custom in-memory/redis rate limiter
    # and apply LOGIN_RATE_LIMIT to /api/v1/auth/login and API_RATE_LIMIT globally.

    # ── Security Policy Settings ──────────────────────────────────────
    SECURITY_MIN_PASSWORD_LENGTH: int = int(
        os.getenv("SECURITY_MIN_PASSWORD_LENGTH", "8")
    )
    SECURITY_MAX_LOGIN_ATTEMPTS: int = int(
        os.getenv("SECURITY_MAX_LOGIN_ATTEMPTS", "5")
    )
    SECURITY_SESSION_IDLE_TIMEOUT: int = int(
        os.getenv("SECURITY_SESSION_IDLE_TIMEOUT", "30")
    )  # minutes

    # Initial admin user (created on first startup)
    INITIAL_ADMIN_USER: str = os.getenv("PROXYWEB_ADMIN_USER", "admin")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("PROXYWEB_ADMIN_PASSWORD", "admin")


settings = Settings()
