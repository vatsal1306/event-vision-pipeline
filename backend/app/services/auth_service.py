"""Photographer registration, login, OTP, JWT, and password reset."""

from __future__ import annotations

import re
from uuid import UUID

import redis.asyncio as redis
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.constants import INDIAN_PHONE_PATTERN, JWTType
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PhoneNotVerifiedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
    hash_password,
    refresh_token_denylist_key,
    verify_password,
)
from app.models.photographer import Photographer
from app.schemas.auth import (
    ForgotPasswordResponse,
    LoginOtpPendingResponse,
    PhotographerProfile,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordResponse,
    SendOTPResponse,
    TokenResponse,
)
from app.utils.otp import OTPService


class AuthService:
    """Business logic for photographer authentication flows."""

    def __init__(
        self,
        db: AsyncSession,
        otp_service: OTPService,
        redis_client: redis.Redis,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the auth service with database and OTP dependencies."""
        self.db = db
        self.otp_service = otp_service
        self.redis = redis_client
        self.settings = settings or get_settings()

    async def register(self, request: RegisterRequest) -> RegisterResponse:
        """Create a photographer account and send a registration OTP.

        Args:
            request: Registration payload.

        Returns:
            Created account metadata without JWT tokens.

        Raises:
            ConflictError: When email or phone is already registered.
        """
        await self._ensure_unique_email_and_phone(request.email, request.phone)

        photographer = Photographer(
            email=request.email.lower(),
            password_hash=hash_password(request.password),
            studio_name=request.studio_name,
            phone=request.phone,
            phone_verified=False,
        )
        self.db.add(photographer)
        await self.db.flush()

        await self.otp_service.send_otp(request.phone, "registration")

        return RegisterResponse(
            id=photographer.id,
            email=photographer.email,
            studio_name=photographer.studio_name,
            phone=photographer.phone,
            message="OTP sent to your phone for verification",
        )

    async def login(self, email_or_phone: str, password: str) -> LoginOtpPendingResponse:
        """Validate credentials and send a login OTP to the registered phone.

        Args:
            email_or_phone: Photographer email or ``+91`` phone number.
            password: Plaintext password.

        Returns:
            OTP pending response with the registered phone for step two.

        Raises:
            AuthenticationError: When credentials are invalid.
            PhoneNotVerifiedError: When registration OTP was never completed.
        """
        photographer = await self._get_photographer_by_identifier(email_or_phone)
        if photographer is None or not verify_password(password, photographer.password_hash):
            raise AuthenticationError("Invalid email or password")

        if not photographer.phone_verified:
            raise PhoneNotVerifiedError()

        if not photographer.is_active:
            raise AuthenticationError("Account not found or inactive")

        await self.otp_service.send_otp(photographer.phone, "login")

        return LoginOtpPendingResponse(
            phone=photographer.phone,
            message="OTP sent to your registered phone",
            expires_in=self.otp_service.otp_expiry_seconds,
        )

    async def send_otp(self, phone: str, purpose: str) -> SendOTPResponse:
        """Send or resend an OTP for the given phone and purpose.

        Args:
            phone: Registered phone number.
            purpose: OTP purpose (registration, login, password_reset).

        Returns:
            Dispatch acknowledgement.

        Raises:
            NotFoundError: When no photographer exists for the phone (non-registration).
        """
        if purpose != "registration":
            photographer = await self._get_photographer_by_phone(phone)
            if photographer is None:
                raise NotFoundError("Account")

        await self.otp_service.send_otp(phone, purpose)
        return SendOTPResponse(
            message="OTP sent successfully",
            expires_in=self.otp_service.otp_expiry_seconds,
        )

    async def verify_otp_and_login(
        self,
        phone: str,
        otp: str,
        purpose: str,
    ) -> TokenResponse:
        """Verify an OTP and issue JWT tokens when appropriate.

        Args:
            phone: Phone number the OTP was sent to.
            otp: User-supplied OTP.
            purpose: OTP purpose namespace.

        Returns:
            Token pair and photographer profile.

        Raises:
            AuthenticationError: When OTP is invalid.
            NotFoundError: When the account does not exist.
        """
        verified = await self.otp_service.verify_otp(phone, purpose, otp)
        if not verified:
            raise AuthenticationError("Invalid OTP")

        photographer = await self._get_photographer_by_phone(phone)
        if photographer is None:
            raise NotFoundError("Account")

        if purpose == "registration":
            photographer.phone_verified = True
            await self.db.flush()

        if not photographer.is_active:
            raise AuthenticationError("Account not found or inactive")

        return await self._build_token_response(photographer)

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Rotate refresh token and issue a new access/refresh pair.

        Args:
            refresh_token: Current refresh JWT.

        Returns:
            New token pair and photographer profile.

        Raises:
            AuthenticationError: When the refresh token is invalid or revoked.
        """
        payload = await self._decode_refresh_token(refresh_token)
        photographer = await self.db.get(Photographer, UUID(payload["sub"]))
        if photographer is None or not photographer.is_active:
            raise AuthenticationError("Account not found or inactive")

        await self._denylist_refresh_jti(payload["jti"], refresh_token)
        return await self._build_token_response(photographer)

    async def logout(self, refresh_token: str) -> None:
        """Revoke a refresh token by adding its ``jti`` to the Redis denylist."""
        payload = await self._decode_refresh_token(refresh_token)
        await self._denylist_refresh_jti(payload["jti"], refresh_token)

    async def forgot_password(self, email_or_phone: str) -> ForgotPasswordResponse:
        """Send a password-reset OTP to the account's registered phone.

        Always returns a generic message to avoid account enumeration.
        """
        photographer = await self._get_photographer_by_identifier(email_or_phone)
        if photographer is not None and photographer.phone_verified:
            await self.otp_service.send_otp(photographer.phone, "password_reset")

        return ForgotPasswordResponse(
            message="If an account exists, an OTP has been sent to the registered phone",
        )

    async def reset_password(
        self,
        email_or_phone: str,
        otp: str,
        new_password: str,
    ) -> ResetPasswordResponse:
        """Reset password after OTP verification.

        Args:
            email_or_phone: Account email or phone used in forgot-password step.
            otp: OTP sent to the registered phone.
            new_password: New plaintext password.

        Returns:
            Success message.

        Raises:
            NotFoundError: When the account does not exist.
            AuthenticationError: When OTP verification fails.
        """
        photographer = await self._get_photographer_by_identifier(email_or_phone)
        if photographer is None:
            raise NotFoundError("Account")

        verified = await self.otp_service.verify_otp(photographer.phone, "password_reset", otp)
        if not verified:
            raise AuthenticationError("Invalid OTP")

        photographer.password_hash = hash_password(new_password)
        await self.db.flush()

        return ResetPasswordResponse(message="Password reset successfully")

    async def get_photographer_by_id(self, photographer_id: UUID) -> Photographer | None:
        """Load a photographer by primary key."""
        return await self.db.get(Photographer, photographer_id)

    async def _build_token_response(self, photographer: Photographer) -> TokenResponse:
        """Create access/refresh tokens and serialize the photographer profile."""
        access_token, expires_in = create_access_token(
            str(photographer.id),
            settings=self.settings,
        )
        refresh_token, _jti, _refresh_expires = create_refresh_token(
            str(photographer.id),
            settings=self.settings,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            photographer=PhotographerProfile.model_validate(photographer),
        )

    async def _decode_refresh_token(self, refresh_token: str) -> dict[str, str]:
        """Decode and validate a refresh token including denylist checks."""
        try:
            payload = decode_jwt(refresh_token, settings=self.settings)
        except JWTError as exc:
            raise AuthenticationError("Invalid refresh token") from exc

        if payload.get("type") != JWTType.REFRESH.value:
            raise AuthenticationError("Invalid token type")

        jti = payload.get("jti")
        if not jti:
            raise AuthenticationError("Invalid refresh token")

        if await self.redis.exists(refresh_token_denylist_key(jti)):
            raise AuthenticationError("Refresh token has been revoked")

        return {"sub": str(payload["sub"]), "jti": str(jti)}

    async def _denylist_refresh_jti(self, jti: str, refresh_token: str) -> None:
        """Store a refresh token ``jti`` in Redis until the token naturally expires."""
        try:
            payload = decode_jwt(refresh_token, settings=self.settings)
            exp = int(payload["exp"])
        except (JWTError, KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("Invalid refresh token") from exc

        from datetime import datetime, timezone

        remaining_seconds = max(
            1,
            exp - int(datetime.now(tz=timezone.utc).timestamp()),
        )
        await self.redis.setex(refresh_token_denylist_key(jti), remaining_seconds, "1")

    async def _ensure_unique_email_and_phone(self, email: str, phone: str) -> None:
        """Raise when email or phone is already registered."""
        normalized_email = email.lower()
        email_exists = await self.db.scalar(
            select(Photographer.id).where(Photographer.email == normalized_email)
        )
        if email_exists is not None:
            raise ConflictError("Email already registered")

        phone_exists = await self.db.scalar(
            select(Photographer.id).where(Photographer.phone == phone)
        )
        if phone_exists is not None:
            raise ConflictError("Phone number already registered")

    async def _get_photographer_by_identifier(self, email_or_phone: str) -> Photographer | None:
        """Resolve a photographer by email or Indian phone number."""
        normalized = email_or_phone.strip()
        if re.fullmatch(INDIAN_PHONE_PATTERN, normalized):
            return await self._get_photographer_by_phone(normalized)

        if "@" in normalized:
            result = await self.db.execute(
                select(Photographer).where(Photographer.email == normalized.lower())
            )
            return result.scalar_one_or_none()

        phone_candidate = normalized if normalized.startswith("+") else f"+91{normalized}"
        if re.fullmatch(INDIAN_PHONE_PATTERN, phone_candidate):
            return await self._get_photographer_by_phone(phone_candidate)

        result = await self.db.execute(
            select(Photographer).where(Photographer.email == normalized.lower())
        )
        return result.scalar_one_or_none()

    async def _get_photographer_by_phone(self, phone: str) -> Photographer | None:
        """Load a photographer by unique phone number."""
        result = await self.db.execute(select(Photographer).where(Photographer.phone == phone))
        return result.scalar_one_or_none()
