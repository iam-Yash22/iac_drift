from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import AutoIncrementPKMixin, Base, TimestampMixin
from app.models.account import AwsAccount
from app.models.drift import DriftRecord
from app.models.scan import Scan
from app.core import constants


class AlertRule(Base, AutoIncrementPKMixin, TimestampMixin):
    __tablename__ = "alert_rules"

    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(50), default=(constants.AlertSeverity.MEDIUM.value if hasattr(constants, "AlertSeverity") else "medium"), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    account_id = Column(Integer, ForeignKey("aws_accounts.id"), nullable=True)
    account = relationship("AwsAccount", backref="alert_rules")

    notifications = relationship("AlertNotification", back_populates="rule", cascade="all, delete-orphan")


class Alert(Base, AutoIncrementPKMixin, TimestampMixin):
    __tablename__ = "alerts"

    account_id = Column(Integer, ForeignKey("aws_accounts.id"), nullable=False, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=True, index=True)
    drift_record_id = Column(Integer, ForeignKey("drift_records.id"), nullable=False, index=True)
    resource_id = Column(String(255), nullable=False)
    resource_type = Column(String(255), nullable=False)
    severity = Column(String(50), nullable=False)
    diffs = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    summary = Column(Text, nullable=False)

    account = relationship("AwsAccount", backref="alerts")
    scan = relationship("Scan", backref="alerts")
    drift_record = relationship("DriftRecord", backref="alerts")


class AlertNotification(Base, AutoIncrementPKMixin, TimestampMixin):
    __tablename__ = "alert_notifications"

    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False, index=True)
    channel = Column(String(50), nullable=False)  # e.g. email, slack
    target = Column(String(1024), nullable=False)  # destination address or webhook
    active = Column(Boolean, default=True, nullable=False)

    # Optional linkage to an account or a specific drift record that triggered the notification
    account_id = Column(Integer, ForeignKey("aws_accounts.id"), nullable=True)
    drift_record_id = Column(Integer, ForeignKey("drift_records.id"), nullable=True)

    rule = relationship("AlertRule", back_populates="notifications")
    account = relationship("AwsAccount", backref="alert_notifications")
    drift_record = relationship("DriftRecord", backref="alert_notifications")


AlertAudit = AlertNotification
