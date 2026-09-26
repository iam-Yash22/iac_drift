"""Utilities for parsing Terraform plan JSON into canonical resource records.

This parser mirrors the state parser's normalization contract so webhook-triggered
Terraform plans can be compared against the same canonical drift model.
"""

import json
from dataclasses import asdict, dataclass

from app.core.constants import DriftType

__all__ = [
    "PlanResource",
    "parse_plan",
    "parse_plan_file",
    "load_plan",
    "normalize_resources",
    "parse_resources",
    "canonicalize_resource",
    "resource_to_dict",
]


@dataclass
class PlanResource:
    """Canonical Terraform plan record used for drift comparisons."""

    resource_type: str
    resource_name: str
    resource_id: str
    mode: str = "managed"
    provider: str | None = None
    instance_id: str | None = None
    actions: list | None = None
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


def _coerce_plan_payload(payload):
    if payload is None:
        return {}
    if isinstance(payload, (str, bytes)):
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        if not text.strip():
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid terraform plan JSON: {exc}") from exc
    if isinstance(payload, dict):
        return payload
    raise TypeError(f"Unsupported Terraform plan payload type: {type(payload).__name__}")


def _clean_string(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _resource_identity(resource_type, resource_name, mode):
    if mode == "data":
        return f"data.{resource_type}.{resource_name}"
    return f"{resource_type}.{resource_name}"


def canonicalize_resource(resource, source_file=None):
    """Normalize a single Terraform plan resource object into a canonical dict."""
    if not isinstance(resource, dict):
        raise TypeError(f"Expected plan resource dict, received {type(resource).__name__}")

    resource_type = _clean_string(resource.get("type")) or "unknown"
    resource_name = _clean_string(resource.get("name")) or "unknown"
    mode = _clean_string(resource.get("mode")) or "managed"
    provider = _clean_string(resource.get("provider_name")) or _clean_string(resource.get("provider"))
    actions = resource.get("change", {}).get("actions") if isinstance(resource.get("change"), dict) else None
    attributes = resource.get("change", {}).get("after") if isinstance(resource.get("change"), dict) else {}
    if not isinstance(attributes, dict):
        attributes = {}

    resource_id = _resource_identity(resource_type, resource_name, mode)
    if resource.get("index") is not None:
        resource_id = f"{resource_id}[{resource.get('index')}]"

    canonical = {
        "resource_type": resource_type,
        "resource_name": resource_name,
        "resource_id": resource_id,
        "mode": mode,
        "provider": provider,
        "instance_id": resource.get("index"),
        "actions": actions,
        "attributes": attributes,
        "source_file": source_file,
        "source_path": source_file,
        "source": {"file": source_file, "path": source_file},
        "raw": resource,
        "drift_type": DriftType.MODIFIED.value,
    }
    return canonical


def resource_to_dict(resource):
    """Return a plain dictionary representation of a canonical plan resource."""
    if isinstance(resource, PlanResource):
        return resource.to_dict()
    if isinstance(resource, dict):
        return resource
    raise TypeError(f"Unsupported resource payload: {type(resource).__name__}")


def _normalize_plan_document(document, source_file=None):
    payload = _coerce_plan_payload(document)
    resources = []

    if not isinstance(payload, dict):
        return resources

    resource_changes = payload.get("resource_changes")
    if isinstance(resource_changes, list):
        for item in resource_changes:
            if not isinstance(item, dict):
                continue
            resource = {
                "type": item.get("type"),
                "name": item.get("name"),
                "mode": item.get("mode"),
                "provider_name": item.get("provider_name"),
                "index": item.get("index"),
                "change": item.get("change"),
            }
            resources.append(canonicalize_resource(resource, source_file=source_file))
        return resources

    modules = payload.get("planned_values", {}).get("root_module", {}).get("resources")
    if isinstance(modules, list):
        for item in modules:
            if not isinstance(item, dict):
                continue
            resources.append(canonicalize_resource(item, source_file=source_file))
        return resources

    return resources


def parse_plan(raw_plan, source_file=None):
    """Parse Terraform plan JSON into a canonical list of resource dicts."""
    return _normalize_plan_document(raw_plan, source_file=source_file)


def parse_plan_file(path):
    """Load a Terraform plan file and normalize the JSON payload."""
    file_path = str(path)
    with open(file_path, "r", encoding="utf-8") as handle:
        plan_json = handle.read()
    return parse_plan(plan_json, source_file=file_path)


def load_plan(path_or_payload, source_file=None):
    """Compatibility loader for Terraform plan JSON represented as a file path or raw data."""
    if isinstance(path_or_payload, str):
        if path_or_payload.strip().startswith("{") or path_or_payload.strip().startswith("["):
            return parse_plan(path_or_payload, source_file=source_file)
        return parse_plan_file(path_or_payload)
    return parse_plan(path_or_payload, source_file=source_file)


def normalize_resources(raw_plan, source_file=None):
    """Alias used by plan-based drift workflows."""
    return parse_plan(raw_plan, source_file=source_file)


def parse_resources(raw_plan, source_file=None):
    """Alias for resource normalization entry points."""
    return parse_plan(raw_plan, source_file=source_file)
