"""Add email as a user login identity field."""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}

    if "email" not in columns:
        op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
        op.execute("UPDATE users SET email = username || '@example.com'")
        op.alter_column("users", "email", nullable=False)

    if "ix_users_email" not in indexes:
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "email")