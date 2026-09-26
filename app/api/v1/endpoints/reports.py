"""Report generation and download endpoints backed by accounts database."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse

from app.api import deps
from app.schemas import report as report_schema
from app.services import report_service, dashboard_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=report_schema.ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    report_in: report_schema.ReportCreate,
    account_id: Optional[int] = Query(default=None),
    current_user: report_schema.ReportOut = Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> report_schema.ReportOut:
    """Generate a report scoped to the user's account from accounts database."""
    # Resolve account ID to current user's account
    resolved_account_id = dashboard_service._resolve_account_id(
        db,
        current_user=current_user,
        account_id=account_id,
    )
    return report_service.create_report(
        db,
        current_user=current_user,
        report_in=report_in,
        account_id=resolved_account_id,
    )


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    current_user: report_schema.ReportOut = Depends(deps.get_current_user),
    db: deps.Session = Depends(deps.get_db),
) -> RedirectResponse:
    """Return a redirect to the presigned download URL for a generated report."""
    url = report_service.get_download_url(db, current_user=current_user, report_id=report_id)
    return RedirectResponse(url=url)
