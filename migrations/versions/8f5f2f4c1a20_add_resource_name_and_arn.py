"""Add display name and ARN to tracked resources.

Revision ID: 8f5f2f4c1a20
Revises: 0006
"""

from alembic import op
import sqlalchemy as sa


revision = "8f5f2f4c1a20"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracked_resources", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("tracked_resources", sa.Column("arn", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("tracked_resources", "arn")
    op.drop_column("tracked_resources", "name")