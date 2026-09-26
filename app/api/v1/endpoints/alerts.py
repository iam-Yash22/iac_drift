"""Alert rule management endpoints backed by accounts database."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.api import deps
from app.auth import rbac
from app.schemas import alert as alert_schema
from app.services import alert_dispatch_service, dashboard_service

router = APIRouter(prefix="/alerts/rules", tags=["alerts"])


@router.get("", response_model=List[alert_schema.AlertRuleOut])
def list_rules(
    account_id: Optional[int] = Query(default=None),
    current_user: alert_schema.AlertRuleOut = Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> List[alert_schema.AlertRuleOut]:
    """List configured alert rules scoped to user's account from accounts database."""
    # Resolve account ID for scoping
    resolved_account_id = dashboard_service._resolve_account_id(
        db,
        current_user=current_user,
        account_id=account_id,
    )
    return alert_dispatch_service.list_rules(db, account_id=resolved_account_id)


@router.post("", response_model=alert_schema.AlertRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    rule_in: alert_schema.AlertRuleCreate,
    account_id: Optional[int] = Query(default=None),
    current_user: alert_schema.AlertRuleOut = Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> alert_schema.AlertRuleOut:
    """Create a new alert rule for the user's account in accounts database."""
    resolved_account_id = dashboard_service._resolve_account_id(
        db,
        current_user=current_user,
        account_id=account_id,
    )
    return alert_dispatch_service.create_rule(db, rule_in, account_id=resolved_account_id)


@router.patch("/{rule_id}", response_model=alert_schema.AlertRuleOut)
def update_rule(
    rule_id: int,
    rule_in: alert_schema.AlertRuleUpdate,
    current_user: alert_schema.AlertRuleOut = Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> alert_schema.AlertRuleOut:
    """Update an existing alert rule."""
    return alert_dispatch_service.update_rule(db, rule_id, rule_in, current_user=current_user)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    current_user: alert_schema.AlertRuleOut = Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> None:
    """Delete an existing alert rule."""
    alert_dispatch_service.delete_rule(db, rule_id, current_user=current_user)
