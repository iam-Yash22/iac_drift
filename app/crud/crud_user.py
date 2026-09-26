from sqlalchemy.orm import Session

import app.models.user
import app.schemas.user
from app.crud.base import CRUDBase
from app.security.hashing import hash_password


class CRUDUser(CRUDBase[app.models.user.User, app.schemas.user.UserCreate, app.schemas.user.UserUpdate]):
    """User-specific CRUD operations.

    Provides `get_by_email` for authentication and overrides `create`
    to hash the password before persisting.
    """

    def get_by_email(self, db: Session, *, email: str):
        return self.get_by_login(db, login=email)

    def get_by_login(self, db: Session, *, login: str):
        normalized_login = login.strip().lower()
        return db.query(self.model).filter(
            (self.model.username == normalized_login) | (self.model.email == normalized_login)
        ).first()

    def create(self, db: Session, *, obj_in: app.schemas.user.UserCreate):
        obj_data = obj_in.dict() if hasattr(obj_in, "dict") else dict(obj_in)

        password = obj_data.pop("password", None)
        if password is not None:
            obj_data["hashed_password"] = hash_password(password)

        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, *, db_obj, obj_in):
        obj_data = obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, "model_dump") else obj_in.dict(exclude_unset=True)
        password = obj_data.pop("password", None)
        if password is not None:
            obj_data["hashed_password"] = hash_password(password)
        return super().update(db, db_obj=db_obj, obj_in=obj_data)


# Module-level instance to be used by other modules (common pattern)
crud_user = CRUDUser(app.models.user.User)
