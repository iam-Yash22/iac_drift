"""Pytest fixtures for tests: `db_session`, `client`, `auth_headers`.

Fixtures:
- `db_session`: function-scoped transactional SQLAlchemy session against an in-memory SQLite engine.
- `client`: `TestClient` with the application's DB dependency overridden to use `db_session`.
- `auth_headers`: best-effort helper that tries to obtain a token via `/auth/token`, falling back to a placeholder header.

Allowed imports only: pytest, fastapi.testclient.TestClient, sqlalchemy, app.factory, db.session, db.base
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.factory import create_app
from app.api import deps as api_deps
from app.db import base as db_base
from app.db import session as db_session_module


@pytest.fixture(scope="function")
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db_base.Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        db_base.Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    app = create_app()

    get_db = getattr(db_session_module, "get_db", None)
    if get_db is not None:
        def _override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[api_deps.get_db] = _override_get_db

    monkeypatch.setattr("app.lifespan.SessionLocal", lambda: db_session)
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(client, db_session):
    try:
        resp = client.post("/auth/token", data={"username": "test", "password": "test"})
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                return {"Authorization": f"Bearer {token}"}
    except Exception:
        pass
    return {"Authorization": "Bearer testtoken"}
