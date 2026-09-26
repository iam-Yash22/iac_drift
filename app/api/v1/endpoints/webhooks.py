"""Webhook ingestion endpoints."""

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.schemas import drift as drift_schema
from app.services import drift_orchestrator
from app.security import hashing

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/terraform-plan", status_code=status.HTTP_202_ACCEPTED)
async def ingest_terraform_plan(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> dict[str, str]:
    """Accept an HMAC-signed Terraform plan payload and hand it to the drift orchestrator."""
    payload = await request.body()
    if not x_signature or not hashing.verify_hmac_signature(payload, x_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    drift_orchestrator.ingest_plan_payload(payload)
    return {"status": "accepted"}
