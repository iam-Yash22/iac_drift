"""Create account-scoped Terraform baseline storage."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "terraform_baselines"
down_revision = "uq_tracked_resources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "terraform_baselines",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=255), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("arn", sa.String(length=255), nullable=True),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["aws_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "resource_type", "resource_id", name="uq_terraform_baselines_account_type_resource"),
    )
    op.create_index("ix_terraform_baselines_account_id", "terraform_baselines", ["account_id"])
    op.create_index("ix_terraform_baselines_resource_type", "terraform_baselines", ["resource_type"])
    op.create_index("ix_terraform_baselines_resource_id", "terraform_baselines", ["resource_id"])


def downgrade() -> None:
    op.drop_index("ix_terraform_baselines_resource_id", table_name="terraform_baselines")
    op.drop_index("ix_terraform_baselines_resource_type", table_name="terraform_baselines")
    op.drop_index("ix_terraform_baselines_account_id", table_name="terraform_baselines")
    op.drop_table("terraform_baselines")