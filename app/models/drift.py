from sqlalchemy import Column, JSON, String, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import AutoIncrementPKMixin, Base, TimestampMixin
from app.models.resource import TrackedResource
from app.core import constants


class DriftRecord(Base, AutoIncrementPKMixin, TimestampMixin):
    __tablename__ = "drift_records"

    tracked_resource_id = Column(Integer, ForeignKey("tracked_resources.id"), nullable=False, index=True)
    change_type = Column(String(100), nullable=False)
    diff = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    severity = Column(String(50), default=constants.DriftSeverity.LOW.value if hasattr(constants, "DriftSeverity") else "low", nullable=False)
    detected_by = Column(String(255), nullable=True)
    reconciled = Column(Boolean, default=False, nullable=False)

    resource = relationship("TrackedResource", backref="drift_records")


Drift = DriftRecord
