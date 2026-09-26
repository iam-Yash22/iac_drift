from typing import Mapping, Any, Optional
import os

import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import AlertChannel


class EmailChannel(AlertChannel):
    """Send alerts via AWS SES.

    Example:
        channel = EmailChannel(source="alerts@example.com")
        channel.send("dest@example.com", {"subject": "Hi", "body": "..."})
    """

    def __init__(self, source: Optional[str] = None, ses_client: Optional[object] = None, max_attempts: int = 3):
        self.source = source or os.getenv("ALERTS_EMAIL_SOURCE")
        if not self.source:
            raise ValueError("source email must be provided via constructor or ALERTS_EMAIL_SOURCE env")

        self.ses = ses_client or boto3.client("ses")
        self._max_attempts = max_attempts

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _send_with_retry(self, target: str, subject: str, body_text: str, body_html: Optional[str] = None) -> dict:
        message = {
            "Source": self.source,
            "Destination": {"ToAddresses": [target]},
            "Message": {
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body_text}},
            },
        }
        if body_html:
            message["Message"]["Body"]["Html"] = {"Data": body_html}

        return self.ses.send_email(**message)

    def send(self, target: str, payload: Mapping[str, Any]) -> bool:
        """Send the payload to `target` email address.

        Payload can either contain `subject` and `body` keys, or an arbitrary
        structure consumed by `alerts.templates` if available.
        """
        # Prefer explicit keys
        subject = str(payload.get("subject") or payload.get("title") or "Alert")
        body_text = str(payload.get("body") or payload.get("text") or "")
        body_html = None

        # Attempt to use templates module if it exists and provides a renderer
        try:
            from . import templates  # local import to avoid hard dependency

            if hasattr(templates, "render_email"):
                rendered = templates.render_email(payload)
                # Expect a tuple (subject, text, html) or dict
                if isinstance(rendered, tuple):
                    subject, body_text, body_html = rendered
                elif isinstance(rendered, dict):
                    subject = rendered.get("subject", subject)
                    body_text = rendered.get("text", body_text)
                    body_html = rendered.get("html") or rendered.get("body_html")
        except Exception:
            # If templates import or rendering fails, fall back to provided keys
            pass

        try:
            resp = self._send_with_retry(target, subject, body_text, body_html)
            return bool(resp.get("MessageId"))
        except Exception:
            return False
