"""Dashboard response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LatestScanOut(BaseModel):
    """Summary of the latest account scan."""

    id: int
    status: str
    created_at: datetime | None = None
    summary: Any | None = None

    model_config = ConfigDict(from_attributes=True)


class DashboardOut(BaseModel):
    """Account dashboard summary."""

    account_id: int
    latest_scan: LatestScanOut | None = None
    alert_counts: dict[str, int]

    model_config = ConfigDict(from_attributes=True)


class AccountScanStatusOut(BaseModel):
    """Latest scan status for one account."""

    account_id: int
    status: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DashboardSummaryOut(BaseModel):
    """Company-wide dashboard summary for the current user's accounts."""

    total_accounts: int
    alert_counts: dict[str, int]
    latest_scans: list[AccountScanStatusOut]

    model_config = ConfigDict(from_attributes=True)


class SeverityHistoryPointOut(BaseModel):
    """Severity totals represented by one completed scan date."""

    date: datetime
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    none: int = 0


class SeverityHistoryOut(BaseModel):
    """Company-wide completed scan severity history."""

    first_scan_at: datetime | None = None
    points: list[SeverityHistoryPointOut]