"""Assign external IDs to monitored accounts.

Revision ID: 0006
Revises: 0005

"""
import secrets

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    accounts = connection.execute(
        sa.select(sa.column("id")).select_from(sa.table("aws_accounts"))
    ).fetchall()
    for (account_id,) in accounts:
        connection.execute(
            sa.text(
                "UPDATE aws_accounts SET external_id = :external_id "
                "WHERE id = :account_id AND external_id IS NULL"
            ),
            {"external_id": secrets.token_hex(16), "account_id": account_id},
        )

    with op.batch_alter_table("aws_accounts") as batch_op:
        batch_op.alter_column(
            "external_id",
            existing_type=sa.String(length=255),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("aws_accounts") as batch_op:
        batch_op.alter_column(
            "external_id",
            existing_type=sa.String(length=255),
            nullable=True,
        )