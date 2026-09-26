from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import AutoIncrementPKMixin, Base, TimestampMixin
from app.models.user import User
from app.models.account import AwsAccount
from app.core import constants


class Report(Base, AutoIncrementPKMixin, TimestampMixin):
    __tablename__ = "reports"

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    file_path = Column(String(1024), nullable=False)

    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    generated_by = relationship("User", backref="reports")

    account_id = Column(Integer, ForeignKey("aws_accounts.id"), nullable=True)
    account = relationship("AwsAccount", backref="reports")

    format = Column(String(50), default=(constants.ReportFormat.PDF.value if hasattr(constants, "ReportFormat") else "pdf"), nullable=False)
