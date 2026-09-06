"""Tests for BE-002: config, exceptions, middleware."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.exceptions import NotFoundError
from app.main import app


# Create a dummy route for testing exception handling
@app.get("/test-not-found")
async def dummy_not_found():
    raise NotFoundError("Dummy")


@app.get("/test-validation")
async def dummy_validation(id: int):
    return {"id": id}


@pytest.mark.asyncio
async def test_not_found_exception_handler():
    """Test that NotFoundError returns 404 with correct JSON."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test-not-found")
        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "NOT_FOUND"
        assert data["detail"] == "Dummy not found"
        assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_validation_exception_handler():
    """Test that RequestValidationError returns 422 with custom format."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test-validation?id=not-an-int")
        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"
        assert data["detail"] == "Validation error"
        assert len(data["errors"]) > 0
        assert data["errors"][0]["field"] == "query.id"


def test_settings_loaded():
    """Test that settings are loaded correctly."""
    assert settings.app_name == "AI Photo Sharing Platform"
    assert settings.aws_region == "ap-south-1"
