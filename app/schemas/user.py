"""User registration, management, and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

__all__ = ["UserCreate", "UserUpdate", "UserRead"]


class UserCreate(BaseModel):
    """Public registration fields; the database supplies ID and role."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique login name.")
    email: EmailStr = Field(..., description="Email address used for login.")
    password: str = Field(..., min_length=8, max_length=128)
    model_config = ConfigDict(extra="forbid")

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("username cannot be empty")
        return value.lower()

class UserUpdate(BaseModel):
    """Schema used for partial user updates."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = Field(default=None)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = Field(default=None, min_length=1, max_length=50)
    model_config = ConfigDict(extra="forbid")

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("username cannot be empty")
        return value.lower()

class UserRead(BaseModel):
    """Safe response summary for a user, including the database id."""

    id: int
    username: str
    email: str
    role: str
    model_config = ConfigDict(from_attributes=True, extra="forbid")
