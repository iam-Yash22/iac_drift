"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api import deps
from app.auth import auth as auth_service
from app.auth import token as auth_token
from app.schemas import token as token_schema
from app.schemas import user as user_schema
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=token_schema.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(deps.get_db),
) -> token_schema.Token:
    """Authenticate a user and return JWT access and refresh tokens."""
    _, tokens = await user_service.authenticate_user(
        db,
        form_data.username,
        form_data.password,
    )
    return tokens


@router.get("/me", response_model=user_schema.UserRead)
def current_user(current_user: object = Depends(deps.get_current_user)) -> user_schema.UserRead:
    """Return the authenticated user's safe profile and role."""
    return current_user


@router.post("/refresh", response_model=token_schema.Token)
def refresh_token(refresh_token: str) -> token_schema.Token:
    """Refresh an access token using a valid refresh token."""
    payload = auth_token.decode_refresh_token(refresh_token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    access_token = auth_service.create_access_token(username)
    new_refresh_token = auth_service.create_refresh_token(username)
    return token_schema.Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )
