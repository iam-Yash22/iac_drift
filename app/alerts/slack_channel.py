from typing import Mapping, Any, Optional
import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import AlertChannel


class SlackChannel(AlertChannel):
    """Send alerts to Slack via an incoming webhook URL.

    The `target` argument is optional and may be used to override the channel
    (e.g. "#alerts") if the webhook accepts it.
    """

    def __init__(self, webhook_url: Optional[str] = None, client: Optional[httpx.Client] = None, max_attempts: int = 3, timeout: float = 5.0):
        self.webhook_url = webhook_url or os.getenv("ALERTS_SLACK_WEBHOOK")
        if not self.webhook_url:
            raise ValueError("webhook_url must be provided or ALERTS_SLACK_WEBHOOK env must be set")

        self.client = client or httpx.Client(timeout=timeout)
        self._max_attempts = max_attempts

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _post(self, payload: dict) -> httpx.Response:
        resp = self.client.post(self.webhook_url, json=payload)
        resp.raise_for_status()
        return resp

    def send(self, target: str, payload: Mapping[str, Any]) -> bool:
        """Build and post a Slack message payload.

        Accepts `text`, `blocks`, `attachments` in `payload`. If a
        `templates.render_slack` function exists it will be used to render the
        message.
        """
        text = payload.get("text") or payload.get("message") or ""
        blocks = payload.get("blocks")
        attachments = payload.get("attachments")

        # Optional: allow a templates module to render Slack payloads
        try:
            from . import templates

            if hasattr(templates, "render_slack"):
                rendered = templates.render_slack(payload)
                if isinstance(rendered, dict):
                    text = rendered.get("text", text)
                    blocks = rendered.get("blocks", blocks)
                    attachments = rendered.get("attachments", attachments)
        except Exception:
            # Fail quietly and fall back to provided payload values
            pass

        body: dict[str, Any] = {}
        if text:
            body["text"] = text
        if blocks:
            body["blocks"] = blocks
        if attachments:
            body["attachments"] = attachments

        # Some webhooks accept a `channel` override; include if provided.
        if target:
            body.setdefault("channel", target)

        try:
            resp = self._post(body)
            return 200 <= resp.status_code < 300
        except Exception:
            return False
