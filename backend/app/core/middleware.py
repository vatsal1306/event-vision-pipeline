"""HTTP middleware for request IDs, timing, and access logs."""

from __future__ import annotations

import time
from uuid import uuid4

import structlog
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.constants import MAX_INCOMING_REQUEST_ID_LENGTH, REQUEST_ID_HEADER
from app.core.logging import get_logger


def resolve_request_id(request: Request) -> str:
    """Reuse a valid incoming request ID or generate a new UUID.

    Args:
        request: Incoming HTTP request.

    Returns:
        Request ID written to logs and the response header.
    """
    incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if incoming and len(incoming) <= MAX_INCOMING_REQUEST_ID_LENGTH and incoming.isprintable():
        return incoming
    return str(uuid4())


class RequestContextMiddleware:
    """ASGI middleware: bind ``request_id``, time the request, emit an access log."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process one ASGI connection.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        request_id = resolve_request_id(request)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start_time = time.perf_counter()
        logger = get_logger()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                elapsed_ms=elapsed_ms,
            )
            structlog.contextvars.clear_contextvars()
