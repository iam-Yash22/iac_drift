"""Tracked resource API response schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.utils.validators import validate_resource_id

__all__ = ["ResourceRead", "ResourceCreate", "ResourceUpdate", "ResourceOut"]


class ResourcePayload(BaseModel):
    """Client-supplied resource fields; the database supplies the ID."""

    account_id: int = Field(..., description="Owning account identifier.")
    resource_id: str = Field(..., description="Cloud provider resource identifier.")
    resource_type: str = Field(..., description="Tracked resource type such as EC2, S3, or RDS.")
    name: str | None = Field(default=None, description="Display name or alias for the resource.")
    arn: str | None = Field(default=None, description="Cloud provider ARN, when available.")
    region: str | None = Field(default=None, description="Cloud region hosting the resource.")
    tags: dict[str, str] | None = Field(default=None, description="Current resource tags.")
    is_active: bool = Field(default=True, description="Whether the tracked resource is still active.")
    model_config = ConfigDict(extra="forbid")


class ResourceRead(BaseModel):
    """Schema returned by resource listing and detail endpoints."""

    id: int = Field(..., description="Database-generated resource identifier.")
    account_id: int = Field(..., description="Owning account identifier.")
    resource_id: str = Field(..., description="Cloud provider resource identifier.")
    resource_type: str = Field(..., description="Tracked resource type such as EC2, S3, or RDS.")
    name: str | None = Field(default=None, description="Display name or alias for the resource.")
    arn: str | None = Field(default=None, description="Cloud provider ARN, when available.")
    region: str | None = Field(default=None, description="Cloud region hosting the resource.")
    tags: dict[str, str] | None = Field(default=None, description="Current resource tags.")
    is_active: bool = Field(default=True, description="Whether the resource is still active.")
    created_at: datetime | None = Field(default=None, description="When the tracked resource was created.")
    updated_at: datetime | None = Field(default=None, description="When the tracked resource was last updated.")
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @classmethod
    def model_validate_resource_id(cls, value: str) -> str:
        return validate_resource_id(value)


ResourceCreate = ResourcePayload
ResourceUpdate = ResourcePayload
ResourceOut = ResourceRead
