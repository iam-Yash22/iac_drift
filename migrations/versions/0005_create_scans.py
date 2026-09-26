"""create durable scan jobs

Revision ID: 0005
Revises: 221ff54b37f2

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "221ff54b37f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["aws_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scans_account_id", "scans", ["account_id"], unique=False)
    op.create_index("ix_scans_status", "scans", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scans_status", table_name="scans")
    op.drop_index("ix_scans_account_id", table_name="scans")
    op.drop_table("scans")
