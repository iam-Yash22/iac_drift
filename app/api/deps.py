"""Central API dependency injection helpers."""

from typing import Optional, Union

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.auth import dependencies as auth_dependencies
from app.crud.crud_account import crud_account
from app.models.account import AwsAccount
from app.services import aws_client_factory
from app.utils.exceptions import UnauthorizedError, ValidationError


def _resolve_account_by_identifier(db: Session, account_id: Union[str, int]) -> Optional[AwsAccount]:
    """Resolve an account using either its database id or its AWS account id."""
    if account_id is None:
        return None

    value = str(account_id).strip()
    if not value:
        return None

    account = db.query(AwsAccount).filter(AwsAccount.account_id == value).first()
    if account is not None:
        return account

    try:
        numeric_account_id = int(value)
    except (TypeError, ValueError):
        return None

    return crud_account.get(db, id=numeric_account_id)


def get_db() -> Session:
    """Provide a database session for the duration of a request."""
    db = db_session.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(current_user: object = Depends(auth_dependencies.get_current_user)) -> object:
    """Resolve the authenticated user via FastAPI dependency injection."""
    return current_user


def _require_aws_access(account: Optional[AwsAccount]) -> Optional[AwsAccount]:
    """Verify the linked AWS role can be assumed before granting access to account-scoped APIs."""
    if account is None:
        return None

    role_arn = getattr(account, "role_arn", None)
    if not role_arn:
        raise UnauthorizedError(
            "AWS authorization failed for this account. Missing role_arn on the account record.",
            detail={"account_id": getattr(account, "id", None)},
        )

    try:
        aws_client_factory.assume_role(
            role_arn=role_arn,
            external_id=getattr(account, "external_id", None),
        )
    except Exception as exc:
        raw_message = getattr(exc, "detail", None) or str(exc)
        raise UnauthorizedError(
            str(raw_message),
            detail=raw_message,
        ) from exc

    return account


def get_account(
    account_id: Optional[Union[str, int]] = Query(default=None),
    current_user: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Optional[AwsAccount]:
    """Resolve and authorize an explicitly requested account before a handler runs."""
    if account_id is None:
        return None

    account = _resolve_account_by_identifier(db, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    return account


def get_monitored_account(
    account_id: Union[str, int],
    current_user: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Optional[AwsAccount]:
    """Resolve a monitored account for any authenticated user."""
    if account_id == 0 or (isinstance(account_id, str) and account_id.strip() == "0"):
        return None

    account = _resolve_account_by_identifier(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    return account


def require_admin(current_user: object = Depends(get_current_user)) -> object:
    """Require the authenticated user to have the admin role."""
    role = getattr(current_user, "role", None)
    role_value = role.value if hasattr(role, "value") else str(role)
    if role_value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )
    return current_user


# Compatibility aliases for callers migrating from ownership-based access.
get_owned_account = get_monitored_account
get_required_account = get_monitored_account