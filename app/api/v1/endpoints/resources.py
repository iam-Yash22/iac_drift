"""Resource listing endpoints backed by accounts database."""

from typing import List

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.schemas import resource as resource_schema
from app.services import dashboard_service

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("", response_model=List[resource_schema.ResourceOut])
def list_resources(
    account=Depends(deps.get_account),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: resource_schema.ResourceOut = Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> List[resource_schema.ResourceOut]:
    """List tracked resources from accounts database for the current user's account."""
    resolved_account_id = account.id if account is not None else dashboard_service._resolve_account_id(db, current_user=current_user)
    return dashboard_service.list_resources(
        db,
        current_user=current_user,
        account_id=resolved_account_id,
        page=page,
        per_page=per_page,
    )
