"""Drift and Terraform plan payload schemas used across drift and webhook endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import DRIFT_STATUS_PENDING, DRIFT_STATUS_DETECTED, DRIFT_STATUS_RESOLVED

__all__ = [
    "DriftRecordRead",
    "DriftScanRequest",
    "TerraformPlanIngest",
    "DriftCreate",
    "DriftUpdate",
    "DriftRecord",
    "DashboardSummary",
]


class DriftRecordRead(BaseModel):
    """Schema returned for drift detection records."""

    id: int = Field(..., description="Database-generated drift record identifier.")
    resource_id: int = Field(..., description="Tracked resource identifier associated with the drift record.")
    account_id: int | None = Field(default=None, description="Owning account identifier.")
    status: str = Field(..., description="Current drift status.")
    summary: str | None = Field(default=None, description="Short human-readable drift summary.")
    details: dict[str, Any] | None = Field(default=None, description="Structured drift metadata.")
    detected_at: datetime | None = Field(default=None, description="When the drift was detected.")
    resolved_at: datetime | None = Field(default=None, description="When the drift was resolved.")
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        valid = {
            DRIFT_STATUS_PENDING,
            DRIFT_STATUS_DETECTED,
            DRIFT_STATUS_RESOLVED,
        }
        if value not in valid:
            raise ValueError(f"status must be one of: {sorted(valid)}")
        return value


class DriftScanRequest(BaseModel):
    """Schema for requesting a new drift scan for one or many resources."""

    resource_ids: list[int] | None = Field(default=None, description="Resource identifiers to scan.")
    account_id: int | None = Field(default=None, description="Optional account filter.")
    force: bool = Field(default=False, description="Whether to bypass cached scan results.")
    model_config = ConfigDict(extra="forbid")


class TerraformPlanIngest(BaseModel):
    """Schema for ingesting Terraform plan outputs from webhook sources."""

    plan_id: str = Field(..., min_length=1, description="Terraform plan identifier.")
    workspace: str | None = Field(default=None, description="Terraform workspace name.")
    account_id: int | None = Field(default=None, description="Account associated with the plan.")
    resource_id: int | None = Field(default=None, description="Resource associated with the plan.")
    format: str = Field(default="terraform", description="Plan input format.")
    raw_plan: dict[str, Any] = Field(..., description="Raw Terraform plan payload.")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata for the ingestion.")
    model_config = ConfigDict(extra="forbid")


class DriftPayload(BaseModel):
    """Client-supplied drift fields; the database supplies the ID."""

    resource_id: int = Field(..., description="Tracked resource identifier associated with the drift record.")
    account_id: int | None = Field(default=None, description="Owning account identifier.")
    status: str = Field(..., description="Current drift status.")
    summary: str | None = Field(default=None, description="Short human-readable drift summary.")
    details: dict[str, Any] | None = Field(default=None, description="Structured drift metadata.")
    detected_at: datetime | None = Field(default=None, description="When the drift was detected.")
    resolved_at: datetime | None = Field(default=None, description="When the drift was resolved.")
    model_config = ConfigDict(extra="forbid")


DriftCreate = DriftPayload
DriftUpdate = DriftPayload
DriftRecord = DriftRecordRead


class DashboardSummary(BaseModel):
    """Summary payload returned by the dashboard endpoint."""

    total_drifts: int = 0
    pending_drifts: int = 0
    resolved_drifts: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_account: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="ignore")
