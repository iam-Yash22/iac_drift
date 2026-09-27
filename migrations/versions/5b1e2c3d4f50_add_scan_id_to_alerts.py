"""link persisted drift alerts to scans

Revision ID: 5b1e2c3d4f50
Revises: 8f5f2f4c1a20
"""

from alembic import op
import sqlalchemy as sa


revision = "5b1e2c3d4f50"
down_revision = "8f5f2f4c1a20"
branch_labels = None
depends_on = "3a7c1d2e9f40"


def upgrade() -> None:
    op.add_column("alerts", sa.Column("scan_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_alerts_scan_id_scans", "alerts", "scans", ["scan_id"], ["id"])
    op.create_index("ix_alerts_scan_id", "alerts", ["scan_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_alerts_scan_id", table_name="alerts")
    op.drop_constraint("fk_alerts_scan_id_scans", "alerts", type_="foreignkey")
    op.drop_column("alerts", "scan_id")
