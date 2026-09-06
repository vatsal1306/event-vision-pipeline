"""HTTP exception handlers that emit the platform error JSON shape."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger()

INTERNAL_ERROR_DETAIL = "Internal server error"
INTERNAL_ERROR_CODE = "INTERNAL_ERROR"


def _validation_errors(exc: RequestValidationError) -> list[dict[str, str]]:
    """Flatten Pydantic/Starlette validation errors into field/message pairs."""
    errors: list[dict[str, str]] = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = ".".join(str(part) for part in location)
        errors.append({"field": field, "message": str(error.get("msg", "Invalid value"))})
    return errors


async def app_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Serialize domain exceptions to ``detail`` + ``code``."""
    if not isinstance(exc, AppException):
        raise TypeError(f"Expected AppException, got {type(exc).__name__}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


async def validation_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Return 422 with per-field errors for invalid JSON or schema mismatches."""
    if not isinstance(exc, RequestValidationError):
        raise TypeError(f"Expected RequestValidationError, got {type(exc).__name__}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "code": "VALIDATION_ERROR",
            "errors": _validation_errors(exc),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Hide internal crash details from clients while logging the real error."""
    logger.exception(
        "http.unhandled_exception",
        method=request.method,
        path=request.url.path,
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": INTERNAL_ERROR_DETAIL, "code": INTERNAL_ERROR_CODE},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global handlers used by every route.

    Args:
        app: FastAPI application instance.
    """
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
