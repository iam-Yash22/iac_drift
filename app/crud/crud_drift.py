from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

import app.models.drift
import app.schemas.drift
import app.models as models
import app.schemas as schemas
from app.crud.base import CRUDBase


class CRUDDrift(CRUDBase[models.drift.Drift, schemas.drift.DriftCreate, schemas.drift.DriftUpdate]):
    """CRUD operations for drift records plus aggregation helpers."""

    def list_for_account(self, db: Session, *, account_id: int) -> List[models.drift.Drift]:
        """Return drift records associated with an account."""
        return (
            db.query(self.model)
            .join(self.model.resource)
            .filter(models.resource.TrackedResource.account_id == account_id)
            .all()
        )

    def count_by_severity(self, db: Session, *, since: Optional[Any] = None) -> List[Dict[str, Any]]:
        q = db.query(models.drift.Drift.severity.label("severity"), func.count().label("count"))
        if since is not None:
            q = q.filter(models.drift.Drift.detected_at >= since)
        q = q.group_by(models.drift.Drift.severity)
        results = q.all()
        return [{"severity": r.severity, "count": int(r.count)} for r in results]

    def count_by_account(self, db: Session, *, since: Optional[Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        q = db.query(models.drift.Drift.account_id.label("account_id"), func.count().label("count"))
        if since is not None:
            q = q.filter(models.drift.Drift.detected_at >= since)
        q = q.group_by(models.drift.Drift.account_id).order_by(func.count().desc()).limit(limit)
        results = q.all()
        return [{"account_id": r.account_id, "count": int(r.count)} for r in results]


crud_drift = CRUDDrift(models.drift.Drift)
