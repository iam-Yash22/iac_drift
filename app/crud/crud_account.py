import secrets
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.models.account import AwsAccount
from app.schemas.account import AccountCreate, AccountRead
from app.crud.base import CRUDBase


class CRUDAccount(CRUDBase[AwsAccount, AccountCreate, AccountRead]):
    """Account-specific CRUD operations.

    Used by onboarding and scan orchestration to persist and enumerate
    monitored AWS accounts. Assumes any encryption of `external_id`
    is performed before calling `create`.
    """

    def get_by_external_id(self, db: Session, *, encrypted_external_id: str) -> Optional[AwsAccount]:
        return (
            db.query(self.model)
            .filter(self.model.external_id == encrypted_external_id)
            .first()
        )

    def get_all(self, db: Session) -> List[AwsAccount]:
        accounts = db.query(self.model).order_by(self.model.id).all()
        changed = False
        for account in accounts:
            if not account.external_id:
                account.external_id = secrets.token_hex(16)
                changed = True

        if changed:
            db.commit()
            for account in accounts:
                db.refresh(account)

        return accounts

    def get_active(self, db: Session) -> List[AwsAccount]:
        return db.query(self.model).filter(self.model.is_active.is_(True)).all()

    def create(self, db: Session, *, obj_in: AccountCreate) -> AwsAccount:
        obj_data: dict[str, Any] = obj_in.dict() if hasattr(obj_in, "dict") else dict(obj_in)
        if "metadata" in obj_data:
            obj_data["metadata_json"] = obj_data.pop("metadata")
        obj_data.setdefault("external_id", secrets.token_hex(16))
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


crud_account = CRUDAccount(AwsAccount)
