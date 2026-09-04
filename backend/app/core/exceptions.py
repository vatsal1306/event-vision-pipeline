"""Domain exception hierarchy mapped to stable HTTP status codes and error codes."""

from __future__ import annotations


class AppException(Exception):
    """Base application exception converted to JSON by the global handler.

    Args:
        message: Human-readable error shown to API clients.
        code: Stable machine-readable code (e.g. ``NOT_FOUND``).
        status_code: HTTP status to return.
    """

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppException):
    """Raised when a named resource does not exist."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found", "NOT_FOUND", 404)


class AuthenticationError(AppException):
    """Raised when credentials or tokens are missing or invalid."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, "AUTH_FAILED", 401)


class AuthorizationError(AppException):
    """Raised when the caller is authenticated but not allowed."""

    def __init__(self, message: str = "Not authorized") -> None:
        super().__init__(message, "FORBIDDEN", 403)


class OTPCooldownError(AppException):
    """Raised when another OTP is requested too soon."""

    def __init__(self, message: str = "Please wait before requesting a new OTP") -> None:
        super().__init__(message, "OTP_COOLDOWN", 429)


class OTPMaxAttemptsError(AppException):
    """Raised when OTP verification attempts are exhausted."""

    def __init__(self, message: str = "Too many attempts") -> None:
        super().__init__(message, "OTP_MAX_ATTEMPTS", 429)


class StorageLimitError(AppException):
    """Raised when a photographer exceeds their storage quota."""

    def __init__(self) -> None:
        super().__init__("Storage limit exceeded", "STORAGE_LIMIT", 402)


class ProcessingError(AppException):
    """Raised when photo or ML processing fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "PROCESSING_ERROR", 500)
