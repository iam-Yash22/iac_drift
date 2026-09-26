"""Authentication token helpers used by the API endpoints."""

from datetime import timedelta
from typing import Any

from app.security import jwt


def create_access_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    """Create an access token for a username or subject payload."""
    payload = subject if isinstance(subject, dict) else {"sub": str(subject)}
    return jwt.create_access_token(payload, expires_delta=expires_delta)


def create_refresh_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    """Create a refresh token using the same signed JWT mechanism."""
    payload = subject if isinstance(subject, dict) else {"sub": str(subject)}
    return jwt.create_access_token(payload, expires_delta=expires_delta)
