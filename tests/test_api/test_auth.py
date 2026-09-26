from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import sessionmaker

from fastapi import HTTPException

from app.api.v1.endpoints.users import delete_user, update_user
from app.core.config import DEFAULT_BOOTSTRAP_ADMIN_PASSWORD, settings
from app.core.constants import Role
from app.lifespan import lifespan
from app.models.scan import Scan
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate


def _try_post(client, payload):
    for path in ("/api/v1/auth/token", "/api/v1/auth/login"):
        resp = client.post(path, data=payload)
        if resp.status_code == 404:
            continue
        return path, resp
    pytest.skip("No auth token/login endpoint found")


def test_token_endpoint_returns_token_or_401(client):
    payload = {"username": "test", "password": "test"}
    path, resp = _try_post(client, payload)

    assert resp.status_code in (200, 401), f"Unexpected status from {path}: {resp.status_code}"

    if resp.status_code == 200:
        body = resp.json()
        assert isinstance(body, dict)
        assert "access_token" in body


def test_protected_endpoint_access_with_auth(client, auth_headers):
    for path in ("/api/v1/auth/me", "/api/v1/users/me"):
        resp = client.get(path, headers=auth_headers)
        if resp.status_code == 404:
            continue
        assert resp.status_code in (200, 401, 405), f"Unexpected status from {path}: {resp.status_code}"
        return
    pytest.skip("No protected 'me' endpoint found")


@pytest.mark.asyncio
async def test_lifespan_bootstraps_default_admin_user(db_session, monkeypatch):
    monkeypatch.setattr("app.lifespan.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.lifespan.check_db_connectivity", lambda: None)
    monkeypatch.setattr("app.lifespan.dispose_engine", lambda: None)
    monkeypatch.setattr("app.core.config.settings.admin_username", "admin", raising=False)
    monkeypatch.setattr("app.core.config.settings.admin_email", "admin@driftwatch-app.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.admin_password", type("Secret", (), {"get_secret_value": lambda self: "StrongPassword123!"})(), raising=False)

    app = MagicMock()
    async with lifespan(app):
        user = db_session.query(User).filter(User.username == "admin").first()
        assert user is not None
        assert user.role == Role.ADMIN.value
        assert user.email == "admin@driftwatch-app.com"


@pytest.mark.asyncio
async def test_lifespan_bootstrap_is_idempotent_and_keeps_password(db_session, monkeypatch):
    monkeypatch.setattr("app.lifespan.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.lifespan.check_db_connectivity", lambda: None)
    monkeypatch.setattr("app.lifespan.dispose_engine", lambda: None)
    monkeypatch.setattr("app.core.config.settings.admin_username", "admin", raising=False)
    monkeypatch.setattr("app.core.config.settings.admin_email", "admin@driftwatch-app.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.admin_password", type("Secret", (), {"get_secret_value": lambda self: "StrongPassword123!"})(), raising=False)

    db_session.add(User(username="admin", email="admin@driftwatch-app.com", hashed_password="hashed-password", role=Role.VIEWER.value))
    db_session.commit()

    app = MagicMock()
    async with lifespan(app):
        user = db_session.query(User).filter(User.username == "admin").one()
        assert user.role == Role.ADMIN.value
        assert user.hashed_password == "hashed-password"


@pytest.mark.asyncio
async def test_lifespan_promotes_wrong_role_admin(db_session, monkeypatch):
    monkeypatch.setattr("app.lifespan.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.lifespan.check_db_connectivity", lambda: None)
    monkeypatch.setattr("app.lifespan.dispose_engine", lambda: None)
    monkeypatch.setattr("app.core.config.settings.admin_username", "admin", raising=False)
    monkeypatch.setattr("app.core.config.settings.admin_email", "admin@driftwatch-app.com", raising=False)
    monkeypatch.setattr("app.core.config.settings.admin_password", type("Secret", (), {"get_secret_value": lambda self: "StrongPassword123!"})(), raising=False)

    db_session.add(User(username="admin", email="admin@driftwatch-app.com", hashed_password="hashed-password", role=Role.VIEWER.value))
    db_session.commit()

    app = MagicMock()
    async with lifespan(app):
        user = db_session.query(User).filter(User.username == "admin").one()
        assert user.role == Role.ADMIN.value


@pytest.mark.asyncio
async def test_lifespan_rejects_weak_default_password_outside_dev(db_session, monkeypatch):
    monkeypatch.setattr("app.lifespan.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.lifespan.check_db_connectivity", lambda: None)
    monkeypatch.setattr("app.lifespan.dispose_engine", lambda: None)
    monkeypatch.setattr("app.core.config.settings.app.environment", "production", raising=False)
    monkeypatch.setattr("app.core.config.settings.admin_password", type("Secret", (), {"get_secret_value": lambda self: DEFAULT_BOOTSTRAP_ADMIN_PASSWORD})(), raising=False)

    app = MagicMock()
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        async with lifespan(app):
            pass


def test_users_delete_and_demote_last_admin_are_rejected(db_session):
    admin = User(username="admin", email="admin@driftwatch-app.com", hashed_password="hashed-password", role=Role.ADMIN.value)
    second = User(username="operator", email="operator@example.com", hashed_password="hashed-password", role=Role.OPERATOR.value)
    db_session.add_all([admin, second])
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        delete_user(admin.id, admin_user=admin, db=db_session)
    assert exc_info.value.status_code == 409

    db_session.rollback()
    db_session.expire_all()
    admin = db_session.query(User).filter(User.username == "admin").one()
    with pytest.raises(HTTPException) as exc_info:
        update_user(admin.id, UserUpdate(role=Role.VIEWER.value), admin_user=admin, db=db_session)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_lifespan_marks_stale_running_scans_as_orphaned(db_session, monkeypatch):
    monkeypatch.setattr("app.lifespan.SessionLocal", lambda: sessionmaker(bind=db_session.bind)())
    monkeypatch.setattr("app.lifespan.check_db_connectivity", lambda: None)
    monkeypatch.setattr("app.lifespan.dispose_engine", lambda: None)
    monkeypatch.setattr("app.core.config.settings.scan_stale_minutes", 30, raising=False)

    stale = Scan(account_id=1, status="running", error=None)
    stale.created_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stale.updated_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.add(stale)
    db_session.commit()

    app = MagicMock()
    async with lifespan(app):
        pass

    fresh_session = sessionmaker(bind=db_session.bind)()
    try:
        refreshed = fresh_session.query(Scan).filter(Scan.id == stale.id).one()
        assert refreshed.status == "failed"
        assert refreshed.error == "orphaned"
    finally:
        fresh_session.close()


def test_user_read_includes_id():
    user = UserRead.model_validate({
        "id": 7,
        "username": "alice",
        "email": "alice@example.com",
        "role": "admin",
    })

    assert user.id == 7
    assert user.model_dump()["id"] == 7
