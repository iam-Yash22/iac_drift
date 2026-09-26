from sqlalchemy import Column, JSON, String, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import AutoIncrementPKMixin, Base, TimestampMixin
from app.models.account import AwsAccount


class TrackedResource(Base, AutoIncrementPKMixin, TimestampMixin):
    __tablename__ = "tracked_resources"

    account_id = Column(Integer, ForeignKey("aws_accounts.id"), nullable=False, index=True)
    resource_id = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    arn = Column(String(255), nullable=True)
    region = Column(String(50), nullable=False, index=True)
    tags = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    configuration = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)

    account = relationship("AwsAccount", backref="tracked_resources")


Resource = TrackedResource
