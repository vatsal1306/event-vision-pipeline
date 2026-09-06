"""Custom exception hierarchy."""

from __future__ import annotations


class AppException(Exception):  # noqa: N818
    """Base application exception."""

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found", "NOT_FOUND", 404)


class AuthenticationError(AppException):
    """Authentication failed (invalid credentials, expired token)."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, "AUTH_FAILED", 401)


class AuthorizationError(AppException):
    """User lacks permissions for this action."""

    def __init__(self, message: str = "Not authorized") -> None:
        super().__init__(message, "FORBIDDEN", 403)


class OTPCooldownError(AppException):
    """OTP request rate limited."""

    def __init__(self, message: str = "Please wait before requesting a new OTP") -> None:
        super().__init__(message, "OTP_COOLDOWN", 429)


class OTPMaxAttemptsError(AppException):
    """Too many failed OTP verification attempts."""

    def __init__(self, message: str = "Too many attempts") -> None:
        super().__init__(message, "OTP_MAX_ATTEMPTS", 429)


class StorageLimitError(AppException):
    """Photographer's storage quota exceeded."""

    def __init__(self) -> None:
        super().__init__("Storage limit exceeded", "STORAGE_LIMIT", 402)


class ProcessingError(AppException):
    """Background processing failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "PROCESSING_ERROR", 500)
