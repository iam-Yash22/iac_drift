"""Global exception handler registration.

Registers ``@app.exception_handler`` callbacks that translate
``utils.exceptions.*`` (and framework errors) into standardized JSON
responses via ``schemas.msg``.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.core.logging_config import get_logger
from app.schemas.msg import build_error_response
from app.utils.exceptions import AppException, InternalServerError

__all__ = ["register_exception_handlers"]

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    """Return the request identifier when request-ID middleware is active."""
    return getattr(request.state, "request_id", None)


def _http_error_message(detail: Any) -> tuple[str, Any | None]:
    """Normalize Starlette HTTPException detail into message and detail fields."""
    if isinstance(detail, str):
        return detail, None
    return "Request failed", detail


async def _app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    log_extra = {
        "code": exc.code,
        "status_code": exc.status_code,
        "request_id": _request_id(request),
        "detail": exc.detail,
    }
    if exc.status_code >= 500:
        logger.error(exc.message, extra=log_extra)
    else:
        logger.warning(exc.message, extra=log_extra)

    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            code=exc.code,
            message=exc.message,
            detail=exc.detail,
            request_id=_request_id(request),
        ),
    )


async def _http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    message, detail = _http_error_message(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(
            code="http_error",
            message=message,
            detail=detail,
            request_id=_request_id(request),
        ),
    )


async def _validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=build_error_response(
            code="validation_error",
            message="Request validation failed",
            detail=exc.errors(),
            request_id=_request_id(request),
        ),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    internal = InternalServerError("Internal server error")
    
    # Add more context for common runtime errors
    exc_context = {
        "code": internal.code,
        "request_id": _request_id(request),
        "exception_type": exc.__class__.__name__,
        "exception_message": str(exc),
    }
    
    # Special handling for AttributeError (often from None defaults in dependencies)
    if isinstance(exc, AttributeError):
        logger.error(
            f"AttributeError: {exc}. This may indicate a missing or None dependency injection.",
            extra=exc_context,
            exc_info=True
        )
    else:
        logger.exception(
            "unhandled exception",
            extra=exc_context,
        )
    
    return JSONResponse(
        status_code=internal.status_code,
        content=build_error_response(
            code=internal.code,
            message=internal.message,
            request_id=_request_id(request),
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-wide exception handlers."""
    app.add_exception_handler(AppException, _app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
