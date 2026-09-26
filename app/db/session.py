"""SQLAlchemy engine lifecycle helpers."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

engine = create_engine(
    str(settings.database.url),
    echo=settings.database.echo,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_timeout=settings.database.pool_timeout,
    pool_recycle=settings.database.pool_recycle,
)

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
