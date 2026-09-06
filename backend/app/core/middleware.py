"""Cross-cutting middleware (Request ID, Logging, CORS)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.responses import Response

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for injecting Request ID and logging HTTP access."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request and log timing/status."""
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                elapsed_ms=round(elapsed_ms, 2),
            )

        response.headers["X-Request-ID"] = request_id
        return response
