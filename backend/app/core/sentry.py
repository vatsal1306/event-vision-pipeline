"""Optional Sentry initialization."""

from __future__ import annotations

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import Settings


def init_sentry(settings: Settings) -> None:
    """Initialize Sentry when a DSN is configured; otherwise do nothing.

    Args:
        settings: Application settings. Empty ``sentry_dsn`` skips init.
    """
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        send_default_pii=False,
        traces_sample_rate=0.0,
    )
