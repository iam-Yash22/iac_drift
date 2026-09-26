"""Alert rule request and response schemas for alert configuration routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import ALERT_SEVERITY_LOW, ALERT_SEVERITY_MEDIUM, ALERT_SEVERITY_HIGH, ALERT_SEVERITY_CRITICAL

__all__ = [
    "AlertRuleCreate",
    "AlertRuleRead",
    "AlertRuleUpdate",
    "AlertRuleOut",
    "AlertOut",
    "AlertAuditCreate",
    "AlertAuditUpdate",
]


class AlertRuleBase(BaseModel):
    """Shared alert rule fields."""

    name: str = Field(..., min_length=1, max_length=200, description="Rule name.")
    description: str | None = Field(default=None, max_length=2000, description="Optional rule description.")
    resource_type: str | None = Field(default=None, description="Resource type to which the rule applies.")
    severity: str = Field(..., description="Severity level for the alert.")
    enabled: bool = Field(default=True, description="Whether the rule is active.")
    conditions: dict[str, Any] = Field(default_factory=dict, description="Condition payload evaluated by the rule.")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional extra metadata.")

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: str) -> str:
        valid = {
            ALERT_SEVERITY_LOW,
            ALERT_SEVERITY_MEDIUM,
            ALERT_SEVERITY_HIGH,
            ALERT_SEVERITY_CRITICAL,
        }
        if value not in valid:
            raise ValueError(f"severity must be one of: {sorted(valid)}")
        return value


class AlertRuleCreate(AlertRuleBase):
    """Schema for creating alert rules."""

    model_config = ConfigDict(extra="forbid")


class AlertRuleRead(AlertRuleBase):
    """Schema returned by alert rule APIs."""

    id: int = Field(..., description="Database-generated alert rule identifier.")
    account_id: int | None = Field(default=None, description="Owning account identifier.")
    created_at: str | None = Field(default=None, description="Rule creation timestamp.")
    updated_at: str | None = Field(default=None, description="Last update timestamp.")
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AlertOut(BaseModel):
    """Schema returned for drift alerts."""

    id: int
    account_id: int
    scan_id: int | None = None
    drift_record_id: int
    resource_id: str
    resource_type: str
    severity: str
    diffs: dict[str, Any]
    summary: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


AlertRuleUpdate = AlertRuleCreate
AlertRuleOut = AlertRuleRead
AlertAuditCreate = AlertRuleCreate
AlertAuditUpdate = AlertRuleCreate
