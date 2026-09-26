"""Health check endpoints with accounts database validation."""

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text

from app.api import deps
from app.db import session as db_session
from app.crud import crud_account

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", status_code=status.HTTP_200_OK)
def health() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready() -> dict[str, Any]:
    """Readiness probe that confirms the accounts database is reachable with active accounts."""
    db = db_session.SessionLocal()
    try:
        # Check database connectivity
        db.execute(text("SELECT 1"))
        
        # Check accounts table and active accounts
        active_accounts = crud_account.crud_account.get_active(db)
        account_count = len(active_accounts) if active_accounts else 0
        
        return {
            "status": "ready",
            "database": "connected",
            "active_accounts": account_count,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
    finally:
        db.close()
