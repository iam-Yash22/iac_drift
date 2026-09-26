import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

import boto3
import botocore.exceptions as botocore_exceptions
import app.security.encryption as encryption
import app.core.config as config
import app.utils.exceptions as exceptions
from app.core.logging_config import get_logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = get_logger(__name__)


# In-memory cache for assumed-role credentials
# Key: (role_arn, region)
# Value: dict with keys: credentials (dict), expiration (datetime)
_CREDENTIALS_CACHE: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}


def _cache_key(role_arn: str, region: Optional[str]) -> Tuple[str, Optional[str]]:
    return (role_arn, region)


def _is_valid(expiration: datetime) -> bool:
    # consider a safety margin of 1 minute to account for clock skew
    return datetime.now(timezone.utc) + timedelta(minutes=1) < expiration


def _decrypt_external_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if hasattr(encryption, "decrypt"):
        try:
            return encryption.decrypt(value)
        except Exception:
            # bubble up minimal context; caller will convert to project exceptions
            raise
    return value


def _extract_aws_error_detail(exc: botocore_exceptions.ClientError) -> Tuple[Optional[str], Optional[str]]:
    """Extract error code and message from a boto3 ClientError.
    
    Returns (error_code, user_message) tuple.
    """
    try:
        error_code = exc.response.get("Error", {}).get("Code")
        error_msg = exc.response.get("Error", {}).get("Message")
        return error_code, error_msg
    except (AttributeError, TypeError):
        return None, str(exc)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((botocore_exceptions.ClientError, botocore_exceptions.EndpointConnectionError)),
)
def _resolve_base_aws_credentials() -> Dict[str, str]:
    """Resolve the base credentials used to call STS.

    Prefer the app's configured values, but also accept the standard AWS
    environment variables and the default boto3 credential chain so a running
    service can authenticate even when the app has not been explicitly configured
    with CLOUD__AWS_* values.
    """
    access_key = config.settings.cloud.aws_access_key_id
    secret_key = config.settings.cloud.aws_secret_access_key
    session_token = config.settings.cloud.aws_session_token

    if access_key:
        access_key = access_key.get_secret_value()
    else:
        access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("CLOUD__AWS_ACCESS_KEY_ID")

    if secret_key:
        secret_key = secret_key.get_secret_value()
    else:
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("CLOUD__AWS_SECRET_ACCESS_KEY")

    if session_token:
        session_token = session_token.get_secret_value()
    else:
        session_token = os.getenv("AWS_SESSION_TOKEN") or os.getenv("CLOUD__AWS_SESSION_TOKEN")

    creds: Dict[str, str] = {}
    if access_key:
        creds["aws_access_key_id"] = access_key
    if secret_key:
        creds["aws_secret_access_key"] = secret_key
    if session_token:
        creds["aws_session_token"] = session_token

    print(f"DEBUG settings.cloud.aws_access_key_id set: {bool(config.settings.cloud.aws_access_key_id)}", file=sys.stderr)
    print(f"DEBUG env AWS_ACCESS_KEY_ID set: {bool(os.getenv('AWS_ACCESS_KEY_ID'))}", file=sys.stderr)
    print(f"DEBUG env CLOUD__AWS_ACCESS_KEY_ID set: {bool(os.getenv('CLOUD__AWS_ACCESS_KEY_ID'))}", file=sys.stderr)
    print(f"DEBUG creds dict keys: {list(creds.keys())}", file=sys.stderr)
    print(f"DEBUG access key prefix: {creds.get('aws_access_key_id', 'MISSING')[:4]}", file=sys.stderr)
    return creds


def _resolve_aws_region() -> Optional[str]:
    region = getattr(config.settings.cloud, "region", None)
    if region:
        return region
    return os.getenv("AWS_REGION") or getattr(config, "AWS_DEFAULT_REGION", None)


def _build_base_sts_session() -> boto3.session.Session:
    """Build the base STS session using the caller identity that is allowed to assume roles."""
    profile_name = os.getenv("AWS_PROFILE") or os.getenv("CLOUD__AWS_PROFILE")
    creds = _resolve_base_aws_credentials()

    if profile_name:
        session = boto3.Session(profile_name=profile_name, region_name=_resolve_aws_region())
        if session.get_credentials() is not None:
            return session

    if creds:
        return boto3.Session(
            region_name=_resolve_aws_region(),
            aws_access_key_id=creds.get("aws_access_key_id"),
            aws_secret_access_key=creds.get("aws_secret_access_key"),
            aws_session_token=creds.get("aws_session_token"),
        )

    return boto3.Session(region_name=_resolve_aws_region())


def _assume_role_api(role_arn: str, external_id: Optional[str], session_name: str) -> Dict[str, Any]:
    sts_session = _build_base_sts_session()
    sts_client = sts_session.client("sts")
    params: Dict[str, Any] = {"RoleArn": role_arn, "RoleSessionName": session_name}
    if external_id:
        params["ExternalId"] = external_id

    return sts_client.assume_role(**params)


def assume_role(role_arn: str, external_id: Optional[str] = None) -> Dict[str, Any]:
    """Assume the given role and return STS credentials dict.

    Returns dict with keys: AccessKeyId, SecretAccessKey, SessionToken, Expiration
    Caches credentials in-memory until their expiration (with a safety margin).
    
    Raises:
      ValidationError: If role_arn is invalid, external_id cannot be decrypted, or AWS
        auth credentials are invalid (AccessDenied, InvalidClientTokenId, etc.).
      ServiceError: If AssumeRole fails for transient reasons or unexpected errors.
    """
    if not role_arn:
        raise exceptions.ValidationError("role_arn is required for AssumeRole")

    region = getattr(config, "AWS_DEFAULT_REGION", None)
    key = _cache_key(role_arn, region)
    cached = _CREDENTIALS_CACHE.get(key)
    if cached:
        expiration = cached.get("expiration")
        if expiration and _is_valid(expiration):
            logger.debug(f"Using cached credentials for role: {role_arn}")
            return cached["credentials"]

    # decrypt external_id if necessary
    try:
        ext = _decrypt_external_id(external_id)
    except Exception as exc:
        logger.error(f"Failed to decrypt external_id for role {role_arn}: {exc}")
        raise exceptions.ValidationError(f"Failed to decrypt external_id: {exc}") from exc

    session_name = getattr(config, "AWS_ASSUME_ROLE_SESSION_NAME", "driftwatch-session")

    try:
        logger.debug(f"Attempting to assume role: {role_arn}")
        resp = _assume_role_api(role_arn=role_arn, external_id=ext, session_name=session_name)
    except botocore_exceptions.ClientError as exc:
        error_code, error_msg = _extract_aws_error_detail(exc)
        log_extra = {"role_arn": role_arn, "error_code": error_code, "aws_error": error_msg}
        
        # Authentication errors (invalid credentials, access denied) -> ValidationError
        auth_errors = {"AccessDenied", "InvalidClientTokenId", "UnrecognizedClientException"}
        if error_code in auth_errors:
            logger.warning(f"AssumeRole authentication failed for {role_arn}: {error_code}", extra=log_extra)
            raise exceptions.ValidationError(
                f"Failed to assume role: {error_code}. Verify role_arn and credentials.",
                detail=error_msg
            ) from exc
        
        # Transient errors and other service errors -> ServiceError
        logger.error(f"AssumeRole failed for {role_arn}: {error_code}", extra=log_extra)
        raise exceptions.ServiceError(
            f"Failed to assume AWS role: {error_code}. Please try again later.",
            detail=error_msg
        ) from exc
    except botocore_exceptions.EndpointConnectionError as exc:
        logger.error(f"Network error assuming role {role_arn}: {exc}")
        raise exceptions.ServiceError(
            "Failed to connect to AWS. Please verify your network connection and try again.",
            detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.error(f"Unexpected error during AssumeRole for {role_arn}: {exc}", exc_info=True)
        raise exceptions.ServiceError(
            f"Unexpected error while assuming AWS role: {exc.__class__.__name__}",
            detail=str(exc)
        ) from exc

    creds = resp.get("Credentials")
    if not creds:
        logger.error(f"AssumeRole returned no credentials for {role_arn}")
        raise exceptions.ServiceError("AssumeRole did not return credentials")

    expiration = creds.get("Expiration")
    if not isinstance(expiration, datetime):
        # attempt to parse if needed (unlikely with boto3)
        expiration = datetime.now(timezone.utc) + timedelta(hours=1)

    _CREDENTIALS_CACHE[key] = {"credentials": creds, "expiration": expiration}
    logger.debug(f"Successfully assumed role {role_arn}; credentials cached until {expiration.isoformat()}")
    return creds


def _session_from_credentials(creds: Dict[str, Any], region: Optional[str] = None) -> boto3.session.Session:
    """Create a separate session using the temporary credentials returned by STS."""
    return boto3.Session(
        aws_access_key_id=creds.get("AccessKeyId"),
        aws_secret_access_key=creds.get("SecretAccessKey"),
        aws_session_token=creds.get("SessionToken"),
        region_name=region or _resolve_aws_region(),
    )


def get_boto3_client(account: Any, service_name: str, region: Optional[str] = None):
    """Return a boto3 client for the target account and service.

    `account` is expected to have `role_arn` and optional `external_id` attributes.
    
    Raises:
      ValidationError: If account.role_arn is missing or auth fails.
      ServiceError: If AssumeRole or client creation fails.
    """
    account_id = getattr(account, "account_id", "<unknown>")
    role_arn = getattr(account, "role_arn", None)
    if not role_arn:
        raise exceptions.ValidationError(f"account.role_arn is required (account_id: {account_id})")

    try:
        ext = getattr(account, "external_id", None)
        creds = assume_role(role_arn=role_arn, external_id=ext)
        session = _session_from_credentials(creds, region=region)
        return session.client(service_name)
    except exceptions.AppException:
        raise
    except Exception as exc:
        logger.error(
            f"Failed to create {service_name} client for account {account_id}: {exc}",
            extra={"account_id": account_id, "service": service_name, "role_arn": role_arn},
            exc_info=True
        )
        raise exceptions.ServiceError(
            f"Failed to create AWS {service_name} client for account {account_id}",
            detail=str(exc)
        ) from exc


def get_clients_for_account(account: Any, services: Optional[list] = None, region: Optional[str] = None) -> Dict[str, Any]:
    """Return a mapping of service name -> boto3 client for the provided services.

    If `services` is None, returns a small set of commonly used clients.
    
    Raises:
      ValidationError: If account credentials are invalid.
      ServiceError: If client creation fails for any service.
    """
    if services is None:
        services = ["sts", "ec2", "s3", "iam", "lambda", "elasticbeanstalk"]

    account_id = getattr(account, "account_id", "<unknown>")
    clients: Dict[str, Any] = {}
    
    for svc in services:
        try:
            clients[svc] = get_boto3_client(account, svc, region=region)
        except exceptions.AppException:
            # Re-raise application exceptions immediately
            raise
        except Exception as exc:
            logger.error(
                f"Failed to create {svc} client for account {account_id}: {exc}",
                extra={"account_id": account_id, "service": svc},
                exc_info=False
            )
            # Re-raise immediately so caller can handle the failure
            raise
    
    return clients


def clear_cache() -> None:
    """Clear the in-memory credentials cache (useful for tests)."""
    _CREDENTIALS_CACHE.clear()
