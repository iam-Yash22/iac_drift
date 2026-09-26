"""Authentication token response and JWT payload schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

__all__ = ["Token", "TokenPayload"]


class Token(BaseModel):
    """Login response payload returned after successful authentication."""

    access_token: str = Field(..., description="JWT access token string.")
    token_type: str = Field(default="bearer", description="Authentication scheme for the token.")
    expires_in: int | None = Field(default=None, description="Token lifetime in seconds, if provided.")


class TokenPayload(BaseModel):
    """JWT claim set decoded from an access token."""

    sub: str | UUID = Field(..., description="Subject identifier tied to the authenticated principal.")
    exp: int | None = Field(default=None, description="Expiration time as a Unix timestamp.")
    iat: int | None = Field(default=None, description="Issued-at time as a Unix timestamp.")
    nbf: int | None = Field(default=None, description="Not-before time as a Unix timestamp.")
    iss: str | None = Field(default=None, description="Token issuer identifier.")
    aud: str | list[str] | None = Field(default=None, description="Audience or audiences for the token.")
    jti: str | UUID | None = Field(default=None, description="Unique token identifier.")
    type: str | None = Field(default=None, description="JWT token type or grant classification.")
    scopes: list[str] | None = Field(default=None, description="Granted permission scopes, when present.")
    raw_claims: dict[str, Any] | None = Field(default=None, description="Original unvalidated claim payload.")
