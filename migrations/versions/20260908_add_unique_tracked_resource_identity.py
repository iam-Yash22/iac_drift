"""Enforce unique tracked resource identity per account."""

from alembic import op


revision = "uq_tracked_resources"
down_revision = ("3a7c1d2e9f40", "5b1e2c3d4f50")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_tracked_resources_account_type_resource",
        "tracked_resources",
        ["account_id", "resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_tracked_resources_account_type_resource",
        "tracked_resources",
        type_="unique",
    )
