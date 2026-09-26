from datetime import datetime, timezone
"""Account management endpoints."""

import json
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func

from app.api import deps
from app.auth import rbac
from app.core.constants import Role
from app.schemas import account as account_schema
from app.services import account_service, drift_orchestrator
from app.services.audit_log_service import record_admin_action
from app.crud import crud_account
from sqlalchemy.exc import IntegrityError

from app.models.scan import Scan
from app.schemas.scan import ScanOut
from app.models.resource import Resource
from app.models.alert import Alert
from app.models.alert import AlertNotification, AlertRule
from app.models.drift import DriftRecord
from app.models.report import Report
from app.models.terraform_baseline import TerraformBaseline
from app.schemas.resource import ResourceOut
from app.schemas.alert import AlertOut
from app.services import dashboard_service, alert_dispatch_service
from app.services import report_service
from app.schemas.report import AccountReportOut, ReportOut, ReportCreate
from app.schemas.dashboard import DashboardOut
from app.parsers import normalizer
from app.crud.crud_resource import crud_resource

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=List[account_schema.AccountOut])
def list_accounts(
    current_user=Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> List[account_schema.AccountOut]:
    """List monitored accounts for authenticated dashboard access."""
    return account_service.list_accounts(db)


@router.post("", response_model=account_schema.AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    account_in: account_schema.AccountCreate,
    current_user: account_schema.AccountOut = Depends(deps.require_admin),
    db: deps.Session = Depends(deps.get_db),
) -> account_schema.AccountOut:
    """Create a new monitored account and validate it through the service layer."""
    created = account_service.create_account(db, account_in)
    record_admin_action(
        actor_id=getattr(current_user, "id", None),
        action="account.created",
        target_type="account",
        target_id=created.id,
        details={"account_id": created.account_id, "name": created.name},
    )
    return created


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int,
    admin_user=Depends(deps.require_admin),
    db: deps.Session = Depends(deps.get_db),
) -> None:
    """Delete an account and its account-owned records as an administrator."""
    account = crud_account.crud_account.get(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    rule_ids = [row.id for row in db.query(AlertRule.id).filter(AlertRule.account_id == account_id).all()]
    if rule_ids:
        db.query(AlertNotification).filter(AlertNotification.rule_id.in_(rule_ids)).delete(synchronize_session=False)
    db.query(AlertNotification).filter(AlertNotification.account_id == account_id).delete(synchronize_session=False)
    for model in (Alert, TerraformBaseline, Report, Scan):
        db.query(model).filter(model.account_id == account_id).delete(synchronize_session=False)
    db.query(AlertRule).filter(AlertRule.account_id == account_id).delete(synchronize_session=False)
    tracked_resources = [row.id for row in db.query(Resource.id).filter(Resource.account_id == account_id).all()]
    if tracked_resources:
        db.query(DriftRecord).filter(DriftRecord.tracked_resource_id.in_(tracked_resources)).delete(synchronize_session=False)
    db.query(Resource).filter(Resource.account_id == account_id).delete(synchronize_session=False)
    db.delete(account)
    db.commit()
    record_admin_action(
        actor_id=getattr(admin_user, "id", None),
        action="account.deleted",
        target_type="account",
        target_id=account_id,
        details={"account_id": account.account_id, "name": account.name},
    )


MAX_TERRAFORM_PLAN_BYTES = 5 * 1024 * 1024


@router.post("/{account_id}/terraform-plan")
async def upload_terraform_plan(
    request: Request,
    current_user=Depends(rbac.require_role(Role.ADMIN, Role.OPERATOR)),
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> dict[str, int]:
    """Replace one account's Terraform baseline from a terraform show JSON payload."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_TERRAFORM_PLAN_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Terraform plan payload exceeds 5 MiB limit",
                )
        except ValueError:
            pass

    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_TERRAFORM_PLAN_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Terraform plan payload exceeds 5 MiB limit",
            )

    if not body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Terraform plan payload",
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid Terraform plan payload") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid Terraform plan payload")

    try:
        parsed = drift_orchestrator._state_document_resources(payload)
        resources = normalizer.normalize_resources(parsed)
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid Terraform plan payload") from exc

    if not resources:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Terraform plan payload contains no resources",
        )

    resource_rows = [resource.to_dict() for resource in resources]
    crud_resource.replace_terraform_baseline(db, account_id=account.id, resources=resource_rows)
    return {"resources_parsed": len(resource_rows)}


@router.post("/{account_id}/scan", status_code=status.HTTP_202_ACCEPTED)
def trigger_account_scan(
    account_id: str,
    background_tasks: BackgroundTasks,
    current_user: account_schema.AccountOut = Depends(deps.get_current_user),
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> dict[str, str]:
    """Queue an on-demand drift scan for an owned active account."""
    if not hasattr(account, "id"):
        account = crud_account.crud_account.get(db, id=account_id)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account is inactive")

    try:
        drift_orchestrator.trigger_account_scan(
            background_tasks,
            db,
            account.id,
            triggered_by_id=getattr(current_user, "id", None),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="scan already in progress for this account",
        ) from exc
    return {"status": "accepted", "account_id": str(account.id)}


@router.post("/{account_id}/scans", response_model=ScanOut, status_code=status.HTTP_202_ACCEPTED)
def create_scan(
    background_tasks: BackgroundTasks,
    current_user=Depends(deps.get_current_user),
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> Scan:
    """Queue a durable asynchronous scan for an authorized account."""
    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account is inactive")

    try:
        scan = drift_orchestrator.trigger_account_scan(
            background_tasks,
            db,
            account.id,
            triggered_by_id=getattr(current_user, "id", None),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="scan already in progress for this account",
        ) from exc
    return scan


@router.post("/{account_id}/automated-scan", response_model=ScanOut, status_code=status.HTTP_200_OK)
async def trigger_automated_scan(
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> Scan:
    """Run the complete automated drift workflow before returning the scan."""
    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account is inactive")

    scan = Scan(account_id=account.id, status="running")
    db.add(scan)
    try:
        db.commit()
        db.refresh(scan)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="scan already in progress for this account",
        ) from exc

    try:
        await drift_orchestrator.orchestrate_account_scan(
            str(account.id),
            "scheduled",
            db=db,
            scan_id=scan.id,
        )
    except Exception as exc:
        try:
            db.rollback()
            fresh_scan = db.get(Scan, scan.id)
            if fresh_scan is None:
                fresh_scan = db.query(Scan).filter(Scan.id == scan.id).one_or_none()
            if fresh_scan is not None and fresh_scan.status in {"queued", "running"}:
                fresh_scan.status = "failed"
                fresh_scan.error = str(exc)
                db.commit()
                db.refresh(fresh_scan)
                return fresh_scan
            if fresh_scan is not None:
                db.refresh(fresh_scan)
                return fresh_scan
        except Exception:
            db.rollback()
        raise

    db.refresh(scan)
    return scan


@router.get("/{account_id}/scans", response_model=List[ScanOut])
def list_account_scans(
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> List[Scan]:
    """Return recent scans for an authorized account, newest first, capped at 200."""
    return (
        db.query(Scan)
        .filter(Scan.account_id == account.id)
        .order_by(Scan.id.desc())
        .limit(200)
        .all()
    )


@router.get("/{account_id}/scans/{scan_id}", response_model=ScanOut)
def get_scan(
    scan_id: str,
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> Scan:
    """Return status for a scan belonging to the authorized account."""
    scan = _get_scan_for_account(db, account.id, scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return scan


@router.get("/{account_id}/scans/{scan_id}/drift")
def get_scan_drift(
    scan_id: str,
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> list:
    """Return drift results linked to a completed scan."""
    scan = _get_scan_for_account(db, account.id, scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return (scan.result or {}).get("drifts", [])


def _get_scan_for_account(db, account_id: int, public_scan_id: str) -> Scan:
    """Resolve a public scan identifier while enforcing account ownership."""
    try:
        scan_id = int(public_scan_id.removeprefix("scan_"))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    scan = db.query(Scan).filter(Scan.id == scan_id, Scan.account_id == account_id).first()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return scan


@router.get("/{account_id}/resources", response_model=List[ResourceOut])
def list_account_resources(
    account=Depends(deps.get_monitored_account),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: deps.Session = Depends(deps.get_db),
) -> List[ResourceOut]:
    """Return the current resource inventory for an authorized account."""
    return dashboard_service.list_resources(db, account_id=account.id, page=page, per_page=per_page)


@router.get("/{account_id}/dashboard", response_model=DashboardOut)
def account_dashboard(
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> DashboardOut:
    """Return the latest scan and alert counts for an authorized account."""
    latest_scan = (
        db.query(Scan)
        .filter(Scan.account_id == account.id)
        .order_by(Scan.created_at.desc())
        .limit(1)
        .first()
    )
    alert_counts = dict(
        db.query(Alert.severity, func.count(Alert.id))
        .filter(Alert.account_id == account.id, Alert.scan_id.isnot(None))
        .group_by(Alert.severity)
        .all()
    )

    return DashboardOut(
        account_id=account.id,
        latest_scan=(
            {
                "id": latest_scan.id,
                "status": latest_scan.status,
                "created_at": latest_scan.created_at,
                "summary": (latest_scan.result or {}).get("summary"),
            }
            if latest_scan
            else None
        ),
        alert_counts=alert_counts,
    )


@router.get("/{account_id}/alerts", response_model=List[AlertOut])
def account_alerts(
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> List[AlertOut]:
    """Return drift alerts for an authorized account."""
    return (
        db.query(Alert)
        .filter(Alert.account_id == account.id, Alert.scan_id.isnot(None))
        .order_by(Alert.created_at.desc())
        .all()
    )


@router.get("/{account_id}/report", response_model=AccountReportOut)
def account_report_snapshot(
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> AccountReportOut:
    """Return the latest completed scan's current drift snapshot."""
    latest_scan = (
        db.query(Scan)
        .filter(Scan.account_id == account.id, Scan.status == "completed")
        .order_by(Scan.created_at.desc())
        .limit(1)
        .first()
    )
    drifts = (latest_scan.result or {}).get("drifts", []) if latest_scan else []
    drifted_resources = [
        drift
        for drift in drifts
        if drift.get("is_drifted") is True and drift.get("is_known_exception") is not True
    ]
    severity_counts: dict[str, int] = {}
    for drift in drifted_resources:
        severity = str(drift.get("severity", "unknown"))
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    return AccountReportOut(
        account_id=account.id,
        generated_at=datetime.now(timezone.utc),
        latest_scan=(
            {
                "id": latest_scan.id,
                "status": latest_scan.status,
                "created_at": latest_scan.created_at,
                "summary": (latest_scan.result or {}).get("summary"),
            }
            if latest_scan
            else None
        ),
        drifted_resources=drifted_resources,
        severity_counts=severity_counts,
    )


@router.post("/{account_id}/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def account_report(
    report_in: ReportCreate,
    account=Depends(deps.get_monitored_account),
    db: deps.Session = Depends(deps.get_db),
) -> ReportOut:
    """Generate a report scoped to an authorized account."""
    return report_service.create_report(db, current_user=None, report_in=report_in, account_id=account.id)
