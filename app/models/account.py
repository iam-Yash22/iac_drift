from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from app.models.base import AutoIncrementPKMixin, Base, TimestampMixin
from app.models.user import User


class AwsAccount(Base, AutoIncrementPKMixin, TimestampMixin):
    __tablename__ = "aws_accounts"

    account_id = Column(String(12), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    role_arn = Column(String(255), nullable=False)
    external_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", backref="aws_accounts")
