"""Generic message and error detail response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

__all__ = ["Msg", "ErrorDetail", "build_error_response"]


class Msg(BaseModel):
    """Generic acknowledgement or status message envelope."""

    message: str = Field(..., description="Human-readable status or acknowledgement message.")
    ok: bool = Field(default=True, description="Indicates whether the operation succeeded.")


class ErrorDetail(BaseModel):
    """Structured error detail used within error responses."""

    code: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable error summary.")
    detail: Any | None = Field(default=None, description="Optional structured error detail.")
    request_id: str | None = Field(default=None, description="Correlating request identifier.")


def build_error_response(
    *,
    code: str,
    message: str,
    detail: Any | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a JSON-compatible standardized error response."""
    return ErrorDetail(
        code=code,
        message=message,
        detail=detail,
        request_id=request_id,
    ).model_dump(mode="json")
