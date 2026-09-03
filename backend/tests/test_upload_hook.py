"""Upload webhook tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_tusd_hook_stub_accepts_payload(client: AsyncClient) -> None:
    """POST /api/v1/upload/hook should accept tusd hook payloads."""
    response = await client.post(
        "/api/v1/upload/hook",
        json={"Type": "post-finish", "Event": {"Upload": {"ID": "test-upload-id"}}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
