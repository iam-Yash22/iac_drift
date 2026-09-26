"""Authentication dependencies for FastAPI route handlers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.oauth2 import oauth2_scheme
from app.crud.crud_user import crud_user
from app.db.session import get_db
from app.schemas.token import TokenPayload
from app.schemas.user import UserRead
from app.security import jwt, rate_limiter


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> UserRead:
    """Extract and validate JWT token from authorization header and fetch user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode_token(token)
        token_data = TokenPayload(**payload) if isinstance(payload, dict) else payload
        if token_data.sub is None:
            raise credentials_exception
        user_id = token_data.sub
    except Exception:
        raise credentials_exception

    user = crud_user.get(db, id=int(user_id))
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(
    current_user: UserRead = Depends(get_current_user),
) -> UserRead:
    """Return the authenticated user; role controls authorization."""
    return current_user
