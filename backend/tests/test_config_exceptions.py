"""API tests for BE-002: errors, CORS, request IDs, and settings."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.constants import REQUEST_ID_HEADER
from app.core.exceptions import NotFoundError
from app.main import create_app


class EchoBody(BaseModel):
    """Minimal body used only in tests to trigger validation errors."""

    name: str = Field(min_length=1)


def _register_test_routes(app: FastAPI) -> None:
    """Attach dummy routes that never ship in the real application."""

    @app.get("/__test__/not-found")
    async def raise_not_found() -> None:
        raise NotFoundError("Widget")

    @app.post("/__test__/echo")
    async def echo(body: EchoBody) -> EchoBody:
        return body

    @app.get("/__test__/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")


@pytest.fixture
async def error_client() -> AsyncIterator[AsyncClient]:
    """HTTP client against a fresh app with test-only error routes."""
    app = create_app()
    _register_test_routes(app)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_not_found_error_returns_code(error_client: AsyncClient) -> None:
    """Raising NotFoundError should return 404 with a stable error code."""
    response = await error_client.get("/__test__/not-found")
    assert response.status_code == 404
    assert response.json() == {"detail": "Widget not found", "code": "NOT_FOUND"}
    assert REQUEST_ID_HEADER in response.headers


@pytest.mark.asyncio
async def test_invalid_json_returns_422_field_errors(error_client: AsyncClient) -> None:
    """Malformed JSON should return 422 with the platform validation shape."""
    response = await error_client.post(
        "/__test__/echo",
        content="{not-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"] == "Validation error"
    assert payload["code"] == "VALIDATION_ERROR"
    assert isinstance(payload["errors"], list)
    assert payload["errors"]


@pytest.mark.asyncio
async def test_schema_validation_returns_field_errors(error_client: AsyncClient) -> None:
    """Missing fields should appear in ``errors``."""
    response = await error_client.post("/__test__/echo", json={})
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    fields = {item["field"] for item in payload["errors"]}
    assert any("name" in field for field in fields)


@pytest.mark.asyncio
async def test_unhandled_exception_hides_internals(error_client: AsyncClient) -> None:
    """Unexpected crashes must not leak the exception message to clients."""
    response = await error_client.get("/__test__/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "code": "INTERNAL_ERROR"}
    assert "secret internals" not in response.text


@pytest.mark.asyncio
async def test_reuses_incoming_request_id(error_client: AsyncClient) -> None:
    """Clients may pass X-Request-ID and receive the same value back."""
    response = await error_client.get("/health", headers={REQUEST_ID_HEADER: "client-trace-1"})
    assert response.headers[REQUEST_ID_HEADER] == "client-trace-1"


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should override defaults (and .env) for Settings."""
    monkeypatch.setenv("FRONTEND_URL", "https://photos.example.com")
    monkeypatch.setenv("JWT_GUEST_TOKEN_EXPIRE_DAYS", "30")
    monkeypatch.setenv("SENTRY_DSN", "")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.frontend_url == "https://photos.example.com"
        assert settings.aws_region == "ap-south-1"
        assert settings.jwt_couple_token_expire_days == settings.jwt_guest_token_expire_days
        assert settings.jwt_guest_token_expire_days == 30
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_cors_allows_any_origin_when_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    """Debug mode should allow ``*`` so local frontends can call the API."""
    monkeypatch.setenv("DEBUG", "true")
    get_settings.cache_clear()
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health", headers={"Origin": "http://localhost:9999"})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_cors_allows_configured_frontend_when_not_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-debug CORS must allow only the configured frontend origin."""
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("FRONTEND_URL", "https://app.spotme.test")
    get_settings.cache_clear()
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            allowed = await client.get("/health", headers={"Origin": "https://app.spotme.test"})
            blocked = await client.get("/health", headers={"Origin": "https://evil.example"})
        assert allowed.headers.get("access-control-allow-origin") == "https://app.spotme.test"
        assert blocked.headers.get("access-control-allow-origin") != "https://evil.example"
    finally:
        get_settings.cache_clear()
