"""Tests for security headers middleware."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.security_headers import SecurityHeadersMiddleware


@pytest.fixture
async def client():
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_security_headers_present(client):
    """Test that all required security headers are present on API responses."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    # Content-Security-Policy
    assert "content-security-policy" in response.headers
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp

    # X-Content-Type-Options
    assert response.headers.get("x-content-type-options") == "nosniff"

    # X-Frame-Options
    assert response.headers.get("x-frame-options") == "DENY"

    # X-XSS-Protection
    assert response.headers.get("x-xss-protection") == "1; mode=block"

    # Referrer-Policy
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    # Permissions-Policy
    permissions = response.headers.get("permissions-policy", "")
    assert "camera=()" in permissions
    assert "microphone=()" in permissions
    assert "geolocation=()" in permissions


@pytest.mark.asyncio
async def test_csp_header_content(client):
    """Test the specific content of the CSP header."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    csp = response.headers["content-security-policy"]

    # Verify key CSP directives
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "img-src 'self' data:" in csp
    assert "font-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "frame-src 'none'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "form-action 'self'" in csp


@pytest.mark.asyncio
async def test_hsts_not_set_over_http(client):
    """Test that HSTS is NOT set when request is over plain HTTP."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    # HSTS should NOT be present on HTTP connections
    assert "strict-transport-security" not in response.headers


@pytest.mark.asyncio
async def test_hsts_set_over_https():
    """Test that HSTS IS set when request is over HTTPS."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="https://test",
    ) as ac:
        response = await ac.get("/api/v1/health")
        assert response.status_code == 200
        assert response.headers.get("strict-transport-security") is not None
        assert "max-age=31536000" in response.headers["strict-transport-security"]


@pytest.mark.asyncio
async def test_security_headers_on_error_responses(client):
    """Test that security headers are present even on error responses."""
    response = await client.get("/api/v1/nonexistent-endpoint")
    # Should still have security headers even on 404
    assert "x-content-type-options" in response.headers
    assert "x-frame-options" in response.headers
    assert "content-security-policy" in response.headers


@pytest.mark.asyncio
async def test_security_headers_on_frontend_paths(client):
    """Test that security headers are present on frontend SPA paths."""
    response = await client.get("/")
    # Frontend paths should also have security headers
    assert "x-content-type-options" in response.headers
    assert "x-frame-options" in response.headers
