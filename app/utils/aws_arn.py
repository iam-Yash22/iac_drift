import re
from dataclasses import dataclass


_ARN_RE = re.compile(
    r"^(?P<partition>arn):"
    r"(?P<service>[A-Za-z0-9-]+):"
    r"(?P<region>[A-Za-z0-9-]*):"
    r"(?P<account_id>[0-9]{12}):"
    r"(?P<resource>.+)$"
)


@dataclass(frozen=True)
class ArnParts:
    partition: str
    service: str
    region: str
    account_id: str
    resource: str

    @property
    def arn(self) -> str:
        return (
            f"arn:{self.partition}:{self.service}:{self.region}:{self.account_id}:{self.resource}"
        )

    @property
    def resource_type(self) -> str:
        if ":" not in self.resource:
            return self.resource
        return self.resource.split(":", 1)[0]

    @property
    def resource_name(self) -> str:
        if ":" not in self.resource:
            return self.resource
        return self.resource.split(":", 1)[1]


def parse_arn(arn: str) -> ArnParts:
    """Parse an AWS ARN into normalized components."""
    if not isinstance(arn, str):
        raise TypeError("ARN must be a string")

    match = _ARN_RE.fullmatch(arn.strip())
    if not match:
        raise ValueError(f"Invalid ARN format: {arn}")

    return ArnParts(
        partition=match.group("partition"),
        service=match.group("service"),
        region=match.group("region"),
        account_id=match.group("account_id"),
        resource=match.group("resource"),
    )


def build_arn(
    *,
    partition: str = "aws",
    service: str,
    region: str = "",
    account_id: str,
    resource: str,
) -> str:
    """Build an AWS ARN string from its components."""
    if not service:
        raise ValueError("service is required")
    if not account_id:
        raise ValueError("account_id is required")
    if not resource:
        raise ValueError("resource is required")

    return f"arn:{partition}:{service}:{region}:{account_id}:{resource}"


def arn_to_resource_key(arn: str) -> dict[str, str]:
    """Return the normalized ARN components used by resource parsers."""
    parts = parse_arn(arn)
    return {
        "partition": parts.partition,
        "service": parts.service,
        "region": parts.region,
        "account_id": parts.account_id,
        "resource": parts.resource,
        "resource_type": parts.resource_type,
        "resource_name": parts.resource_name,
    }


__all__ = ["ArnParts", "parse_arn", "build_arn", "arn_to_resource_key"]
