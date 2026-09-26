from typing import Any, Dict, Generator, List, Optional

import botocore.exceptions as botocore_exceptions
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import app.core.constants as constants
from app.core.logging_config import get_logger


logger = get_logger(__name__)


# Retry configuration for AWS API calls
_retry_decorator = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((botocore_exceptions.ClientError, botocore_exceptions.EndpointConnectionError)),
)


def _paginate(client: Any, operation_name: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
    """Yield pages for the given operation using paginator if available.

    Falls back to a single operation call when a paginator isn't available.
    """
    try:
        paginator = client.get_paginator(operation_name)
    except (ValueError, AttributeError):
        # no paginator available, call the operation directly
        method = getattr(client, operation_name, None)
        if not method:
            raise AttributeError(f"Client has no operation {operation_name}")
        yield method(**kwargs)
        return

    for page in paginator.paginate(**kwargs):
        yield page


@_retry_decorator
def fetch_ec2_instances(ec2_client: Any, filters: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Return a flat list of EC2 instance dicts (raw boto3 response objects)."""
    instances: List[Dict[str, Any]] = []
    for page in _paginate(ec2_client, "describe_instances", Filters=filters or []):
        for reservation in page.get("Reservations", []):
            instances.extend(reservation.get("Instances", []))
    return instances


@_retry_decorator
def fetch_security_groups(ec2_client: Any, group_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Return security groups in the canonical shape used by Terraform comparison."""
    def normalize_permissions(permissions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for permission in permissions:
            normalized.append({
                "cidr_blocks": [item["CidrIp"] for item in permission.get("IpRanges", []) if "CidrIp" in item],
                "description": permission.get("Description", ""),
                "from_port": permission.get("FromPort", 0),
                "ipv6_cidr_blocks": [item["CidrIpv6"] for item in permission.get("Ipv6Ranges", []) if "CidrIpv6" in item],
                "prefix_list_ids": permission.get("PrefixListIds", []),
                "protocol": permission.get("IpProtocol"),
                "security_groups": [item["GroupId"] for item in permission.get("UserIdGroupPairs", []) if "GroupId" in item],
                "self": False,
                "to_port": permission.get("ToPort", 0),
            })
        return normalized

    kwargs: Dict[str, Any] = {}
    if group_ids:
        kwargs["GroupIds"] = group_ids

    groups: List[Dict[str, Any]] = []
    for page in _paginate(ec2_client, "describe_security_groups", **kwargs):
        for group in page.get("SecurityGroups", []):
            item = dict(group)
            item["resource_id"] = item.get("GroupId")
            item["resource_name"] = item.get("GroupName")
            item["resource_type"] = "security_group"
            item["arn"] = item.get("SecurityGroupArn")
            item["name"] = item.get("GroupName")
            item["description"] = item.get("Description")
            item["vpc_id"] = item.get("VpcId")
            item["ingress"] = normalize_permissions(item.get("IpPermissions", []))
            item["egress"] = normalize_permissions(item.get("IpPermissionsEgress", []))
            groups.append(item)
    return groups


@_retry_decorator
def fetch_rds_instances(rds_client: Any) -> List[Dict[str, Any]]:
    """Return a list of RDS DB instance dicts."""
    dbs: List[Dict[str, Any]] = []
    for page in _paginate(rds_client, "describe_db_instances"):
        dbs.extend(page.get("DBInstances", []))
    return dbs


@_retry_decorator
def fetch_iam_roles(iam_client: Any) -> List[Dict[str, Any]]:
    """Return a list of IAM role dicts."""
    roles: List[Dict[str, Any]] = []
    for page in _paginate(iam_client, "list_roles"):
        roles.extend(page.get("Roles", []))
    enriched_roles: List[Dict[str, Any]] = []
    for role in roles:
        item = dict(role)
        role_name = item["RoleName"]
        try:
            tag_response = iam_client.list_role_tags(RoleName=role_name)
            item["Tags"] = tag_response.get("Tags", [])
        except botocore_exceptions.ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
                logger.warning(
                    "IAM role tag fetch denied role_name=%s error_code=%s",
                    role_name,
                    error_code,
                    exc_info=True,
                )
                item["Tags"] = []
            else:
                raise
        enriched_roles.append(item)
    return enriched_roles


@_retry_decorator
def fetch_s3_buckets(s3_client: Any) -> List[Dict[str, Any]]:
    """Return a list of S3 bucket dicts from `list_buckets()`.

    Note: `list_buckets` is not paginated.
    """
    resp = s3_client.list_buckets()
    buckets: List[Dict[str, Any]] = []
    for bucket in resp.get("Buckets", []):
        item = dict(bucket)
        bucket_name = item.get("Name")
        if bucket_name:
            try:
                tag_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
                logger.info("live tags resource_id=%s raw_tags=%s error_code=None", bucket_name, tag_response)
                item["Tags"] = {
                    tag["Key"]: tag["Value"]
                    for tag in tag_response.get("TagSet", [])
                    if "Key" in tag and "Value" in tag
                }
            except s3_client.exceptions.ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                logger.error(
                    "live tags resource_id=%s raw_tags={} error_code=%s",
                    bucket_name,
                    error_code,
                    exc_info=True,
                )
                if error_code != "NoSuchTagSet":
                    raise
                item["Tags"] = {}
            except Exception:
                logger.error("live tag fetch failed resource_id=%s", bucket_name, exc_info=True)
                raise
        buckets.append(item)
    return buckets


@_retry_decorator
def fetch_lambda_functions(lambda_client: Any) -> List[Dict[str, Any]]:
    """Return Lambda functions, including tags when the API permits it."""
    functions: List[Dict[str, Any]] = []
    for page in _paginate(lambda_client, "list_functions"):
        for function in page.get("Functions", []):
            item = dict(function)
            function_arn = item.get("FunctionArn")
            if function_arn:
                try:
                    tags_response = lambda_client.list_tags(Resource=function_arn)
                    item["Tags"] = tags_response.get("Tags", {})
                except (AttributeError, botocore_exceptions.ClientError):
                    item.setdefault("Tags", {})
            functions.append(item)
    return functions


@_retry_decorator
def fetch_elastic_beanstalk_environments(eb_client: Any) -> List[Dict[str, Any]]:
    """Return Elastic Beanstalk environments from all applications."""
    environments: List[Dict[str, Any]] = []
    for page in _paginate(eb_client, "describe_environments"):
        environments.extend(page.get("Environments", []))
    return environments


__all__ = [
    "fetch_ec2_instances",
    "fetch_security_groups",
    "fetch_rds_instances",
    "fetch_iam_roles",
    "fetch_s3_buckets",
    "fetch_lambda_functions",
    "fetch_elastic_beanstalk_environments",
]