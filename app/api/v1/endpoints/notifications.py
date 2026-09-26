"""Notification endpoints for user-triggered scan activity."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.core.constants import Role
from app.models.account import AwsAccount
from app.models.scan import Scan
from app.models.user import User
from app.schemas.notification import ScanNotification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[ScanNotification])
def list_notifications(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
) -> list[ScanNotification]:
    """Return recent scans triggered by non-admin users."""
    rows = (
        db.query(Scan, AwsAccount, User)
        .join(AwsAccount, Scan.account_id == AwsAccount.id)
        .join(User, Scan.triggered_by_id == User.id)
        .filter(User.role != Role.ADMIN.value)
        .order_by(Scan.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        ScanNotification(
            scan_id=scan.scan_id,
            account_id=scan.account_id,
            account_name=account.name,
            status=scan.status,
            triggered_by_username=user.username,
            triggered_by_email=user.email,
            triggered_at=scan.created_at,
        )
        for scan, account, user in rows
    ]
