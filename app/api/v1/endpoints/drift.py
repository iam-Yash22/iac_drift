"""Drift monitoring endpoints."""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api import deps
from app.schemas import drift as drift_schema
from app.services import drift_orchestrator

router = APIRouter(prefix="/drift", tags=["drift"])


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
def trigger_scan_request(
    background_tasks: BackgroundTasks,
    account_id: Optional[int] = Query(default=None, ge=1),
    current_user: drift_schema.DriftRecord = Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> dict[str, str]:
    """Queue an account scan or an active-account fleet scan without blocking."""
    try:
        if account_id is None:
            fleet_result = drift_orchestrator.trigger_fleet_scan(
                background_tasks,
                db,
                triggered_by_id=getattr(current_user, "id", None),
            )
            return fleet_result
        drift_orchestrator.trigger_account_scan(
            background_tasks,
            db,
            account_id,
            triggered_by_id=getattr(current_user, "id", None),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="scan already in progress for this account",
        ) from exc
    return {"status": "accepted"}


@router.post("/scan/{account_id}", status_code=status.HTTP_202_ACCEPTED)
def trigger_scan(
    account_id: int,
    background_tasks: BackgroundTasks,
    current_user: drift_schema.DriftRecord = Depends(deps.get_current_user),
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> dict[str, str]:
    """Trigger a drift scan for a single account or a fleet-wide run."""
    try:
        if account_id == 0:
            fleet_result = drift_orchestrator.trigger_fleet_scan(
                background_tasks,
                db,
                triggered_by_id=getattr(current_user, "id", None),
            )
            return fleet_result
        validated_account_id = getattr(account, "id", account_id)
        drift_orchestrator.trigger_account_scan(
            background_tasks,
            db,
            validated_account_id,
            triggered_by_id=getattr(current_user, "id", None),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="scan already in progress for this account",
        ) from exc
    return {"status": "accepted"}


@router.get("", response_model=List[drift_schema.DriftRecord])
def list_drift(
    account=Depends(deps.get_account),
    requested_account_id: Optional[int] = Query(default=None, alias="account_id", ge=1),
    current_user: drift_schema.DriftRecord = Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> List[drift_schema.DriftRecord]:
    """List drift records from accounts database. Scoped to user's account unless admin."""
    from app.services import dashboard_service

    # For non-admin users, scope to their registered account
    role = getattr(current_user, "role", None)
    role_value = role.value if hasattr(role, "value") else str(role)
    if account is not None:
        resolved_account_id = account.id
    elif role_value != "admin":
        resolved_account_id = dashboard_service._resolve_account_id(
            db,
            current_user=current_user,
            account_id=requested_account_id,
        )
    else:
        # Admin can see all or filter by account_id
        resolved_account_id = requested_account_id

    return drift_orchestrator.list_drift(db, account_id=resolved_account_id)
