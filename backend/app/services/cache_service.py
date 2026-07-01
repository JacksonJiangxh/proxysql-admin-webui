"""
Application-level data cache with TTL support.

Uses in-memory TTLCache as the primary backend. Designed for single-process
deployments. Can be extended with Redis backend by implementing the same
interface and making the backend configurable via Settings.CACHE_BACKEND.

Cache invalidation strategy:
- TTL-based automatic expiry for all cached entries.
- Manual invalidation on write operations (sync apply/save/discard/load).
- Dashboard snapshots have short TTL (5-15s) — data is inherently ephemeral.
- Config diffs have medium TTL (30-60s) — stale after config changes.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from cachetools import TTLCache

logger = logging.getLogger(__name__)


class CacheService:
    """In-memory cache with TTL, designed for API response caching.

    Cache keys are deterministically generated from (prefix, *args, **kwargs)
    so that identical requests hit the same key.
    """

    def __init__(
        self,
        dashboard_ttl: int = 10,
        config_diff_ttl: int = 60,
        maxsize: int = 256,
    ):
        """Initialize cache with per-category TTL values.

        Args:
            dashboard_ttl: Seconds to cache dashboard snapshots (default 10s).
            config_diff_ttl: Seconds to cache config diffs (default 60s).
            maxsize: Maximum number of cached entries (LRU eviction).
        """
        self._dashboard_ttl = dashboard_ttl
        self._config_diff_ttl = config_diff_ttl
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=max(dashboard_ttl, config_diff_ttl))
        self._hits = 0
        self._misses = 0

    def _make_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Generate a deterministic cache key.

        All positional and keyword arguments are serialized to JSON and hashed,
        ensuring identical logical requests map to the same key regardless of
        argument order in kwargs.
        """
        payload = json.dumps(
            {"prefix": prefix, "args": args, "kwargs": kwargs},
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"{prefix}:{digest}"

    def get_dashboard_snapshot(
        self, server_id: str, digest_limit: int = 10
    ) -> Optional[dict]:
        """Retrieve a cached dashboard snapshot if not expired."""
        key = self._make_key("dashboard", server_id=server_id, digest_limit=digest_limit)
        value = self._cache.get(key)
        if value is not None:
            self._hits += 1
            logger.debug(f"Cache HIT: {key}")
            # Return a shallow copy to prevent callers from mutating cached data
            return dict(value) if isinstance(value, dict) else value
        self._misses += 1
        logger.debug(f"Cache MISS: {key}")
        return None

    def set_dashboard_snapshot(
        self, server_id: str, digest_limit: int, data: dict
    ) -> None:
        """Store a dashboard snapshot with short TTL."""
        key = self._make_key("dashboard", server_id=server_id, digest_limit=digest_limit)
        # Store with explicit TTL for dashboard entries
        self._cache[key] = data
        logger.debug(f"Cache SET (dashboard, ttl={self._dashboard_ttl}s): {key}")

    def get_config_diff(
        self, server_id: str, table: Optional[str] = None
    ) -> Optional[dict]:
        """Retrieve a cached config diff if not expired."""
        key = self._make_key("config_diff", server_id=server_id, table=table)
        value = self._cache.get(key)
        if value is not None:
            self._hits += 1
            logger.debug(f"Cache HIT: {key}")
            return dict(value) if isinstance(value, dict) else value
        self._misses += 1
        logger.debug(f"Cache MISS: {key}")
        return None

    def set_config_diff(
        self, server_id: str, table: Optional[str], data: dict
    ) -> None:
        """Store a config diff with medium TTL."""
        key = self._make_key("config_diff", server_id=server_id, table=table)
        self._cache[key] = data
        logger.debug(f"Cache SET (config_diff, ttl={self._config_diff_ttl}s): {key}")

    def invalidate_config_diff(self, server_id: str) -> int:
        """Remove all cached config diffs for a server.

        Called after sync operations (apply/save/discard/load) to ensure
        stale diffs are not served.

        Returns:
            Number of cache entries invalidated.
        """
        prefix = self._make_key("config_diff", server_id=server_id, table=None)[:20]
        # Collect keys to avoid dict-size-changed-during-iteration
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._cache[k]
        if keys_to_delete:
            logger.info(
                f"Cache INVALIDATE: server={server_id}, removed={len(keys_to_delete)} entries"
            )
        return len(keys_to_delete)

    def clear(self) -> None:
        """Clear all cached entries (useful for testing)."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache CLEAR: all entries removed")

    @property
    def stats(self) -> dict:
        """Return cache statistics for monitoring."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "maxsize": self._cache.maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
            "dashboard_ttl": self._dashboard_ttl,
            "config_diff_ttl": self._config_diff_ttl,
        }


# Singleton — one instance shared across the application.
cache_service = CacheService()
