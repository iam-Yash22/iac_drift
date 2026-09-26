"""Ensure unique Terraform baseline identity is declared and applied."""

from alembic import op
import sqlalchemy as sa


revision = "tf_baseline_uq"
down_revision = "terraform_baselines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("terraform_baselines")
    }
    if "uq_terraform_baselines_account_type_resource" not in constraints:
        op.create_unique_constraint(
            "uq_terraform_baselines_account_type_resource",
            "terraform_baselines",
            ["account_id", "resource_type", "resource_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("terraform_baselines")
    }
    if "uq_terraform_baselines_account_type_resource" in constraints:
        op.drop_constraint(
            "uq_terraform_baselines_account_type_resource",
            "terraform_baselines",
            type_="unique",
        )