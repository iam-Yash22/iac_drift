from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScanOut(BaseModel):
    id: int
    scan_id: str
    account_id: int
    triggered_by_id: int | None = None
    triggered_by_username: str | None = None
    triggered_by_email: str | None = None
    status: str
    result: dict | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
