from typing import Mapping, Any, Optional
import json
import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import AlertChannel


class WebhookChannel(AlertChannel):
    """POST a signed JSON payload to a customer-provided URL.

    The payload is signed using an HMAC secret and the signature is placed in
    a header (default `X-Signature`). If `security.hashing` provides a
    compatible signing function it will be used; otherwise a stdlib HMAC
    (SHA256) is used as a fallback.
    """

    def __init__(self, secret: Optional[str] = None, client: Optional[httpx.Client] = None, max_attempts: int = 3, timeout: float = 5.0, signature_header: str = "X-Signature"):
        self.secret = secret or os.getenv("ALERTS_WEBHOOK_SECRET")
        if not self.secret:
            # Allow sending unsigned if explicitly intended by passing None
            # but warn via exception to force explicit configuration.
            raise ValueError("webhook secret must be provided via constructor or ALERTS_WEBHOOK_SECRET env")

        self.client = client or httpx.Client(timeout=timeout)
        self._max_attempts = max_attempts
        self.signature_header = signature_header

    def _compute_signature(self, body_bytes: bytes) -> str:
        # Try to use security.hashing if available
        try:
            from app.security import hashing

            # Common helper names: hmac_sign, sign_hmac
            if hasattr(hashing, "hmac_sign"):
                return hashing.hmac_sign(body_bytes, self.secret)
            if hasattr(hashing, "sign_hmac"):
                return hashing.sign_hmac(body_bytes, self.secret)
        except Exception:
            pass

        # Fallback to stdlib HMAC-SHA256 hex digest
        import hmac as _hmac
        import hashlib as _hashlib

        sig = _hmac.new(self.secret.encode("utf-8"), body_bytes, _hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _post(self, url: str, body: bytes, headers: dict) -> httpx.Response:
        resp = self.client.post(url, content=body, headers=headers)
        resp.raise_for_status()
        return resp

    def send(self, target: str, payload: Mapping[str, Any]) -> bool:
        """Send a signed JSON payload to `target` URL.

        `payload` may be the JSON body itself or contain a `json` key. If a
        `templates.render_webhook` function exists it will be used to produce
        the JSON body.
        """
        if not target:
            return False

        body_obj: Any

        # Allow templates to render the payload if present
        try:
            from . import templates

            if hasattr(templates, "render_webhook"):
                rendered = templates.render_webhook(payload)
                # rendered can be a dict or JSON string
                if isinstance(rendered, (dict, list)):
                    body_obj = rendered
                elif isinstance(rendered, str):
                    body_obj = json.loads(rendered)
                else:
                    body_obj = payload.get("json", payload)
            else:
                body_obj = payload.get("json", payload)
        except Exception:
            body_obj = payload.get("json", payload)

        try:
            body_bytes = json.dumps(body_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        except Exception:
            # If body_obj isn't JSON-serializable, fall back to str()
            body_bytes = str(body_obj).encode("utf-8")

        signature = self._compute_signature(body_bytes)

        headers = {
            "Content-Type": "application/json",
            self.signature_header: signature,
        }

        try:
            resp = self._post(target, body_bytes, headers)
            return 200 <= resp.status_code < 300
        except Exception:
            return False
