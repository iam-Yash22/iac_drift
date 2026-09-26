"""Account request and response schemas for account-related routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.validators import validate_account_id, validate_role_arn

__all__ = ["AccountCreate", "AccountRead", "AccountOut"]


class AccountBase(BaseModel):
    """Shared account fields."""

    name: str = Field(..., min_length=1, max_length=200, description="Account display name.")
    account_id: str = Field(..., description="AWS account identifier.")
    role_arn: str = Field(..., description="AWS IAM role ARN assumed for this account.")
    is_active: bool = Field(default=True, description="Whether the account is available for use.")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional provider-specific metadata.")

    @field_validator("account_id")
    @classmethod
    def validate_account_identifier(cls, value: str) -> str:
        return validate_account_id(value)

    @field_validator("role_arn")
    @classmethod
    def validate_role_arn_value(cls, value: str) -> str:
        return validate_role_arn(value)


class AccountCreate(AccountBase):
    """Schema used when creating a new account record."""

    model_config = ConfigDict(extra="forbid")


class AccountRead(AccountBase):
    """Schema returned for account records."""

    id: int = Field(..., description="Database-generated account identifier.")
    external_id: str = Field(..., description="External ID used when assuming the account role.")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional provider-specific metadata.",
        validation_alias="metadata_json",
    )
    created_at: datetime | None = Field(default=None, description="Time the account was created.")
    updated_at: datetime | None = Field(default=None, description="Last time the account record was updated.")
    model_config = ConfigDict(from_attributes=True, extra="forbid")


AccountOut = AccountRead
