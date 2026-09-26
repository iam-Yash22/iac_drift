"""add persisted drift alerts

Revision ID: 3a7c1d2e9f40
Revises: 221ff54b37f2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "3a7c1d2e9f40"
down_revision = "221ff54b37f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("drift_record_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("diffs", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["aws_accounts.id"]),
        sa.ForeignKeyConstraint(["drift_record_id"], ["drift_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_account_id", "alerts", ["account_id"], unique=False)
    op.create_index("ix_alerts_drift_record_id", "alerts", ["drift_record_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_alerts_drift_record_id", table_name="alerts")
    op.drop_index("ix_alerts_account_id", table_name="alerts")
    op.drop_table("alerts")