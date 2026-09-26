"""associate scans with the user who triggered them"""

from alembic import op
import sqlalchemy as sa


revision = "scan_triggered_by"
down_revision = "tf_baseline_uq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("triggered_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_scans_triggered_by_id_users",
        "scans",
        "users",
        ["triggered_by_id"],
        ["id"],
    )
    op.create_index("ix_scans_triggered_by_id", "scans", ["triggered_by_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scans_triggered_by_id", table_name="scans")
    op.drop_constraint("fk_scans_triggered_by_id_users", "scans", type_="foreignkey")
    op.drop_column("scans", "triggered_by_id")
