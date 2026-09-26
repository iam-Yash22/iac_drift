"""Canonical normalization layer for Terraform and live AWS resource payloads.

This module reconciles heterogeneous resource dictionaries from HCL, Terraform
state, Terraform plan, and AWS describe APIs into a consistent shape suitable
to be consumed by drift comparison logic.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional

from app.core.constants import DriftType
from app.utils.aws_arn import arn_to_resource_key

__all__ = [
    "NormalizedResource",
    "normalize_resource",
    "normalize_resources",
    "normalize_collection",
    "canonicalize",
    "resource_key",
    "to_dict",
]


@dataclass
class NormalizedResource:
    """Canonical resource representation used by the drift engine."""

    resource_type: str
    resource_name: str
    resource_id: str
    provider: Optional[str] = None
    mode: str = "managed"
    source_file: Optional[str] = None
    source_path: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    drift_type: str = DriftType.MODIFIED.value
    tags: Dict[str, str] = field(default_factory=dict)
    arn: Optional[str] = None
    region: Optional[str] = None
    account_id: Optional[str] = None
    line: Optional[int] = None
    line_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["source"] = {
            "file": self.source_file,
            "path": self.source_path,
            "line": self.line,
            "line_number": self.line_number,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }
        return data


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    return value


def _as_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _pick_first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _coalesce_key(resource: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = resource.get(key)
        if value is not None:
            return value
    return None


def _resource_name_from_id(resource_id: Any) -> str:
    if resource_id is None:
        return "unknown"
    text = str(resource_id)
    if "." in text:
        return text.rsplit(".", 1)[-1]
    return text


def _infer_type(resource: Dict[str, Any], fallback: str = "unknown") -> str:
    if resource.get("FunctionName") or resource.get("FunctionArn"):
        return "lambda_function"
    if resource.get("EnvironmentId") or resource.get("EnvironmentArn"):
        return "elastic_beanstalk_environment"
    candidates = [
        resource.get("resource_type"),
        resource.get("type"),
        resource.get("kind"),
        resource.get("name"),
        resource.get("resourceKind"),
        resource.get("ResourceType"),
        resource.get("resourceType"),
    ]
    for value in candidates:
        clean = _clean(value)
        if clean:
            return str(clean)
    if resource.get("InstanceId") or resource.get("InstanceType"):
        return "ec2_instance"
    if resource.get("GroupId") or resource.get("GroupName"):
        return "security_group"
    if resource.get("DBInstanceIdentifier") or resource.get("DbiResourceId"):
        return "rds_instance"
    if resource.get("RoleName") or resource.get("AssumeRolePolicyDocument"):
        return "iam_role"
    if resource.get("BucketArn") or (resource.get("Name") and resource.get("CreationDate")):
        return "s3_bucket"
    return fallback


def _infer_name(resource: Dict[str, Any], fallback: str = "unknown") -> str:
    named_candidates = [
        resource.get("resource_name"),
        resource.get("name"),
        resource.get("ResourceName"),
        resource.get("RoleName"),
        resource.get("GroupName"),
        resource.get("DBInstanceIdentifier"),
        resource.get("Name"),
        resource.get("FunctionName"),
        resource.get("EnvironmentName"),
    ]
    for value in named_candidates:
        clean = _clean(value)
        if clean:
            return str(clean)

    tags = resource.get("Tags")
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict) and tag.get("Key") == "Name" and _clean(tag.get("Value")):
                return str(_clean(tag["Value"]))

    for value in (resource.get("InstanceId"), resource.get("resourceId"), resource.get("id")):
        clean = _clean(value)
        if clean:
            return str(clean)
    if isinstance(resource.get("resource_id"), str):
        return _resource_name_from_id(resource["resource_id"])
    return fallback


def _infer_resource_id(resource: Dict[str, Any], resource_type: str, resource_name: str) -> str:
    if resource_type == "lambda_function":
        existing = (
            _clean(resource.get("FunctionName"))
            or _clean(resource.get("resource_id"))
            or _clean(resource.get("id"))
            or _clean(resource.get("ResourceId"))
            or _clean(resource.get("FunctionArn"))
            or _clean(resource.get("Arn"))
        )
    elif resource_type == "elastic_beanstalk_environment":
        existing = (
            _clean(resource.get("EnvironmentId"))
            or _clean(resource.get("resource_id"))
            or _clean(resource.get("id"))
            or _clean(resource.get("ResourceId"))
            or _clean(resource.get("EnvironmentArn"))
            or _clean(resource.get("Arn"))
        )
    else:
        existing = (
            _clean(resource.get("resource_id"))
            or _clean(resource.get("id"))
            or _clean(resource.get("ResourceId"))
            or _clean(resource.get("InstanceId"))
            or _clean(resource.get("GroupId"))
            or _clean(resource.get("DbiResourceId"))
            or _clean(resource.get("DBInstanceIdentifier"))
            or _clean(resource.get("RoleId"))
            or _clean(resource.get("Arn"))
            or _clean(resource.get("FunctionArn"))
            or _clean(resource.get("BucketArn"))
            or _clean(resource.get("FunctionName"))
            or _clean(resource.get("EnvironmentArn"))
            or _clean(resource.get("EnvironmentId"))
            or (_clean(resource.get("Name")) if resource_type == "s3_bucket" else None)
        )
    if existing:
        return str(existing)
    if resource_type and resource_name:
        return f"{resource_type}.{resource_name}"
    return "unknown"


def _attr_payload(resource: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("attributes", "properties", "data", "details", "raw"):
        payload = resource.get(key)
        if isinstance(payload, dict):
            return payload
    return _as_mapping(resource)


def _tags_payload(resource: Dict[str, Any]) -> Dict[str, str]:
    tags = resource.get("tags")
    if isinstance(tags, dict):
        return {str(k): str(v) for k, v in tags.items()}
    raw_tags = resource.get("Tags")
    if isinstance(raw_tags, dict):
        return {str(k): str(v) for k, v in raw_tags.items()}
    if isinstance(raw_tags, list):
        return {
            str(item["Key"]): str(item["Value"])
            for item in raw_tags
            if isinstance(item, dict) and "Key" in item and "Value" in item
        }
    return {}


def _source_info(resource: Dict[str, Any]) -> Dict[str, Any]:
    source = resource.get("source")
    if isinstance(source, dict):
        return source
    return {
        "file": resource.get("source_file") or resource.get("source_path") or resource.get("file"),
        "path": resource.get("source_path") or resource.get("source_file") or resource.get("file"),
        "line": resource.get("line") or resource.get("line_number"),
        "line_number": resource.get("line_number") or resource.get("line"),
        "start_line": resource.get("start_line"),
        "end_line": resource.get("end_line"),
    }


def _applicable_arn(resource: Dict[str, Any]) -> Optional[str]:
    arn = _coalesce_key(
        resource,
        "arn",
        "ARN",
        "Arn",
        "BucketArn",
        "FunctionArn",
        "EnvironmentArn",
    )
    if arn:
        return str(arn)
    if isinstance(resource.get("attributes"), dict):
        candidate = resource["attributes"].get("arn") or resource["attributes"].get("ARN")
        if candidate:
            return str(candidate)
    return None


def _region(resource: Dict[str, Any]) -> Optional[str]:
    region = _coalesce_key(resource, "region", "Region", "AvailabilityZone")
    if region:
        return str(region)
    attributes = resource.get("attributes")
    if isinstance(attributes, dict):
        region = attributes.get("region") or attributes.get("Region")
        if region:
            return str(region)
    return None


def _account_id(resource: Dict[str, Any], arn: Optional[str]) -> Optional[str]:
    account_id = _coalesce_key(resource, "account_id", "AccountId")
    if account_id:
        return str(account_id)
    if arn:
        try:
            return arn_to_resource_key(arn).get("account_id")
        except Exception:
            return None
    return None


def _line_meta(resource: Dict[str, Any]) -> Dict[str, Optional[int]]:
    info = _source_info(resource)
    return {
        "line": info.get("line"),
        "line_number": info.get("line_number"),
        "start_line": info.get("start_line"),
        "end_line": info.get("end_line"),
    }


def resource_key(resource: Dict[str, Any]) -> str:
    """Build a stable key that matches the normalized resource identity."""
    resource_type = _infer_type(resource)
    resource_name = _infer_name(resource)
    resource_id = _infer_resource_id(resource, resource_type, resource_name)
    return f"{resource_type}.{resource_name}:{resource_id}"


def normalize_resource(resource: Dict[str, Any]) -> NormalizedResource:
    """Convert a heterogeneous resource payload into the canonical normalized shape."""
    if resource is None:
        raise ValueError("Resource payload cannot be None")
    if not isinstance(resource, dict):
        raise TypeError(f"Expected dict resource payload, received {type(resource).__name__}")

    resource_type = _infer_type(resource)
    resource_name = _infer_name(resource)
    resource_id = _infer_resource_id(resource, resource_type, resource_name)
    if resource_type in {"lambda_function", "elastic_beanstalk_environment"}:
        required = {
            "lambda_function": ("FunctionName", "FunctionArn"),
            "elastic_beanstalk_environment": ("EnvironmentId", "EnvironmentArn", "EnvironmentName"),
        }[resource_type]
        missing = [key for key in required if not _clean(resource.get(key))]
        if missing:
            raise ValueError(
                f"{resource_type} is missing required AWS fields: {', '.join(missing)}"
            )
    source = _source_info(resource)
    arn = _applicable_arn(resource)
    region = _region(resource)
    account_id = _account_id(resource, arn)
    attributes = _attr_payload(resource)
    tags = _tags_payload(resource)
    metadata = _line_meta(resource)

    normalized = NormalizedResource(
        resource_type=str(resource_type),
        resource_name=str(resource_name),
        resource_id=str(resource_id),
        provider=_pick_first(resource.get("provider"), resource.get("provider_name"), resource.get("cloud_provider")),
        mode=str(_clean(_coalesce_key(resource, "mode", "Mode")) or "managed"),
        source_file=source.get("file") or source.get("path"),
        source_path=source.get("path") or source.get("file"),
        attributes=attributes,
        raw=resource,
        drift_type=str(_clean(resource.get("drift_type")) or DriftType.MODIFIED.value),
        tags=tags,
        arn=arn,
        region=region,
        account_id=account_id,
        line=metadata.get("line"),
        line_number=metadata.get("line_number"),
        start_line=metadata.get("start_line"),
        end_line=metadata.get("end_line"),
    )
    return normalized


def normalize_resources(resources: Iterable[Dict[str, Any]]) -> List[NormalizedResource]:
    """Normalize a collection of resource payloads into canonical records."""
    if resources is None:
        return []
    normalized: List[NormalizedResource] = []
    for item in resources:
        if item is None:
            continue
        if isinstance(item, NormalizedResource):
            normalized.append(item)
            continue
        if not isinstance(item, dict):
            continue
        normalized.append(normalize_resource(item))
    return normalized


def normalize_collection(payload: Any) -> List[NormalizedResource]:
    """Normalize a list, tuple, or nested mapping of resources into canonical records."""
    if payload is None:
        return []

    if isinstance(payload, (NormalizedResource,)):
        return [payload]

    if isinstance(payload, dict):
        if any(
            key in payload
            for key in (
                "resource_id",
                "id",
                "InstanceId",
                "GroupId",
                "GroupName",
                "Name",
                "Arn",
                "ARN",
                "FunctionName",
                "EnvironmentId",
                "EnvironmentName",
                "BucketArn",
                "FunctionArn",
                "EnvironmentArn",
            )
        ):
            return normalize_resources([payload])

        resources: List[NormalizedResource] = []
        for value in payload.values():
            if isinstance(value, dict):
                resources.extend(normalize_collection(value))
            elif isinstance(value, (list, tuple, set)):
                resources.extend(normalize_collection(value))
        return resources

    if isinstance(payload, (list, tuple, set)):
        resources: List[NormalizedResource] = []
        for item in payload:
            if item is None:
                continue
            if isinstance(item, NormalizedResource):
                resources.append(item)
                continue
            if isinstance(item, dict):
                if any(
                    key in item
                    for key in (
                        "resource_id",
                        "id",
                        "InstanceId",
                        "GroupId",
                        "GroupName",
                        "Name",
                        "Arn",
                        "ARN",
                        "FunctionName",
                        "EnvironmentId",
                        "EnvironmentName",
                        "BucketArn",
                        "FunctionArn",
                        "EnvironmentArn",
                    )
                ):
                    resources.extend(normalize_resources([item]))
                else:
                    resources.extend(normalize_collection(item))
                continue
            if isinstance(item, (list, tuple, set)):
                resources.extend(normalize_collection(item))
        return resources

    return []


def canonicalize(resource: Dict[str, Any]) -> NormalizedResource:
    """Compatibility alias for normalization that mirrors the drift engine contract."""
    return normalize_resource(resource)


def to_dict(resource: Any) -> Dict[str, Any]:
    """Serialize a resource-like payload to a plain dictionary."""
    if isinstance(resource, NormalizedResource):
        return resource.to_dict()
    if isinstance(resource, dict):
        return resource
    if hasattr(resource, "to_dict"):
        return resource.to_dict()
    return {}
