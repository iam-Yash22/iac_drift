"""Dashboard summary endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func

from app.api import deps
from app.models.account import AwsAccount
from app.models.alert import Alert
from app.models.scan import Scan
from app.schemas.dashboard import DashboardSummaryOut, SeverityHistoryOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
def get_summary(
    current_user=Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> DashboardSummaryOut:
    """Return company-wide dashboard data scoped to the current user's accounts."""
    accounts = db.query(AwsAccount).all()

    latest_scans = []
    for account in accounts:
        latest_scan = (
            db.query(Scan)
            .filter(Scan.account_id == account.id)
            .order_by(Scan.created_at.desc())
            .limit(1)
            .first()
        )
        latest_scans.append(
            {
                "account_id": account.id,
                "status": latest_scan.status if latest_scan else None,
            }
        )

    alert_query = db.query(Alert.severity, func.count(Alert.id)).join(
        AwsAccount,
        Alert.account_id == AwsAccount.id,
    ).filter(Alert.scan_id.isnot(None))
    alert_counts = dict(alert_query.group_by(Alert.severity).all())

    return DashboardSummaryOut(
        total_accounts=len(accounts),
        alert_counts=alert_counts,
        latest_scans=latest_scans,
    )


@router.get("/severity-history", response_model=SeverityHistoryOut)
def get_severity_history(
    account_id: int | None = Query(default=None),
    current_user=Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> SeverityHistoryOut:
    """Return severity totals for every completed scan, ordered by scan date."""
    scan_query = (
        db.query(Scan)
        .filter(Scan.status == "completed", Scan.created_at.isnot(None))
    )
    if account_id is not None:
        scan_query = scan_query.filter(Scan.account_id == account_id)
    completed_scans = scan_query.order_by(Scan.created_at.asc(), Scan.id.asc()).all()
    if not completed_scans:
        return SeverityHistoryOut(first_scan_at=None, points=[])

    points = []
    for scan in completed_scans:
        counts = {severity: 0 for severity in ("critical", "high", "medium", "low", "info", "none")}
        scan_severities = set()
        for drift in (scan.result or {}).get("drifts", []):
            if drift.get("is_drifted") is not True or drift.get("is_known_exception") is True:
                continue
            severity = str(drift.get("severity", "none")).lower()
            scan_severities.add(severity)
        for severity in scan_severities:
            counts[severity] = counts.get(severity, 0) + 1
        points.append({"date": scan.created_at, **counts})

    return SeverityHistoryOut(
        first_scan_at=completed_scans[0].created_at,
        points=points,
    )
