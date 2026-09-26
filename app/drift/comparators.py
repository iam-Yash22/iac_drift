from typing import Any, Callable, Dict, Mapping, Sequence


_ALLOWED_RESOURCE_TYPES = {
    "ec2_instance",
    "aws_instance",
    "aws_ebs_volume",
    "aws_s3_bucket",
    "aws_db_instance",
    "aws_lambda_function",
    "aws_security_group",
    "aws_route53_record",
    "aws_iam_role",
    "aws_iam_policy",
    "aws_vpc",
    "aws_subnet",
    "aws_ebs_snapshot",
    "aws_efs_file_system",
}


_DEFAULT_IGNORE_FIELDS = (
    "id",
    "arn",
    "owner_id",
    "created_at",
    "creation_date",
    "last_modified",
    "last_updated",
    "status",
    "state",
    "tags_all",
    "user_data",
    "public_ip",
    "private_ip",
    "ipv6_addresses",
    "network_interface",
    "placement_group",
    "availability_zone",
    "vpc_security_group_ids",
    "security_groups",
    "root_block_device",
    "ebs_optimized",
    "ami_launch_index",
    "launch_template",
    "instance_id",
    "domain_name",
    "hosted_zone_id",
    "bucket_domain_name",
    "bucket_regional_domain_name",
    "policy",
    "website",
    "logging",
    "versioning",
    "encryption",
    "cors",
    "lifecycle_rule",
    "replication_configuration",
    "request_payer",
    "force_destroy",
    "object_lock_configuration",
    "ownership_controls",
    "public_access_block",
    "acl",
    "grant",
)


_RESOURCE_FIELD_RULES: Dict[str, Dict[str, Sequence[str]]] = {
    "ec2_instance": {
        "ignore": (
            "ami_launch_index",
            "instance_id",
            "public_ip",
            "private_ip",
            "ipv6_addresses",
            "network_interface",
            "placement_group",
            "availability_zone",
            "vpc_security_group_ids",
            "root_block_device",
            "ebs_optimized",
            "security_groups",
            "state",
            "arn",
            "tags_all",
        ),
    },
    "aws_instance": {
        "ignore": (
            "ami_launch_index",
            "instance_id",
            "public_ip",
            "private_ip",
            "ipv6_addresses",
            "network_interface",
            "placement_group",
            "availability_zone",
            "vpc_security_group_ids",
            "root_block_device",
            "ebs_optimized",
            "security_groups",
            "state",
            "arn",
            "tags_all",
        ),
    },
    "aws_s3_bucket": {
        "ignore": (
            "bucket_domain_name",
            "bucket_regional_domain_name",
            "hosted_zone_id",
            "arn",
            "bucket_regional_domain_name",
            "policy",
            "website",
            "logging",
            "versioning",
            "encryption",
            "cors",
            "lifecycle_rule",
            "replication_configuration",
            "request_payer",
            "force_destroy",
            "public_access_block",
            "ownership_controls",
            "object_lock_configuration",
            "grant",
            "acl",
        ),
    },
    "aws_db_instance": {
        "ignore": (
            "arn",
            "endpoint",
            "address",
            "port",
            "status",
            "hosted_zone_id",
            "db_instance_arn",
        ),
    },
    "aws_lambda_function": {
        "ignore": (
            "arn",
            "version",
            "qualified_arn",
            "last_modified",
            "function_name",
            "invoke_arn",
            "state",
            "tags_all",
        ),
    },
    "aws_vpc": {
        "ignore": (
            "arn",
            "cidr_block_association_id",
            "default_security_group_id",
            "default_route_table_id",
            "owner_id",
            "enable_dns_hostnames",
            "enable_dns_support",
        ),
    },
}


def _to_lower_sequence(values: Sequence[str]) -> set[str]:
    return {str(value).lower() for value in values}


def _normalize_map(mapping: Mapping[str, Any]) -> Dict[str, Any]:
    return {str(key): value for key, value in mapping.items()}


def _strip_ignored_fields(payload: Mapping[str, Any], resource_type: str) -> Dict[str, Any]:
    normalized = _normalize_map(payload)
    rules = _RESOURCE_FIELD_RULES.get(resource_type.lower(), {})
    ignored = _to_lower_sequence(rules.get("ignore", ())) | _to_lower_sequence(_DEFAULT_IGNORE_FIELDS)
    allowed = _to_lower_sequence(rules.get("allow", ()))

    filtered: Dict[str, Any] = {}
    for key, value in normalized.items():
        lowered = key.lower()
        if lowered in ignored:
            continue
        if allowed and lowered not in allowed:
            continue
        filtered[key] = value
    return filtered


def ignored_fields(resource_type: str) -> set[str]:
    rules = _RESOURCE_FIELD_RULES.get((resource_type or "").lower(), {})
    return _to_lower_sequence(rules.get("ignore", ()))


def _compare_nested_values(left: Any, right: Any) -> bool:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return left == right
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        if len(left) != len(right):
            return False
        return all(_compare_nested_values(a, b) for a, b in zip(left, right))
    if isinstance(left, set) and isinstance(right, set):
        return left == right
    return left == right


def compare_generic_fields(desired: Any, actual: Any) -> bool:
    if isinstance(desired, Mapping) and isinstance(actual, Mapping):
        return _compare_nested_values(
            _normalize_map(desired),
            _normalize_map(actual),
        )
    return _compare_nested_values(desired, actual)


def compare_s3_bucket_fields(desired: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    desired_filtered = _strip_ignored_fields(desired, "aws_s3_bucket")
    actual_filtered = _strip_ignored_fields(actual, "aws_s3_bucket")
    return desired_filtered == actual_filtered


def compare_instance_fields(desired: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    desired_filtered = _strip_ignored_fields(desired, "aws_instance")
    actual_filtered = _strip_ignored_fields(actual, "aws_instance")
    return desired_filtered == actual_filtered


def compare_db_instance_fields(desired: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    desired_filtered = _strip_ignored_fields(desired, "aws_db_instance")
    actual_filtered = _strip_ignored_fields(actual, "aws_db_instance")
    return desired_filtered == actual_filtered


def compare_lambda_fields(desired: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    desired_filtered = _strip_ignored_fields(desired, "aws_lambda_function")
    actual_filtered = _strip_ignored_fields(actual, "aws_lambda_function")
    return desired_filtered == actual_filtered


def compare_vpc_fields(desired: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    desired_filtered = _strip_ignored_fields(desired, "aws_vpc")
    actual_filtered = _strip_ignored_fields(actual, "aws_vpc")
    return desired_filtered == actual_filtered


RESOURCE_TYPE_COMPARATORS: Dict[str, Callable[[Mapping[str, Any], Mapping[str, Any]], bool]] = {
    "aws_instance": compare_instance_fields,
    "aws_ebs_volume": compare_generic_fields,
    "aws_s3_bucket": compare_s3_bucket_fields,
    "aws_db_instance": compare_db_instance_fields,
    "aws_lambda_function": compare_lambda_fields,
    "aws_security_group": compare_generic_fields,
    "aws_route53_record": compare_generic_fields,
    "aws_iam_role": compare_generic_fields,
    "aws_iam_policy": compare_generic_fields,
    "aws_vpc": compare_vpc_fields,
    "aws_subnet": compare_generic_fields,
    "aws_ebs_snapshot": compare_generic_fields,
    "aws_efs_file_system": compare_generic_fields,
}


def get_resource_comparator(resource_type: str) -> Callable[[Any, Any], bool]:
    key = (resource_type or "").lower()
    if key in _ALLOWED_RESOURCE_TYPES:
        return RESOURCE_TYPE_COMPARATORS.get(key, compare_generic_fields)
    return compare_generic_fields


def compare_values(desired: Any, actual: Any, resource_type: str = "") -> bool:
    """Compare values for a given resource type while filtering AWS-generated noise."""
    comparator = get_resource_comparator(resource_type)
    if isinstance(desired, Mapping) and isinstance(actual, Mapping):
        return comparator(desired, actual)
    return comparator(desired, actual)


def compare_resource_fields(resource_type: str, desired: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    comparator = get_resource_comparator(resource_type)
    return comparator(desired, actual)


__all__ = [
    "RESOURCE_TYPE_COMPARATORS",
    "compare_values",
    "compare_resource_fields",
    "compare_generic_fields",
    "compare_s3_bucket_fields",
    "compare_instance_fields",
    "compare_db_instance_fields",
    "compare_lambda_fields",
    "compare_vpc_fields",
    "get_resource_comparator",
]
