"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import router as v1_router
from app.config import Settings, get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.sentry import init_sentry


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    """Allow any origin in debug; lock CORS to the frontend URL otherwise.

    ``allow_credentials`` cannot be combined with origin ``*``, so credentials
    are enabled only when a specific frontend origin is used.
    """
    if settings.debug:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings)
    init_sentry(settings)

    app = FastAPI(
        title=settings.app_name,
        debug=False,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    _configure_cors(app, settings)
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()
