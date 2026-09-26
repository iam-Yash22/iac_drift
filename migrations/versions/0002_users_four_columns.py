"""Reduce users to identity, password, and manually managed role."""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}

    if "hashed_password" not in columns:
        op.add_column("users", sa.Column("hashed_password", sa.String(length=255), nullable=True))
        op.execute("UPDATE users SET hashed_password = password_hash")
        op.alter_column("users", "hashed_password", nullable=False)
    if "username" not in columns:
        op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
        op.execute("UPDATE users SET username = 'user_' || id")
        op.alter_column("users", "username", nullable=False)
    if "email" not in columns:
        op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
        op.execute("UPDATE users SET email = username || '@example.com'")
        op.alter_column("users", "email", nullable=False)
    if "role" not in columns:
        op.add_column("users", sa.Column("role", sa.String(length=50), nullable=False, server_default="viewer"))

    if "users_email_key" in {constraint.name for constraint in sa.inspect(bind).get_unique_constraints("users")}:
        op.drop_constraint("users_email_key", "users", type_="unique")
    for column in ("name", "password_hash", "full_name", "is_active", "is_superuser", "created_at", "updated_at"):
        if column in columns:
            op.drop_column("users", column)
    if "ix_users_username" not in indexes:
        op.create_index("ix_users_username", "users", ["username"], unique=True)
    if "ix_users_email" not in indexes:
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    raise NotImplementedError("Downgrade 0002 requires restoring removed user data manually")