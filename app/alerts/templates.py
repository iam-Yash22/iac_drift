from string import Template
import json
from typing import Mapping, Any, Dict, Tuple, Optional, Union


def _ensure_mapping(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(payload)


# Default templates
_SUBJECT_TPL = Template("Drift detected: $rule_name on $resource")
_BODY_TPL = Template(
    """
Rule: $rule_name
Resource: $resource
Severity: $severity

Details:
$details
"""
)


def render_email(record: Mapping[str, Any]) -> Union[Tuple[str, str, Optional[str]], Dict[str, str]]:
    """Render an email subject and body from a `DriftRecord`-shaped mapping.

    Returns either a tuple `(subject, text, html)` or a dict with the same keys.
    """
    r = _ensure_mapping(record)

    # Allow explicit override
    if "subject" in r or "body" in r or "text" in r:
        subject = str(r.get("subject") or r.get("title") or _SUBJECT_TPL.safe_substitute(r))
        text = str(r.get("body") or r.get("text") or _BODY_TPL.safe_substitute(r))
        html = r.get("html")
        return {"subject": subject, "text": text, "html": html}

    subject = _SUBJECT_TPL.safe_substitute(r)
    text = _BODY_TPL.safe_substitute(r)
    # Minimal HTML rendering
    html = "<pre>" + (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")) + "</pre>"
    return (subject, text, html)


def render_slack(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Render a Slack payload (text + Block Kit `blocks`) from a record."""
    r = _ensure_mapping(record)

    # If explicit blocks provided, pass through
    if "blocks" in r:
        return {"text": r.get("text", "Alert"), "blocks": r["blocks"]}

    title = r.get("title") or r.get("rule_name") or "Drift alert"
    details = r.get("details") or r.get("summary") or r.get("description") or ""

    # Build simple Block Kit message
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": details}},
    ]

    # Optionally include a fields block with important keys
    fields = []
    for k in ("resource", "severity", "rule_name"):
        if k in r:
            fields.append({"type": "mrkdwn", "text": f"*{k}*: {r[k]}"})
    if fields:
        blocks.append({"type": "section", "fields": fields})

    return {"text": title, "blocks": blocks}


def render_sns(record: Mapping[str, Any]) -> str:
    """Render a string message suitable for SNS payloads."""
    r = _ensure_mapping(record)
    # Prefer explicit message
    if "message" in r:
        return str(r["message"])

    subj = r.get("title") or r.get("rule_name") or "Drift alert"
    body = r.get("details") or r.get("summary") or r.get("description") or ""
    return f"{subj}\n\n{body}"


def render_webhook(record: Mapping[str, Any]) -> Any:
    """Render a JSON-serializable webhook payload.

    Returns a dict (or other JSON-serializable object). If the record already
    contains a `json` key that is a mapping, it is returned as-is.
    """
    r = _ensure_mapping(record)
    if "json" in r:
        return r["json"]

    payload = {
        "alert": {
            "rule": r.get("rule_name"),
            "resource": r.get("resource"),
            "severity": r.get("severity"),
            "details": r.get("details") or r.get("summary") or r.get("description"),
        },
        "meta": {k: v for k, v in r.items() if k not in ("rule_name", "resource", "severity", "details", "summary", "description")},
    }
    return payload
