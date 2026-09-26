from sqlalchemy.orm import Session

import app.models.alert
import app.schemas.alert
import app.models as models
import app.schemas as schemas
from app.crud.base import CRUDBase


class CRUDAlertRule(CRUDBase[models.alert.AlertRule, schemas.alert.AlertRuleCreate, schemas.alert.AlertRuleUpdate]):
    """CRUD for alert rule configuration."""

    def get_by_name(self, db: Session, *, name: str):
        return db.query(self.model).filter(self.model.name == name).first()

    def list_rules(self, db: Session, *, active_only=True):
        q = db.query(self.model)
        if active_only:
            q = q.filter(self.model.active == True)
        return q.all()


class CRUDAlertAudit(CRUDBase[models.alert.AlertAudit, schemas.alert.AlertAuditCreate, schemas.alert.AlertAuditUpdate]):
    """CRUD for notification-send audit records."""

    def record(self, db: Session, *, audit_in):
        obj_data = audit_in.dict() if hasattr(audit_in, "dict") else dict(audit_in)
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def list_for_rule(self, db: Session, *, rule_id, since=None, limit=100):
        q = db.query(self.model).filter(self.model.rule_id == rule_id)
        if since is not None:
            q = q.filter(self.model.attempted_at >= since)
        return q.order_by(self.model.attempted_at.desc()).limit(limit).all()


crud_alert_rule = CRUDAlertRule(models.alert.AlertRule)
crud_alert_audit = CRUDAlertAudit(models.alert.AlertAudit)
