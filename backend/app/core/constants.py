"""Shared constants that must not be scattered as magic strings or numbers."""

from __future__ import annotations

from enum import Enum

OTP_LENGTH = 6
"""Numeric OTP length shown to users and stored in Redis."""

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 16
PASSWORD_PATTERN = (
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9])"
    rf".{{{PASSWORD_MIN_LENGTH},{PASSWORD_MAX_LENGTH}}}$"
)
"""Password must include upper, lower, digit, special char, and be 8-16 chars."""

INDIAN_PHONE_PATTERN = r"^\+91\d{10}$"
INDIAN_E164_PREFIX = "+91"
INDIAN_MOBILE_DIGIT_COUNT = 10

SMS_PROVIDER_LOG = "log"
SMS_PROVIDER_FAST2SMS = "fast2sms"
FAST2SMS_BULK_URL = "https://www.fast2sms.com/dev/bulkV2"
FAST2SMS_OTP_ROUTE = "otp"
FAST2SMS_QUICK_ROUTE = "q"
FAST2SMS_HTTP_TIMEOUT_SECONDS = 30.0
# OTP route often needs KYC (996) or is blocked (998/408); retry Quick SMS.
FAST2SMS_OTP_FALLBACK_STATUS_CODES = frozenset({408, 996, 998})
OTP_SMS_BODY_TEMPLATE = "Your verification code is: {otp}"

OTP_CHANNEL_SMS = "sms"
OTP_CHANNEL_EMAIL = "email"

EMAIL_PROVIDER_NONE = "none"
EMAIL_PROVIDER_LOG = "log"
EMAIL_PROVIDER_SMTP = "smtp"
SMTP_HTTP_TIMEOUT_SECONDS = 30.0

REQUEST_ID_HEADER = "X-Request-ID"
"""HTTP header used to correlate logs for a single request."""

MAX_INCOMING_REQUEST_ID_LENGTH = 128
"""Reject oversized client-supplied request IDs to avoid log abuse."""


class JWTType(str, Enum):
    """JWT `type` claim values used across photographer, guest, and couple auth."""

    ACCESS = "access"
    REFRESH = "refresh"
    GUEST = "guest"
    COUPLE = "couple"
