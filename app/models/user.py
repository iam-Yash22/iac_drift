from sqlalchemy import Column, String
from app.models.base import AutoIncrementPKMixin, Base
from app.core.constants import Role


class User(Base, AutoIncrementPKMixin):
    __tablename__ = "users"

    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default=Role.VIEWER.value, nullable=False)
