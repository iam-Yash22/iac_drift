from sqlalchemy import Column, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.account import AwsAccount
from app.models.base import AutoIncrementPKMixin, Base, TimestampMixin


class TerraformBaseline(Base, AutoIncrementPKMixin, TimestampMixin):
    __tablename__ = "terraform_baselines"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "resource_type",
            "resource_id",
            name="uq_terraform_baselines_account_type_resource",
        ),
    )

    account_id = Column(Integer, ForeignKey("aws_accounts.id"), nullable=False, index=True)
    resource_type = Column(String(255), nullable=False, index=True)
    resource_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    arn = Column(String(255), nullable=True)
    region = Column(String(50), nullable=True)
    tags = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    configuration = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)

    account = relationship("AwsAccount", backref="terraform_baselines")