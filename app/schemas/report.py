"""Report request and response schemas for report generation endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import REPORT_FORMAT_JSON, REPORT_FORMAT_CSV, REPORT_FORMAT_HTML
from app.schemas.dashboard import LatestScanOut

__all__ = [
    "ReportRequest",
    "ReportRead",
    "ReportCreate",
    "ReportUpdate",
    "ReportOut",
        "AccountReportOut",
]


class ReportRequest(BaseModel):
    """Schema used to request a report generation job."""

    report_type: str = Field(..., description="Type of report to generate.")
    format: str = Field(default=REPORT_FORMAT_JSON, description="Output format for the generated report.")
    account_id: int | None = Field(default=None, description="Optional account filter.")
    resource_id: int | None = Field(default=None, description="Optional resource filter.")
    start_date: datetime | None = Field(default=None, description="Start timestamp for the report window.")
    end_date: datetime | None = Field(default=None, description="End timestamp for the report window.")
    filters: dict[str, Any] | None = Field(default=None, description="Additional report filters.")
    model_config = ConfigDict(extra="forbid")

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        valid = {REPORT_FORMAT_JSON, REPORT_FORMAT_CSV, REPORT_FORMAT_HTML}
        if value not in valid:
            raise ValueError(f"format must be one of: {sorted(valid)}")
        return value


class ReportRead(BaseModel):
    """Schema returned for a generated report job or stored report metadata."""

    id: int = Field(..., description="Database-generated report identifier.")
    report_type: str = Field(..., description="Type of generated report.")
    format: str = Field(..., description="Report output format.")
    status: str = Field(..., description="Current report generation status.")
    account_id: int | None = Field(default=None, description="Account associated with the report.")
    resource_id: int | None = Field(default=None, description="Resource associated with the report.")
    created_at: datetime | None = Field(default=None, description="When the report was created.")
    completed_at: datetime | None = Field(default=None, description="When the report finished.")
    download_url: str | None = Field(default=None, description="URL to fetch the generated artifact.")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional report metadata.")
    model_config = ConfigDict(from_attributes=True, extra="forbid")


ReportCreate = ReportRequest
ReportUpdate = ReportRequest
ReportOut = ReportRead


class AccountReportOut(BaseModel):
    """Current drift snapshot for an account."""

    account_id: int
    generated_at: datetime
    latest_scan: LatestScanOut | None = None
    drifted_resources: list[dict[str, Any]] = Field(default_factory=list)
    severity_counts: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
