"""Shared cross-cutting enumerations for IaC DriftWatch.

Pure constant definitions with no external dependencies. Import enums at
module-load time wherever a stable, shared vocabulary is needed across
API schemas, services, persistence, and background workers::

    from app.core.constants import DriftType, Role, Severity

These types are intentionally decoupled from Pydantic models and ORM
mappings so they can be referenced from any layer without import cycles.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ALERT_SEVERITY_LOW",
    "ALERT_SEVERITY_MEDIUM",
    "ALERT_SEVERITY_HIGH",
    "ALERT_SEVERITY_CRITICAL",
    "AlertChannel",
    "DRIFT_STATUS_PENDING",
    "DRIFT_STATUS_DETECTED",
    "DRIFT_STATUS_RESOLVED",
    "DriftType",
    "REPORT_FORMAT_JSON",
    "REPORT_FORMAT_CSV",
    "REPORT_FORMAT_HTML",
    "ReportFormat",
    "Role",
    "Severity",
]


class Role(StrEnum):
    """Authorization roles for platform users and service accounts."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    SERVICE = "service"


class DriftType(StrEnum):
    """Classification of infrastructure drift between IaC and live state."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RECREATED = "recreated"
    UNMANAGED = "unmanaged"


class Severity(StrEnum):
    """Impact severity assigned to a drift event or alert."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertChannel(StrEnum):
    """Outbound notification delivery channels."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    TEAMS = "teams"
    PAGERDUTY = "pagerduty"


class ReportFormat(StrEnum):
    """Supported export formats for drift and audit reports."""

    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    HTML = "html"
    XLSX = "xlsx"


ALERT_SEVERITY_LOW = Severity.LOW.value
ALERT_SEVERITY_MEDIUM = Severity.MEDIUM.value
ALERT_SEVERITY_HIGH = Severity.HIGH.value
ALERT_SEVERITY_CRITICAL = Severity.CRITICAL.value

DRIFT_STATUS_PENDING = "pending"
DRIFT_STATUS_DETECTED = "detected"
DRIFT_STATUS_RESOLVED = "resolved"

REPORT_FORMAT_JSON = ReportFormat.JSON.value
REPORT_FORMAT_CSV = ReportFormat.CSV.value
REPORT_FORMAT_HTML = ReportFormat.HTML.value
