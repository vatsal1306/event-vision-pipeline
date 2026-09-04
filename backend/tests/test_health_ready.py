"""Readiness health endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ready_returns_ready_when_database_available(
    migrated_databases: None,
    client: AsyncClient,
) -> None:
    """GET /health/ready should succeed when PostgreSQL is reachable."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
