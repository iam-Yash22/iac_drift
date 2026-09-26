"""User management endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.auth import rbac
from app.core.constants import Role
from app.models.user import User
from app.schemas import user as user_schema
from app.services import user_service
from app.services.audit_log_service import record_admin_action
from app.models.account import AwsAccount
from app.models.report import Report
from app.models.scan import Scan

router = APIRouter(prefix="/users", tags=["users"])


def _count_admin_users(db: deps.Session) -> int:
    return db.query(User).filter(User.role == Role.ADMIN.value).count()


@router.get("", response_model=List[user_schema.UserRead])
def list_users(
    admin_user: object = Depends(rbac.require_role("admin")),
    db: deps.Session = Depends(deps.get_db),
) -> List[user_schema.UserRead]:
    """List all users."""
    return user_service.list_users(db)


@router.post("", response_model=user_schema.UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: user_schema.UserCreate,
    admin_user: object = Depends(rbac.require_role("admin")),
    db: deps.Session = Depends(deps.get_db),
) -> user_schema.UserRead:
    """Create a user as an administrator."""
    created = await user_service.register_user(db, user_in)
    record_admin_action(
        actor_id=getattr(admin_user, "id", None),
        action="user.created",
        target_type="user",
        target_id=created.id,
        details={"username": created.username, "role": created.role},
    )
    return created


@router.patch("/{user_id}", response_model=user_schema.UserRead)
def update_user(
    user_id: int,
    user_in: user_schema.UserUpdate,
    admin_user: object = Depends(rbac.require_role("admin")),
    db: deps.Session = Depends(deps.get_db),
) -> user_schema.UserRead:
    """Update an existing user."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user and target_user.role == Role.ADMIN.value and user_in.role is not None and user_in.role != Role.ADMIN.value:
        if _count_admin_users(db) <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot demote the last remaining admin")

    updated = user_service.update_user(db, user_id, user_in)
    record_admin_action(
        actor_id=getattr(admin_user, "id", None),
        action="user.updated",
        target_type="user",
        target_id=user_id,
        details={"fields": list(user_in.model_dump(exclude_unset=True).keys())},
    )
    return updated


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin_user: object = Depends(rbac.require_role("admin")),
    db: deps.Session = Depends(deps.get_db),
) -> None:
    """Delete an existing user."""
    if user_id == getattr(admin_user, "id", None):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrators cannot delete themselves")

    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user and target_user.role == Role.ADMIN.value and _count_admin_users(db) <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete the last remaining admin")

    db.query(AwsAccount).filter(AwsAccount.owner_id == user_id).update({AwsAccount.owner_id: None}, synchronize_session=False)
    db.query(Report).filter(Report.generated_by_id == user_id).update({Report.generated_by_id: None}, synchronize_session=False)
    db.query(Scan).filter(Scan.triggered_by_id == user_id).update({Scan.triggered_by_id: None}, synchronize_session=False)
    user_service.delete_user(db, user_id)
    record_admin_action(
        actor_id=getattr(admin_user, "id", None),
        action="user.deleted",
        target_type="user",
        target_id=user_id,
    )
