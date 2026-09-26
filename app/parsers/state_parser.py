"""Utilities for parsing Terraform state JSON into canonical resource records.

The parser intentionally keeps the dependency surface minimal: it only relies on
stdlib JSON and dataclasses for normalization, plus the shared constants module.
"""

import json
from dataclasses import dataclass, asdict

from app.core.constants import DriftType

__all__ = [
    "StateResource",
    "parse_state",
    "parse_state_file",
    "load_state",
    "normalize_resources",
    "parse_resources",
    "canonicalize_resource",
    "resource_to_dict",
]


@dataclass
class StateResource:
    """Canonical Terraform state record used for comparison and drift analysis."""

    resource_type: str
    resource_name: str
    resource_id: str
    mode: str = "managed"
    provider: str | None = None
    instance_id: str | None = None
    attributes: dict | None = None
    source_file: str | None = None
    source_path: str | None = None
    raw: dict | None = None

    def to_dict(self):
        data = asdict(self)
        data["source"] = {
            "file": self.source_file,
            "path": self.source_path,
        }
        return data


def _coerce_state_payload(payload):
    if payload is None:
        return {}
    if isinstance(payload, (str, bytes)):
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        if not text.strip():
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid terraform state JSON: {exc}") from exc
    if isinstance(payload, dict):
        return payload
    raise TypeError(f"Unsupported Terraform state payload type: {type(payload).__name__}")


def _clean_string(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _safe_attributes(value):
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    return {"value": value}


def _resource_address(resource):
    mode = _clean_string(resource.get("mode")) or "managed"
    resource_type = _clean_string(resource.get("type")) or "unknown"
    resource_name = _clean_string(resource.get("name")) or "unknown"
    if mode == "data":
        return f"data.{resource_type}.{resource_name}"
    return f"{resource_type}.{resource_name}"


def canonicalize_resource(resource, source_file=None):
    """Normalize one item from a Terraform state resource list into a canonical dict."""
    if not isinstance(resource, dict):
        raise TypeError(f"Expected resource dict, received {type(resource).__name__}")

    resource_type = _clean_string(resource.get("type"))
    resource_name = _clean_string(resource.get("name"))
    mode = _clean_string(resource.get("mode")) or "managed"
    provider = _clean_string(resource.get("provider"))
    instance_id = None

    attribute_block = {}
    instances = resource.get("instances") or []
    if isinstance(instances, list) and instances:
        instance = instances[0]
        if isinstance(instance, dict):
            if "index_key" in instance:
                instance_id = str(instance.get("index_key"))
            attribute_block = _safe_attributes(instance.get("attributes"))
            if provider is None:
                provider = _clean_string(instance.get("provider"))
    elif "attributes" in resource:
        attribute_block = _safe_attributes(resource.get("attributes"))

    if not resource_type:
        resource_type = "unknown"
    if not resource_name:
        resource_name = "unknown"

    resource_id = _resource_address({"mode": mode, "type": resource_type, "name": resource_name})
    if instance_id is not None and instance_id not in ("None", "none"):
        resource_id = f"{resource_id}[{instance_id}]"

    canonical = {
        "resource_type": resource_type,
        "resource_name": resource_name,
        "resource_id": resource_id,
        "mode": mode,
        "provider": provider,
        "instance_id": instance_id,
        "attributes": attribute_block,
        "source_file": source_file,
        "source_path": source_file,
        "source": {"file": source_file, "path": source_file},
        "raw": resource,
        "drift_type": DriftType.MODIFIED.value,
    }
    return canonical


def resource_to_dict(resource):
    """Return a plain dictionary representation of a canonical state resource."""
    if isinstance(resource, StateResource):
        return resource.to_dict()
    if isinstance(resource, dict):
        return resource
    raise TypeError(f"Unsupported resource payload: {type(resource).__name__}")


def _normalize_state_document(document, source_file=None):
    payload = _coerce_state_payload(document)

    resources = payload.get("resources") if isinstance(payload, dict) else []
    if not isinstance(resources, list):
        return []

    normalized = []
    for item in resources:
        if not isinstance(item, dict):
            continue
        normalized.append(canonicalize_resource(item, source_file=source_file))
    return normalized


def parse_state(raw_state, source_file=None):
    """Parse Terraform state JSON into a canonical list of resource dicts."""
    return _normalize_state_document(raw_state, source_file=source_file)


def parse_state_file(path):
    """Load a Terraform state file and normalize the JSON payload."""
    file_path = str(path)
    with open(file_path, "r", encoding="utf-8") as handle:
        state_json = handle.read()
    return parse_state(state_json, source_file=file_path)


def load_state(path_or_payload, source_file=None):
    """Compatibility loader for Terraform state JSON represented as a file path or raw data."""
    if isinstance(path_or_payload, str):
        if path_or_payload.strip().startswith("{") or path_or_payload.strip().startswith("["):
            return parse_state(path_or_payload, source_file=source_file)
        return parse_state_file(path_or_payload)
    return parse_state(path_or_payload, source_file=source_file)


def normalize_resources(raw_state, source_file=None):
    """Alias used by scanners and drift workflows to canonicalize Terraform state."""
    return parse_state(raw_state, source_file=source_file)


def parse_resources(raw_state, source_file=None):
    """Alias for resource normalization entry points."""
    return parse_state(raw_state, source_file=source_file)
