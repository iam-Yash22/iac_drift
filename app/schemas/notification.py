from datetime import datetime

from pydantic import BaseModel


class ScanNotification(BaseModel):
    scan_id: str
    account_id: int
    account_name: str
    status: str
    triggered_by_username: str
    triggered_by_email: str
    triggered_at: datetime
