from sqlalchemy.orm import Session

import app.models.report
import app.schemas.report
import app.models as models
import app.schemas as schemas
from app.crud.base import CRUDBase


class CRUDReport(CRUDBase[models.report.Report, schemas.report.ReportCreate, schemas.report.ReportUpdate]):
    """CRUD for report metadata persisted after report generation."""

    def create(self, db: Session, *, obj_in):
        obj_data = obj_in.dict() if hasattr(obj_in, "dict") else dict(obj_in)
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_s3_key(self, db: Session, *, s3_key):
        return db.query(self.model).filter(self.model.s3_key == s3_key).first()

    def list_by_requester(self, db: Session, *, requester, limit=100, offset=0):
        q = db.query(self.model).filter(self.model.requester == requester)
        return q.order_by(self.model.created_at.desc()).offset(offset).limit(limit).all()

    def remove_by_s3_key(self, db: Session, *, s3_key):
        obj = self.get_by_s3_key(db, s3_key=s3_key)
        if obj is None:
            return None
        db.delete(obj)
        db.commit()
        return obj


crud_report = CRUDReport(models.report.Report)
