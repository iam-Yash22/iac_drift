import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add parent directory (app) to path so relative imports work
app_path = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(app_path))
sys.path.insert(0, str(app_path.parent))

from db.base import Base
from core.config import settings


config = context.config

target_metadata = Base.metadata


def get_database_url() -> str:
    database_url = settings.database.url
    if database_url is None:
        raise RuntimeError("DATABASE__URL must be configured before running Alembic migrations.")
    return str(database_url)


config.set_main_option("sqlalchemy.url", get_database_url())


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
