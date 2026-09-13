"""Photographer registration, login, OTP, JWT, and password reset."""

from __future__ import annotations

import re
from uuid import UUID

import redis.asyncio as redis
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.constants import INDIAN_PHONE_PATTERN, JWTType, OTP_CHANNEL_EMAIL, OTP_CHANNEL_SMS
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
    SendOTPRequest,
    SendOTPResponse,
    TokenResponse,
    VerifyOTPRequest,
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
            email_verified=False,
        )
        self.db.add(photographer)
        await self.db.flush()

        await self.otp_service.send_otp(
            request.phone,
            "registration",
            channel=OTP_CHANNEL_SMS,
        )
        await self.otp_service.send_otp(
            photographer.email,
            "registration",
            channel=OTP_CHANNEL_EMAIL,
        )

        return RegisterResponse(
            id=photographer.id,
            email=photographer.email,
            studio_name=photographer.studio_name,
            phone=photographer.phone,
            message="OTPs sent to your phone and email for verification",
        )

    async def login(self, email_or_phone: str, password: str) -> LoginOtpPendingResponse:
        """Validate credentials and send a login OTP to the registered email.

        Args:
            email_or_phone: Photographer email or ``+91`` phone number.
            password: Plaintext password.

        Returns:
            OTP pending response with the registered email for step two.

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

        await self.otp_service.send_otp(
            photographer.email,
            "login",
            channel=OTP_CHANNEL_EMAIL,
        )

        return LoginOtpPendingResponse(
            email=photographer.email,
            message="OTP sent to your registered email",
            expires_in=self.otp_service.otp_expiry_seconds,
        )

    async def send_otp(self, request: SendOTPRequest) -> SendOTPResponse:
        """Send or resend an OTP for the given destination and purpose.

        Args:
            request: Channel, purpose, and phone or email.

        Returns:
            Dispatch acknowledgement.

        Raises:
            NotFoundError: When no photographer exists for a non-registration send.
        """
        if request.channel == OTP_CHANNEL_EMAIL:
            destination = str(request.email).lower()
            if request.purpose != "registration":
                photographer = await self._get_photographer_by_identifier(destination)
                if photographer is None:
                    raise NotFoundError("Account")
                destination = photographer.email
            await self.otp_service.send_otp(
                destination,
                request.purpose,
                channel=OTP_CHANNEL_EMAIL,
            )
        else:
            phone = request.phone or ""
            if request.purpose != "registration":
                photographer = await self._get_photographer_by_phone(phone)
                if photographer is None:
                    raise NotFoundError("Account")
            await self.otp_service.send_otp(phone, request.purpose, channel=OTP_CHANNEL_SMS)

        return SendOTPResponse(
            message="OTP sent successfully",
            expires_in=self.otp_service.otp_expiry_seconds,
        )

    async def verify_otp_and_login(self, request: VerifyOTPRequest) -> TokenResponse:
        """Verify OTPs and issue JWT tokens for registration or login.

        Args:
            request: Purpose-specific OTP payload.

        Returns:
            Token pair and photographer profile.

        Raises:
            AuthenticationError: When OTP is invalid.
            NotFoundError: When the account does not exist.
        """
        if request.purpose == "registration":
            return await self._verify_registration_otps(request)
        return await self._verify_login_otp(request)

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
        """Send independent password-reset OTPs to email and phone.

        Always returns a generic message to avoid account enumeration.
        """
        photographer = await self._get_photographer_by_identifier(email_or_phone)
        if photographer is not None and photographer.phone_verified:
            await self.otp_service.send_otp(
                photographer.phone,
                "password_reset",
                channel=OTP_CHANNEL_SMS,
            )
            await self.otp_service.send_otp(
                photographer.email,
                "password_reset",
                channel=OTP_CHANNEL_EMAIL,
            )

        return ForgotPasswordResponse(
            message=(
                "If an account exists, OTPs have been sent to the registered email and phone"
            ),
        )

    async def reset_password(
        self,
        email_or_phone: str,
        phone_otp: str,
        email_otp: str,
        new_password: str,
    ) -> ResetPasswordResponse:
        """Reset password after both email and SMS OTPs succeed.

        Args:
            email_or_phone: Account email or phone used in forgot-password step.
            phone_otp: OTP sent via SMS.
            email_otp: OTP sent via email.
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

        verified = await self.otp_service.verify_otp_pair(
            phone=photographer.phone,
            phone_otp=phone_otp,
            email=photographer.email,
            email_otp=email_otp,
            purpose="password_reset",
        )
        if not verified:
            raise AuthenticationError("Invalid OTP")

        if verify_password(new_password, photographer.password_hash):
            from app.core.exceptions import BadRequestError

            raise BadRequestError("New password cannot be the same as the current password")

        photographer.password_hash = hash_password(new_password)
        photographer.email_verified = True
        await self.db.flush()

        return ResetPasswordResponse(message="Password reset successfully")

    async def _verify_registration_otps(self, request: VerifyOTPRequest) -> TokenResponse:
        """Consume phone and email registration OTPs, then issue tokens."""
        phone = request.phone or ""
        email = str(request.email).lower()
        photographer = await self._get_photographer_by_phone(phone)
        if photographer is None:
            raise NotFoundError("Account")
        if photographer.email != email:
            raise AuthenticationError("Invalid OTP")

        verified = await self.otp_service.verify_otp_pair(
            phone=phone,
            phone_otp=request.phone_otp or "",
            email=email,
            email_otp=request.email_otp or "",
            purpose="registration",
        )
        if not verified:
            raise AuthenticationError("Invalid OTP")

        photographer.phone_verified = True
        photographer.email_verified = True
        await self.db.flush()

        if not photographer.is_active:
            raise AuthenticationError("Account not found or inactive")

        return await self._build_token_response(photographer)

    async def _verify_login_otp(self, request: VerifyOTPRequest) -> TokenResponse:
        """Consume the email login OTP and issue tokens."""
        email = str(request.email).lower()
        photographer = await self._get_photographer_by_identifier(email)
        if photographer is None:
            raise NotFoundError("Account")
        if not photographer.phone_verified:
            raise PhoneNotVerifiedError()
        if not photographer.is_active:
            raise AuthenticationError("Account not found or inactive")

        verified = await self.otp_service.verify_otp(email, "login", request.otp or "")
        if not verified:
            raise AuthenticationError("Invalid OTP")

        photographer.email_verified = True
        await self.db.flush()
        return await self._build_token_response(photographer)

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
