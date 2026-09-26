"""SQLAlchemy model registration module for Alembic.

Imports every model module solely for side-effect registration onto ``Base.metadata``,
consumed by Alembic's ``env.py`` for autogenerate diffing. This module should
never be imported by runtime request-handling code.
"""

from app.models.account import AwsAccount  # noqa: F401
from app.models.alert import Alert, AlertRule, AlertNotification  # noqa: F401
from app.models.base import Base  # noqa: F401
from app.models.drift import DriftRecord  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.resource import TrackedResource  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.scan import Scan  # noqa: F401
from app.models.terraform_baseline import TerraformBaseline  # noqa: F401

__all__ = [
    "Base",
    "User",
    "AwsAccount",
    "TrackedResource",
    "DriftRecord",
    "TerraformBaseline",
    "AlertRule",
    "AlertNotification",
    "Alert",
    "Report",
]
