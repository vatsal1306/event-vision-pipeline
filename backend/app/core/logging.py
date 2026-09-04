"""Structured logging setup with secret redaction."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from app.config import Settings

SENSITIVE_FIELD_NAMES = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "secret_key",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "otp",
        "otp_code",
        "sms_api_key",
        "aws_secret_access_key",
        "aws_access_key_id",
    }
)
REDACTED_VALUE = "***REDACTED***"


def _is_sensitive_key(key: str) -> bool:
    """Return True if a log field name looks like a secret."""
    normalized = key.lower().replace("-", "_")
    if normalized in SENSITIVE_FIELD_NAMES:
        return True
    return any(part in normalized for part in ("password", "otp", "token", "secret"))


def _redact(value: Any) -> Any:
    """Recursively redact sensitive keys inside nested mappings and sequences."""
    if isinstance(value, MutableMapping):
        return {
            k: REDACTED_VALUE if _is_sensitive_key(str(k)) else _redact(v) for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


def redact_sensitive_data(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Structlog processor that strips passwords, OTP codes, and tokens from events."""
    redacted = _redact(event_dict)
    if isinstance(redacted, dict):
        return redacted
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure structlog for console (debug) or JSON (non-debug) output.

    Args:
        settings: Application settings controlling renderer choice.
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.debug:
        processors: list[Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(),
        ]
    else:
        processors = [*shared_processors, structlog.processors.JSONRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger() -> Any:
    """Return the process-wide structured logger."""
    return structlog.get_logger()
