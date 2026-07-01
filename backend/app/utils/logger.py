"""Structured JSON logging setup for production environments.

When LOG_FORMAT=json (or LOG_LEVEL is set), logs are emitted as JSON lines
suitable for ingestion by ELK, Loki, or other log aggregation systems.

Usage:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("proxy connection established", extra={"server_id": srv_id})
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON lines with standardised fields."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        # Include any extra fields passed via logger.info(..., extra={...})
        for key in ("server_id", "user_id", "request_id", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, default=str, ensure_ascii=False)


def setup_logging(log_level: str = "INFO", json_format: bool = True) -> None:
    """Configure the root logger with structured or plain-text output.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        json_format: If True, emit JSON lines; otherwise use a readable
            colored format suitable for development.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove any existing handlers (uvicorn adds its own)
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance. Identical to logging.getLogger but signals intent."""
    return logging.getLogger(name)
