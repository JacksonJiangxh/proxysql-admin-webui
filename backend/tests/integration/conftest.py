"""Integration test fixtures for the ProxySQL Admin WebUI.

Provides:
- test_app: FastAPI TestClient via httpx.ASGITransport
- auth_headers: login as admin, return Bearer + CSRF headers
- admin_token / operator_token / viewer_token: role-specific tokens
- test_server: registered test server configuration
- test_server_id: the ID of the registered server
- test_wizard_execution: runs a wizard preview and returns the result
- auth_user: raw user dict from /auth/me

All fixtures are self-cleaning via the autouse setup_db fixture that
uses a temporary SQLite database per test.

IMPORTANT: Security features (rate limiting, CSRF) are NOT disabled.
Rate limiters are RESET between tests so each test has a clean state,
but the actual security code paths are fully exercised.
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport

# ── Ensure FERNET_KEY is set before importing app modules ──
if "FERNET_KEY" not in os.environ:
    from cryptography.fernet import Fernet
    os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

from app.main import app
from app.database import init_db, DB_PATH


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

    # Also clear the LoginRateLimiter's underlying limiter
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

    test_db = tmp_path / "test_integration.db"
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


# ── Test client ────────────────────────────────────

@pytest.fixture
async def test_app():
    """Return an AsyncClient connected to the FastAPI app via ASGITransport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── Auth helpers ───────────────────────────────────

async def _login(client: AsyncClient, username: str, password: str) -> dict:
    """Login and return the full token response."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": username, "password": password
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()


async def _get_csrf_token(client: AsyncClient, access_token: str) -> str | None:
    """Fetch a CSRF token by hitting a non-exempt GET endpoint."""
    resp = await client.get("/api/v1/servers", headers={
        "Authorization": f"Bearer {access_token}"
    })
    for cookie in resp.cookies.jar:
        if cookie.name == "csrf_token":
            return cookie.value
    return None


async def _build_auth_headers(client: AsyncClient, username: str, password: str) -> dict:
    """Login and return headers with Authorization + X-CSRF-Token."""
    token_data = await _login(client, username, password)
    access_token = token_data["access_token"]
    csrf = await _get_csrf_token(client, access_token)
    headers = {"Authorization": f"Bearer {access_token}"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
        # httpx ASGI transport uses "test.local" as the cookie domain
        # when base_url is "http://test"
        client.cookies.set("csrf_token", csrf, domain="test.local")
    return headers


async def _refresh_csrf_headers(client: AsyncClient, access_token: str) -> dict:
    """Refresh CSRF token and return updated auth headers.

    Call this after each state-changing request (POST/PUT/PATCH/DELETE)
    because the CSRF middleware rotates the token on each such request.
    """
    csrf = await _get_csrf_token(client, access_token)
    headers = {"Authorization": f"Bearer {access_token}"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
        client.cookies.set("csrf_token", csrf, domain="test.local")
    return headers


@pytest.fixture
async def auth_headers(test_app):
    """Return auth headers (Bearer + CSRF) for the admin user."""
    return await _build_auth_headers(test_app, "admin", "admin")


@pytest.fixture
async def admin_token(auth_headers):
    """Return admin access token string (extracted from auth_headers)."""
    return auth_headers["Authorization"].replace("Bearer ", "")


@pytest.fixture
async def operator_token(test_app):
    """Create an operator user and return their access token.

    Uses its own auth headers to avoid consuming the CSRF token
    that other fixtures/tests in the same function need.
    """
    headers = await _build_auth_headers(test_app, "admin", "admin")
    resp = await test_app.post("/api/v1/users", json={
        "username": "test_operator",
        "password": "Operator123!",
        "role": "operator",
    }, headers=headers)
    assert resp.status_code == 200, f"Failed to create operator: {resp.text}"

    data = await _login(test_app, "test_operator", "Operator123!")
    return data["access_token"]


@pytest.fixture
async def viewer_token(test_app):
    """Create a viewer user and return their access token.

    Uses its own auth headers to avoid consuming the CSRF token
    that other fixtures/tests in the same function need.
    """
    headers = await _build_auth_headers(test_app, "admin", "admin")
    resp = await test_app.post("/api/v1/users", json={
        "username": "test_viewer",
        "password": "Viewer123!",
        "role": "viewer",
    }, headers=headers)
    assert resp.status_code == 200, f"Failed to create viewer: {resp.text}"

    data = await _login(test_app, "test_viewer", "Viewer123!")
    return data["access_token"]


@pytest.fixture
async def auth_user(test_app, admin_token):
    """Return the authenticated user dict from /auth/me."""
    resp = await test_app.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200
    return resp.json()


# ── CSRF refresh helper (for tests that make multiple state-changing requests) ─

@pytest.fixture
def refresh_csrf():
    """Return a function that refreshes CSRF token for a client.

    Usage:
        headers = await refresh_csrf(test_app, admin_token)
    """
    return _refresh_csrf_headers


# ── Server fixtures ────────────────────────────────

@pytest.fixture
async def test_server(test_app, admin_token):
    """Register a test ProxySQL server and return its config dict.

    Uses admin_token directly (not auth_headers) to avoid consuming
    the CSRF token that other tests in the same function need.
    The CSRF middleware will still validate the token — we fetch
    a fresh one just for this request.
    """
    # Build auth headers with a fresh CSRF token for this request
    headers = await _build_auth_headers(test_app, "admin", "admin")
    resp = await test_app.post("/api/v1/servers", json={
        "name": "integration-test-server",
        "host": "127.0.0.1",
        "port": 6032,
        "admin_user": "admin",
        "admin_password": "admin",
        "is_default": True,
    }, headers=headers)
    assert resp.status_code == 200, f"Failed to create test server: {resp.text}"
    return resp.json()


@pytest.fixture
async def test_server_id(test_server):
    """Return the ID of the registered test server."""
    return test_server["id"]


# ── Wizard fixtures ────────────────────────────────

@pytest.fixture
async def test_wizard_preview(test_app, auth_headers, test_server_id):
    """Run a W01 wizard preview and return the result."""
    resp = await test_app.post("/api/v1/wizards/preview", json={
        "wizard_id": "W01",
        "server_id": test_server_id,
        "fields": {
            "hostgroup_id": 0,
            "hostname": "10.0.0.1",
            "port": 3306,
        },
    }, headers=auth_headers)
    assert resp.status_code == 200, f"Wizard preview failed: {resp.text}"
    return resp.json()
