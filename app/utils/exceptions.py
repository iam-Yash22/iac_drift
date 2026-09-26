"""Application exception hierarchy.

Domain and service layers raise these exceptions; ``app.exception_handlers``
maps them to standardized JSON HTTP responses.
"""

from __future__ import annotations

from typing import Any, ClassVar

__all__ = [
    "AppException",
    "BadRequestError",
    "ConflictError",
    "ForbiddenError",
    "InternalServerError",
    "NotFoundError",
    "ServiceError",
    "ServiceUnavailableError",
    "UnauthorizedError",
    "ValidationError",
]


class AppException(Exception):
    """Base class for application errors with HTTP semantics."""

    default_code: ClassVar[str] = "application_error"
    default_status_code: ClassVar[int] = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        detail: Any | None = None,
    ) -> None:
        self.message = message
        self.code = code or self.default_code
        self.status_code = status_code or self.default_status_code
        self.detail = detail
        super().__init__(message)


class BadRequestError(AppException):
    default_code = "bad_request"
    default_status_code = 400


class UnauthorizedError(AppException):
    default_code = "unauthorized"
    default_status_code = 401


class ForbiddenError(AppException):
    default_code = "forbidden"
    default_status_code = 403


class NotFoundError(AppException):
    default_code = "not_found"
    default_status_code = 404


class ConflictError(AppException):
    default_code = "conflict"
    default_status_code = 409


class ValidationError(AppException):
    default_code = "validation_error"
    default_status_code = 422


class ServiceError(AppException):
    default_code = "service_error"
    default_status_code = 500


class ServiceUnavailableError(AppException):
    default_code = "service_unavailable"
    default_status_code = 503


class InternalServerError(AppException):
    default_code = "internal_error"
    default_status_code = 500
