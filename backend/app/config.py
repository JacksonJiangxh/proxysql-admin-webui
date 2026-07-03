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

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production-min-32-chars!!")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/app.db")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ProxySQL defaults
    PROXYSQL_DEFAULT_HOST: str = os.getenv("PROXYSQL_DEFAULT_HOST", "127.0.0.1")
    PROXYSQL_DEFAULT_PORT: int = int(os.getenv("PROXYSQL_DEFAULT_PORT", "6032"))

    # Encryption key for stored ProxySQL credentials
    FERNET_KEY: str = os.getenv("FERNET_KEY", "")

    _fernet_valid = False
    if FERNET_KEY:
        try:
            from cryptography.fernet import Fernet as _Fernet  # noqa: N813
            _Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)
            _fernet_valid = True
        except Exception:
            pass

    if not _fernet_valid:
        from cryptography.fernet import Fernet
        import warnings
        if FERNET_KEY:
            warnings.warn(
                f"FERNET_KEY is invalid. Auto-generating a temporary key. "
                "Set FERNET_KEY env var for persistence across restarts.",
                RuntimeWarning,
            )
        else:
            warnings.warn(
                "FERNET_KEY not set. Auto-generated a temporary key. "
                "Set FERNET_KEY env var for persistence across restarts.",
                RuntimeWarning,
            )
        FERNET_KEY = Fernet.generate_key().decode()

    # Initial admin user (created on first startup)
    INITIAL_ADMIN_USER: str = os.getenv("PROXYWEB_ADMIN_USER", "admin")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("PROXYWEB_ADMIN_PASSWORD", "admin")


settings = Settings()
