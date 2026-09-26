from sqlalchemy import Column, ForeignKey, Index, JSON, String, text
from sqlalchemy.orm import relationship

from app.models.base import AutoIncrementPKMixin, Base, TimestampMixin


class Scan(Base, AutoIncrementPKMixin, TimestampMixin):
    __tablename__ = "scans"
    __table_args__ = (
        Index(
            "uq_scans_account_in_progress",
            "account_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    account_id = Column(ForeignKey("aws_accounts.id"), nullable=False, index=True)
    triggered_by_id = Column(ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    result = Column(JSON, nullable=True)
    error = Column(String(2000), nullable=True)

    account = relationship("AwsAccount", backref="scans")
    triggered_by = relationship("User", backref="triggered_scans")

    @property
    def scan_id(self) -> str:
        return f"scan_{self.id}"
