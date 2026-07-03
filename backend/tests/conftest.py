"""Global test fixtures for the ProxySQL Admin WebUI backend tests.

Provides:
- setup_db: autouse fixture that creates an isolated SQLite database per test
- Rate limiter reset: all rate limiters are reset between tests so each test
  starts with a clean state, but the actual security code paths are fully exercised.
"""
import os
import pytest

# ── Ensure FERNET_KEY is set before importing app modules ──
if "FERNET_KEY" not in os.environ:
    from cryptography.fernet import Fernet
    os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

from app.database import init_db

# ── Rate limiter tracking ──────────────────────────────────────────
# We track every SimpleRateLimiter instance so we can reset their
# internal stores between tests. This way rate limiting code is
# still exercised (not disabled), but each test starts clean.

_all_simple_rate_limiters: list = []


def _track_limiter_instance(limiter) -> None:
    """Register a SimpleRateLimiter instance for later reset."""
    _all_simple_rate_limiters.append(limiter)


def _reset_all_rate_limiters() -> None:
    """Reset all rate limiter stores between tests.

    This ensures each test starts with a clean rate limit state,
    but the actual rate limiting logic is still exercised during tests.
    """
    # Clear all tracked SimpleRateLimiter instances (global + endpoint-specific)
    for limiter in _all_simple_rate_limiters:
        limiter._store.clear()

    # Also clear the LoginRateLimiter's module-level limiter
    from app.middleware.rate_limit import _login_limiter
    _login_limiter._store.clear()


# ── Monkey-patch SimpleRateLimiter.__init__ to track instances ──
from app.middleware.rate_limit import SimpleRateLimiter

_original_simple_init = SimpleRateLimiter.__init__


def _tracking_init(self, max_requests: int, window_seconds: int):
    _original_simple_init(self, max_requests, window_seconds)
    _track_limiter_instance(self)


SimpleRateLimiter.__init__ = _tracking_init


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Set up a temporary test database for each test.

    Creates an isolated SQLite database per test and resets rate limiters.
    Security features (rate limiting, CSRF) are fully active - rate limiters
    are only reset between tests, not disabled.
    """
    import app.database as db_module

    test_db = tmp_path / "test_app.db"
    original_path = db_module.DB_PATH
    db_module.DB_PATH = test_db
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"

    await init_db()

    # Reset rate limiters so each test starts clean
    _reset_all_rate_limiters()

    yield

    db_module.DB_PATH = original_path
    if test_db.exists():
        test_db.unlink()
