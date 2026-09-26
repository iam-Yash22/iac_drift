import re

from pydantic import field_validator


AWS_ACCOUNT_ID_RE = re.compile(r"^\d{12}$")
AWS_ROLE_ARN_RE = re.compile(r"^arn:aws:iam::\d{12}:role\/[A-Za-z0-9+=,.@_-]+(?:\/[A-Za-z0-9+=,.@_-]+)*$")
RESOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/+=,@-]*$")


def account_id_validator(value: str) -> str:
    """Validate a 12-digit AWS account ID string."""
    if not isinstance(value, str):
        raise TypeError("account ID must be a string")
    if not AWS_ACCOUNT_ID_RE.fullmatch(value):
        raise ValueError("must be exactly 12 digits")
    return value


def validate_account_id(value: str) -> str:
    """Validate an AWS account ID using the schema's public helper name."""
    return account_id_validator(value)


def validate_role_arn(value: str) -> str:
    """Validate an AWS IAM role ARN."""
    if not isinstance(value, str):
        raise TypeError("role ARN must be a string")
    if not AWS_ROLE_ARN_RE.fullmatch(value):
        raise ValueError("must be a valid AWS IAM role ARN")
    return value


def validate_resource_id(value: str) -> str:
    """Validate a non-empty cloud resource identifier."""
    if not isinstance(value, str):
        raise TypeError("resource ID must be a string")
    if not RESOURCE_ID_RE.fullmatch(value):
        raise ValueError("must be a valid cloud resource ID")
    return value


def aws_account_id_field_validator():
    """Return a Pydantic field validator for AWS account IDs."""

    @field_validator("account_id")
    @classmethod
    def _validate_account_id(cls, value: str) -> str:
        return account_id_validator(value)

    return _validate_account_id


__all__ = [
    "AWS_ACCOUNT_ID_RE",
    "AWS_ROLE_ARN_RE",
    "RESOURCE_ID_RE",
    "account_id_validator",
    "validate_account_id",
    "validate_role_arn",
    "validate_resource_id",
    "aws_account_id_field_validator",
]
