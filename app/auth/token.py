"""Refresh-token decoding helpers."""

from typing import Any

from app.security import jwt


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode a refresh token and raise when its payload is invalid."""
    payload = jwt.decode_token(token)
    if not isinstance(payload, dict):
        raise ValueError("Invalid refresh token")
    return payload
