"""Role-based access control (RBAC) route guard dependencies."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_active_user
from app.core.constants import Role


def require_role(*roles: Role | str) -> Callable[..., None]:
    """Dependency factory that verifies the current active user possesses an allowed role.

    Usage::

        @router.get("/admin/settings", dependencies=[Depends(require_role(Role.ADMIN))])
        def admin_settings(): ...
    """
    allowed_roles = {r if isinstance(r, str) else r.value for r in roles}

    def role_checker(
        current_user=Depends(get_current_active_user),
    ) -> None:
        user_role = getattr(current_user, "role", None)
        if user_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no assigned role",
            )
        user_role_str = user_role.value if isinstance(user_role, Role) else str(user_role)
        if user_role_str not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted",
            )

    return role_checker


def require_admin(current_user) -> None:
    """Reject non-admin users for handlers with an already validated JWT."""
    role = getattr(current_user, "role", None)
    role_value = role.value if isinstance(role, Role) else str(role)
    if role_value != Role.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )
