"""SQLAlchemy engine lifecycle helpers."""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def _is_test_runtime() -> bool:
    return (
        "pytest" in sys.modules
        or os.getenv("APP_ENV", "").lower() == "test"
        or os.getenv("ENVIRONMENT", "").lower() == "test"
        or os.getenv("PYTEST_CURRENT_TEST") is not None
    )


def _build_engine():
    database_url = settings.database.url
    if database_url is None:
        if _is_test_runtime():
            return create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        raise RuntimeError("DATABASE__URL must be configured before creating the SQLAlchemy engine.")
    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            echo=settings.database.echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(
        str(database_url),
        echo=settings.database.echo,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
    )


engine = _build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """FastAPI dependency to provide a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connectivity() -> None:
    """Verify the database is reachable by executing a trivial query."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def dispose_engine() -> None:
    """Release all connections held by the engine connection pool."""
    engine.dispose()
