import json
import urllib.request

import app.models.account
from app.auth.auth import create_access_token
from app.db.session import SessionLocal
from app.models.account import AwsAccount


db = SessionLocal()
account = db.get(AwsAccount, 1)
token = create_access_token(account.owner_id)
db.close()
headers = {"Authorization": f"Bearer {token}"}

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/accounts/1/scans",
    headers=headers,
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    scan = json.load(response)
print("TRIGGER_STATUS", response.status)
print("TRIGGER_BODY", json.dumps(scan))

scan_id = scan["id"]
request = urllib.request.Request(
    f"http://127.0.0.1:8000/api/v1/accounts/1/scans/{scan_id}/drift",
    headers=headers,
)
with urllib.request.urlopen(request, timeout=30) as response:
    drifts = json.load(response)
print("DRIFT_STATUS", response.status)
print("S3_DRIFT", json.dumps(next(item for item in drifts if item.get("resource_type") == "s3_bucket")))