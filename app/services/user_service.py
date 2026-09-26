import inspect
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

import app.crud.crud_user as crud_user
import app.security.hashing as hashing
import app.security.jwt as jwt
import app.schemas.user as user_schemas
import app.schemas.token as token_schemas
import app.utils.exceptions as exceptions


async def _maybe_await(value: Any) -> Any:
    """Await value if it's awaitable, otherwise return it directly."""
    if inspect.isawaitable(value):
        return await value
    return value


async def register_user(db: Session, user_in: user_schemas.UserCreate) -> Any:
    """Create a new user: ensure uniqueness, hash password, persist via CRUD.

    Returns the created user object from the CRUD layer.
    Raises a conflict-style exception if the email is already registered.
    """
    existing = await _maybe_await(
        crud_user.crud_user.get_by_login(db, login=user_in.username)
    )
    if existing is None:
        existing = await _maybe_await(
            crud_user.crud_user.get_by_login(db, login=str(user_in.email))
        )
    if existing:
        raise exceptions.ConflictError("A user with this email already exists")

    # Hash password (support sync or async hashers)
    created = await _maybe_await(crud_user.crud_user.create(db, obj_in=user_in))
    return created


def list_users(db: Session) -> list[Any]:
    return crud_user.crud_user.get_multi(db)


def update_user(db: Session, user_id: int, user_in: user_schemas.UserUpdate) -> Any:
    user = crud_user.crud_user.get(db, user_id)
    if user is None:
        raise exceptions.NotFoundError("User not found")
    return crud_user.crud_user.update(db, db_obj=user, obj_in=user_in)


def delete_user(db: Session, user_id: int) -> None:
    if crud_user.crud_user.remove(db, id=user_id) is None:
        raise exceptions.NotFoundError("User not found")


async def create_tokens_for_user(user: Any) -> token_schemas.Token:
    """Issue JWT tokens for a given user object. Returns a Token schema.

    The function uses the `security.jwt` helpers and supports sync/async
    token creation implementations.
    """
    sub = str(getattr(user, "id", getattr(user, "pk", "")))
    if not sub:
        # fallback to email if no id present
        sub = str(getattr(user, "email", ""))

    access = await _maybe_await(jwt.create_access_token({"sub": sub}))
    refresh = None
    # create_refresh_token might not exist in all projects
    if hasattr(jwt, "create_refresh_token"):
        refresh = await _maybe_await(jwt.create_refresh_token({"sub": sub}))

    token_payload = {"access_token": access, "token_type": "bearer"}
    if refresh is not None:
        token_payload["refresh_token"] = refresh

    # Construct token schema if available, otherwise return raw dict
    try:
        return token_schemas.Token(**token_payload)
    except Exception:
        return token_payload  # type: ignore


async def authenticate_user(db: Session, login: str, password: str) -> Tuple[Any, Any]:
    """Validate credentials and return (user, token).

    Raises an unauthorized-style exception on bad credentials.
    """
    user = await _maybe_await(crud_user.crud_user.get_by_login(db, login=login))
    if not user:
        raise exceptions.UnauthorizedError("Invalid credentials")

    valid = await _maybe_await(
        hashing.verify_password(password, getattr(user, "hashed_password", ""))
    )
    if not valid:
        raise exceptions.UnauthorizedError("Invalid credentials")

    token = await create_tokens_for_user(user)
    return user, token
