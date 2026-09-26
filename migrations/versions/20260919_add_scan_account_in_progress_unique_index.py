"""Add a partial unique index to ensure only one queued/running scan per account."""

from alembic import op

revision = "scan_account_in_progress_index"
down_revision = "scan_triggered_by"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY account_id
                           ORDER BY updated_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM scans
                WHERE status IN ('queued', 'running')
            )
            UPDATE scans AS s
            SET status = 'failed', error = 'orphaned'
            FROM ranked AS r
            WHERE s.id = r.id
              AND r.rn > 1
            """
        )

    op.create_index(
        "uq_scans_account_in_progress",
        "scans",
        ["account_id"],
        unique=True,
        sqlite_where="status IN ('queued', 'running')",
        postgresql_where="status IN ('queued', 'running')",
    )


def downgrade() -> None:
    op.drop_index("uq_scans_account_in_progress", table_name="scans")
