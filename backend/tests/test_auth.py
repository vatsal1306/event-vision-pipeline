"""Integration tests for photographer authentication."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_redis_dep
from app.core.database import get_db
from app.core.redis_client import create_redis_client
from app.main import app
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

VALID_PASSWORD = "Password1!"
REGISTER_PAYLOAD = {
    "email": "studio@example.com",
    "password": VALID_PASSWORD,
    "studio_name": "Awesome Studio",
    "phone": "+919876543210",
}


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator:
    """Dedicated Redis client flushed before each auth test."""
    client = create_redis_client()
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def auth_client(db_session, redis_client) -> AsyncIterator[AsyncClient]:
    """HTTP client with database and Redis dependencies overridden."""

    async def override_get_db() -> AsyncIterator:
        yield db_session

    async def override_get_redis() -> AsyncIterator:
        yield redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_dep] = override_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def _read_otp(redis_client, phone: str, purpose: str) -> str:
    otp_service = OTPService(redis_client, SMSService())
    stored = await otp_service.peek_otp(phone, purpose)
    assert stored is not None
    return stored


async def _register_and_verify(auth_client: AsyncClient, redis_client) -> dict:
    response = await auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    otp = await _read_otp(redis_client, REGISTER_PAYLOAD["phone"], "registration")
    verify_response = await auth_client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": REGISTER_PAYLOAD["phone"],
            "otp": otp,
            "purpose": "registration",
        },
    )
    assert verify_response.status_code == 200
    return verify_response.json()


@pytest.mark.asyncio
async def test_register_verify_login_refresh_flow(auth_client, redis_client) -> None:
    """Register, verify OTP, login with OTP, refresh tokens, and logout."""
    register_response = await auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert "access_token" not in body

    otp = await _read_otp(redis_client, REGISTER_PAYLOAD["phone"], "registration")
    verify_response = await auth_client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": REGISTER_PAYLOAD["phone"],
            "otp": otp,
            "purpose": "registration",
        },
    )
    assert verify_response.status_code == 200
    tokens = verify_response.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["photographer"]["phone_verified"] is True

    login_response = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email_or_phone": REGISTER_PAYLOAD["email"],
            "password": VALID_PASSWORD,
        },
    )
    assert login_response.status_code == 200
    login_body = login_response.json()
    assert login_body["otp_sent"] is True

    login_otp = await _read_otp(redis_client, REGISTER_PAYLOAD["phone"], "login")
    login_verify = await auth_client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": REGISTER_PAYLOAD["phone"],
            "otp": login_otp,
            "purpose": "login",
        },
    )
    assert login_verify.status_code == 200

    refresh_response = await auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_verify.json()["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"] != login_verify.json()["refresh_token"]

    logout_response = await auth_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
        json={"refresh_token": refreshed["refresh_token"]},
    )
    assert logout_response.status_code == 204


@pytest.mark.asyncio
async def test_login_bad_password_returns_401(auth_client, redis_client) -> None:
    """Invalid password returns 401 without revealing account existence details."""
    await auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email_or_phone": REGISTER_PAYLOAD["email"],
            "password": "WrongPass1!",
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_login_before_phone_verification_returns_phone_not_verified(
    auth_client,
    redis_client,
) -> None:
    """Login is blocked until registration OTP verification completes."""
    await auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email_or_phone": REGISTER_PAYLOAD["email"],
            "password": VALID_PASSWORD,
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "PHONE_NOT_VERIFIED"


@pytest.mark.asyncio
async def test_otp_reuse_after_success_fails(auth_client, redis_client) -> None:
    """A consumed OTP cannot be verified again."""
    await auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    otp = await _read_otp(redis_client, REGISTER_PAYLOAD["phone"], "registration")

    first = await auth_client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": REGISTER_PAYLOAD["phone"],
            "otp": otp,
            "purpose": "registration",
        },
    )
    assert first.status_code == 200

    second = await auth_client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": REGISTER_PAYLOAD["phone"],
            "otp": otp,
            "purpose": "registration",
        },
    )
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_fourth_otp_attempt_returns_max_attempts(auth_client, redis_client) -> None:
    """The fourth OTP verification attempt returns OTP_MAX_ATTEMPTS."""
    await auth_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    for _ in range(3):
        response = await auth_client.post(
            "/api/v1/auth/verify-otp",
            json={
                "phone": REGISTER_PAYLOAD["phone"],
                "otp": "000000",
                "purpose": "registration",
            },
        )
        assert response.status_code == 401

    fourth = await auth_client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": REGISTER_PAYLOAD["phone"],
            "otp": "000000",
            "purpose": "registration",
        },
    )
    assert fourth.status_code == 429
    assert fourth.json()["code"] == "OTP_MAX_ATTEMPTS"


@pytest.mark.asyncio
async def test_reset_password_with_otp(auth_client, redis_client) -> None:
    """Forgot password sends OTP and reset-password updates the password."""
    await _register_and_verify(auth_client, redis_client)

    forgot = await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email_or_phone": REGISTER_PAYLOAD["email"]},
    )
    assert forgot.status_code == 200

    otp = await _read_otp(redis_client, REGISTER_PAYLOAD["phone"], "password_reset")
    new_password = "NewPass2@"
    reset = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={
            "email_or_phone": REGISTER_PAYLOAD["email"],
            "otp": otp,
            "new_password": new_password,
        },
    )
    assert reset.status_code == 200

    login_response = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email_or_phone": REGISTER_PAYLOAD["email"],
            "password": new_password,
        },
    )
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_openapi_documents_auth_routes(auth_client) -> None:
    """Auth routes appear in the OpenAPI schema when docs are enabled."""
    response = await auth_client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/verify-otp" in paths
