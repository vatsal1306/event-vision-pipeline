"""FastAPI application factory.

Creates and configures the ASGI application with middleware,
routers, and lifecycle events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.router import router as v1_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handle application startup and shutdown events.

    Startup: initialise connections, verify services.
    Shutdown: close connections, flush logs.
    """
    logger.info("application_startup")
    yield
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    OpenAPI docs are only exposed when ``DEBUG`` is ``True``
    (checked via the ``DEBUG`` environment variable).
    """
    import os

    is_debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    app = FastAPI(
        title="AI Photo Sharing Platform",
        description="AI-powered event photo delivery platform for professional photographers.",
        version="0.1.0",
        docs_url="/docs" if is_debug else None,
        redoc_url="/redoc" if is_debug else None,
        openapi_url="/openapi.json" if is_debug else None,
        lifespan=lifespan,
    )

    # ── Routers ──────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(v1_router)

    return app


# Module-level app instance for ``uvicorn app.main:app``
app = create_app()
