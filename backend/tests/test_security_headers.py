"""Tests for HTTP security headers."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_security_headers_present_on_success(client: AsyncClient) -> None:
    """Test that a successful API request includes the security headers."""
    response = await client.get("/health/ready")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"


async def test_security_headers_present_on_error(client: AsyncClient) -> None:
    """Test that a failed API request (e.g., 404) also includes the security headers."""
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
