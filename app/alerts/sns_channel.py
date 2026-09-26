from typing import Mapping, Any, Optional
import os

import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import AlertChannel


class SNSChannel(AlertChannel):
    """Publish messages to an AWS SNS topic.

    The `target` argument to `send` is expected to be a Topic ARN. If omitted,
    the `topic_arn` provided at construction or via `ALERTS_SNS_TOPIC_ARN` env
    var will be used.
    """

    def __init__(self, topic_arn: Optional[str] = None, sns_client: Optional[object] = None, max_attempts: int = 3):
        self.topic_arn = topic_arn or os.getenv("ALERTS_SNS_TOPIC_ARN")
        self.sns = sns_client or boto3.client("sns")
        self._max_attempts = max_attempts

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _publish(self, topic_arn: str, message: str, subject: Optional[str] = None, message_attributes: Optional[dict] = None) -> dict:
        kwargs = {"TopicArn": topic_arn, "Message": message}
        if subject:
            kwargs["Subject"] = subject
        if message_attributes:
            kwargs["MessageAttributes"] = message_attributes

        return self.sns.publish(**kwargs)

    def send(self, target: str, payload: Mapping[str, Any]) -> bool:
        """Publish `payload` to SNS.

        Payload may contain `message` and optional `subject`. If a
        `templates.render_sns` function is available it will be used to render
        the message body.
        """
        topic = target or self.topic_arn
        if not topic:
            raise ValueError("topic ARN must be provided as target or configured via ALERTS_SNS_TOPIC_ARN")

        message = str(payload.get("message") or payload.get("body") or "")
        subject = payload.get("subject")
        message_attributes = payload.get("message_attributes")

        # Allow optional templates.render_sns to shape the message
        try:
            from . import templates

            if hasattr(templates, "render_sns"):
                rendered = templates.render_sns(payload)
                if isinstance(rendered, dict):
                    message = rendered.get("message", message)
                    subject = rendered.get("subject", subject)
                    message_attributes = rendered.get("message_attributes", message_attributes)
                elif isinstance(rendered, str):
                    message = rendered
        except Exception:
            pass

        try:
            resp = self._publish(topic, message, subject, message_attributes)
            return bool(resp.get("MessageId"))
        except Exception:
            return False
