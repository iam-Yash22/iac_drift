"""Database initialization module for bootstrapping the admin account."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import DEFAULT_BOOTSTRAP_ADMIN_PASSWORD, settings
from app.core.constants import Role
from app.crud.crud_user import crud_user
from app.schemas.user import UserCreate


def _ensure_demo_viewer(db: Session) -> None:
    if not settings.demo_mode:
        return

    viewer_username = (settings.demo_viewer_username or "").strip()
    viewer_password = settings.demo_viewer_password.get_secret_value() if settings.demo_viewer_password else ""
    if not viewer_username or not viewer_password.strip():
        return

    prompt_user = crud_user.get_by_login(db, login=viewer_username)
    if prompt_user is None:
        crud_user.create(
            db,
            obj_in=UserCreate(
                username=viewer_username,
                email=f"{viewer_username}@example.com",
                password=viewer_password,
            ),
        )
        db.commit()
        return

    prompt_user.role = Role.VIEWER.value
    db.add(prompt_user)
    db.commit()


def init_db(db: Session) -> None:
    """Ensure the configured bootstrap admin user exists and is an admin."""
    admin_username = (settings.admin_username or "admin").strip() or "admin"
    admin_email = str(settings.admin_email)
    admin_password = (
        settings.admin_password.get_secret_value()
        if settings.admin_password is not None
        else DEFAULT_BOOTSTRAP_ADMIN_PASSWORD
    )

    admin_user = crud_user.get_by_login(db, login=admin_username)
    if admin_user is None:
        admin_user = crud_user.create(
            db,
            obj_in=UserCreate(
                username=admin_username,
                email=admin_email,
                password=admin_password,
            ),
        )

    admin_user.email = admin_email
    admin_user.role = Role.ADMIN.value
    db.add(admin_user)
    db.commit()

    _ensure_demo_viewer(db)
    db.commit()
