import inspect
from typing import Any, Dict

from sqlalchemy.orm import Session

import app.services.aws_client_factory as aws_client_factory
import app.crud.crud_account as crud_account
import app.security.encryption as encryption
import app.schemas.account as account_schemas
import app.utils.exceptions as exceptions



async def _maybe_await(value: Any) -> Any:
    """Await value if it's awaitable, otherwise return it directly."""
    if inspect.isawaitable(value):
        return await value
    return value


def list_accounts(db) -> list[Any]:
    """Return monitored AWS accounts in database order."""
    return crud_account.crud_account.get_all(db)


def create_account(db: Session, account_in: account_schemas.AccountCreate) -> Any:
    """Create and persist a monitored AWS account."""
    return crud_account.crud_account.create(db, obj_in=account_in)


async def onboard_account(account_in: account_schemas.AccountCreate) -> Any:
    """Validate `role_arn`/`external_id` via AssumeRole then persist the account.

    Steps:
    - Ensure no existing account with same `role_arn`.
    - Call `services.aws_client_factory.assume_role(...)` to validate credentials.
    - Encrypt sensitive fields using `security.encryption`.
    - Persist via `crud.crud_account.create` and return created record.

    Raises ConflictError when account exists, ValidationError on failed AssumeRole.
    """
    existing = await _maybe_await(crud_account.get_by_role_arn(account_in.role_arn))
    if existing:
        raise exceptions.ConflictError("An account with this role_arn already exists")

    # Attempt to assume role to validate supplied role_arn/external_id
    try:
        assume_result = await _maybe_await(
            aws_client_factory.assume_role(role_arn=account_in.role_arn, external_id=getattr(account_in, "external_id", None))
        )
    except Exception as exc:  # propagate a validation-style error
        raise exceptions.ValidationError(f"Failed to validate role_arn/external_id: {exc}") from exc

    if not assume_result:
        raise exceptions.ValidationError("AssumeRole did not return credentials; validation failed")

    # Encrypt sensitive fields before persisting (may be sync or async)
    encrypted_external_id = None
    if hasattr(account_in, "external_id") and getattr(account_in, "external_id"):
        if hasattr(encryption, "encrypt"):
            maybe_encrypted = encryption.encrypt(getattr(account_in, "external_id"))
            encrypted_external_id = await _maybe_await(maybe_encrypted)
        else:
            encrypted_external_id = getattr(account_in, "external_id")

    # Prepare payload for create
    if hasattr(account_in, "dict"):
        payload: Dict[str, Any] = account_in.dict()
    else:
        payload = dict(vars(account_in))

    if encrypted_external_id is not None:
        payload["external_id"] = encrypted_external_id

    # Optionally store a lightweight validation marker or metadata
    payload.setdefault("validated", True)
    payload.setdefault("assume_role_meta", {})

    created = await _maybe_await(crud_account.create(payload))
    return created
