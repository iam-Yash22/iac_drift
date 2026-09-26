"""Configuration and cross-cutting constants for IaC DriftWatch.

Defines the ``Settings(BaseSettings)`` singleton. Values are loaded from the
project-root ``.env`` file (via ``python-dotenv``) and process environment
variables, validated by Pydantic, and exposed through:

* ``get_settings()`` — ``lru_cache``-backed factory (preferred for DI/tests)
* ``settings`` — module-level instance created once at import time

Usage::

    from app.core.config import settings, get_settings

    db_url = settings.database.url
    cfg = get_settings()  # same cached instance
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


KNOWN_AWS_DEFAULTS: list[dict[str, str]] = [
    {
        "resource_type": "security_group",
        "attribute": "GroupName",
        "operator": "equals",
        "pattern": "default",
    },
    {
        "resource_type": "iam_role",
        "attribute": "Path",
        "operator": "starts_with",
        "pattern": "/aws-service-role/",
    },
]


def _split_comma_separated(value: object) -> object:
    """Parse a comma-separated string into a list of stripped items."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


CommaSeparatedStrList = Annotated[
    list[str],
    NoDecode,
    BeforeValidator(_split_comma_separated),
]

# Resolve `.env` relative to the project root (two levels above this file).
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
DEFAULT_BOOTSTRAP_ADMIN_PASSWORD = "changethisadminpassword123!"

# Populate os.environ before Settings is constructed (pydantic-settings also
# reads env_file, but explicit dotenv loading keeps behaviour predictable).
load_dotenv(_ENV_FILE, override=False, encoding="utf-8")


class ApplicationSettings(BaseModel):
    """Core application identity and runtime behaviour."""

    name: str = Field(default="IaC DriftWatch", description="Human-readable application name.")
    version: str = Field(default="0.1.0", description="Semantic version string.")
    environment: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENVIRONMENT", "APP__ENVIRONMENT"),
        description="Deployment environment.",
    )
    debug: bool = Field(default=False, description="Enable debug mode (never in production).")
    api_prefix: str = Field(default="/api/v1", description="Global API route prefix.")
    timezone: str = Field(default="UTC", description="Default application timezone.")

    @model_validator(mode="after")
    def _disable_debug_in_production(self) -> ApplicationSettings:
        if self.environment == "production" and self.debug:
            raise ValueError("debug must be False when environment is production")
        return self


class DatabaseSettings(BaseModel):
    """PostgreSQL connection and pool settings."""

    url: PostgresDsn = Field(
        default="postgresql+psycopg2://program:postgres@localhost:5432/iac_driftwatch",
        description="SQLAlchemy-compatible database URL.",
    )
    echo: bool = Field(default=False, description="Echo SQL statements to logs.")
    pool_size: int = Field(default=5, ge=1, le=100, description="Connection pool size.")
    max_overflow: int = Field(default=10, ge=0, le=100, description="Pool overflow limit.")
    pool_timeout: int = Field(default=30, ge=1, description="Seconds to wait for a connection.")
    pool_recycle: int = Field(default=1800, ge=0, description="Recycle connections after N seconds.")


class SecuritySettings(BaseModel):
    """Authentication, tokens, and cryptographic secrets."""

    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production-use-a-long-random-string"),
        description="Application secret key for signing tokens.",
    )
    algorithm: Literal["HS256", "HS384", "HS512"] = Field(
        default="HS256",
        description="JWT signing algorithm.",
    )
    access_token_expire_minutes: int = Field(
        default=480,
        ge=1,
        description="Access token lifetime in minutes.",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        description="Refresh token lifetime in days.",
    )
    password_min_length: int = Field(default=8, ge=8, le=128, description="Minimum password length.")

    @field_validator("secret_key")
    @classmethod
    def _secret_key_min_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("secret_key must be at least 32 characters")
        return value


class LoggingSettings(BaseModel):
    """Structured logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Root log level.",
    )
    format: Literal["json", "text"] = Field(
        default="json",
        description="Log output format.",
    )
    access_log: bool = Field(default=True, description="Log HTTP access requests.")


class CORSSettings(BaseModel):
    """Cross-Origin Resource Sharing policy."""

    allow_origins: CommaSeparatedStrList = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8001"],
        validation_alias=AliasChoices("CORS_ORIGINS", "CORS__ALLOW_ORIGINS"),
        description="Allowed Origin headers (comma-separated in env).",
    )
    allow_credentials: bool = Field(default=True, description="Allow credentials on CORS requests.")
    allow_methods: CommaSeparatedStrList = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        description="Allowed HTTP methods (comma-separated in env).",
    )
    allow_headers: CommaSeparatedStrList = Field(
        default_factory=lambda: ["*"],
        description="Allowed request headers (comma-separated in env).",
    )


class RedisSettings(BaseModel):
    """Redis cache / broker settings (optional until wired up)."""

    url: RedisDsn | None = Field(default=None, description="Redis connection URL.")
    key_prefix: str = Field(default="iac_driftwatch", description="Key namespace prefix.")
    default_ttl_seconds: int = Field(default=3600, ge=1, description="Default cache TTL.")


class WorkerSettings(BaseModel):
    """Background worker / task queue settings."""

    enabled: bool = Field(default=False, description="Enable background workers.")
    concurrency: int = Field(default=2, ge=1, le=64, description="Worker process concurrency.")
    task_default_queue: str = Field(default="default", description="Default task queue name.")
    task_soft_time_limit: int = Field(
        default=300,
        ge=1,
        description="Soft time limit per task in seconds.",
    )


class CloudSettings(BaseModel):
    """Cloud provider credentials and defaults (extensible)."""

    provider: Literal["aws", "azure", "gcp", "none"] = Field(
        default="none",
        description="Primary cloud provider.",
    )
    region: str | None = Field(default=None, description="Default cloud region.")
    aws_access_key_id: SecretStr | None = Field(default=None, description="AWS access key ID.")
    aws_secret_access_key: SecretStr | None = Field(
        default=None,
        description="AWS secret access key.",
    )
    aws_session_token: SecretStr | None = Field(default=None, description="AWS session token.")


class FeatureFlagSettings(BaseModel):
    """Feature toggles for gradual rollout and experimentation."""

    enable_drift_detection: bool = Field(default=True, description="Enable IaC drift detection.")
    enable_notifications: bool = Field(default=False, description="Enable outbound notifications.")
    enable_metrics: bool = Field(default=True, description="Expose application metrics.")
    enable_api_docs: bool = Field(default=True, description="Serve OpenAPI / Swagger UI.")


class Settings(BaseSettings):
    """
    Root settings aggregate.

    Nested sections are populated from environment variables using a double-
    underscore delimiter, e.g. ``DATABASE__URL``, ``SECURITY__SECRET_KEY``.
    Values are also loaded from the project-root ``.env`` file when present.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    app: ApplicationSettings = Field(default_factory=ApplicationSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    cloud: CloudSettings = Field(default_factory=CloudSettings)
    features: FeatureFlagSettings = Field(default_factory=FeatureFlagSettings)
    admin_username: str = Field(
        default="admin",
        validation_alias=AliasChoices("ADMIN_USERNAME"),
        description="Bootstrap admin username.",
    )
    admin_email: EmailStr = Field(
        default="admin@driftwatch-app.com",
        validation_alias=AliasChoices("ADMIN_EMAIL"),
        description="Bootstrap admin email.",
    )
    admin_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ADMIN_PASSWORD"),
        description="Bootstrap admin password used outside development.",
    )
    demo_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEMO_MODE"),
        description="Automatically create a demo viewer user when enabled.",
    )
    demo_viewer_username: str = Field(
        default="demo_viewer",
        validation_alias=AliasChoices("DEMO_VIEWER_USERNAME"),
        description="Username for the optional demo viewer account.",
    )
    demo_viewer_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DEMO_VIEWER_PASSWORD"),
        description="Password for the optional demo viewer account.",
    )
    app_base_url: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("APP_BASE_URL"),
        description="Base URL used in links included in alert emails.",
    )
    alert_sender_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALERT_SENDER_EMAIL", "GMAIL_ADDRESS"),
        description="SMTP sender email used for drift alerts.",
    )
    alert_sender_app_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ALERT_SENDER_APP_PASSWORD", "GMAIL_APP_PASSWORD"),
        description="SMTP app password used for drift alerts.",
    )
    scan_stale_minutes: int = Field(
        default=30,
        ge=0,
        validation_alias=AliasChoices("SCAN_STALE_MINUTES"),
        description="Age in minutes before queued/running scans are treated as orphaned.",
    )

    @property
    def gmail_address(self) -> str | None:
        """Backward-compatible alias for existing integrations and tests."""
        return self.alert_sender_email

    @gmail_address.setter
    def gmail_address(self, value: str | None) -> None:
        self.alert_sender_email = value

    @property
    def gmail_app_password(self) -> SecretStr | None:
        """Backward-compatible alias for existing integrations and tests."""
        return self.alert_sender_app_password

    @gmail_app_password.setter
    def gmail_app_password(self, value: SecretStr | None) -> None:
        self.alert_sender_app_password = value

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> Settings:
        if self.app.environment == "production":
            secret = self.security.secret_key.get_secret_value()
            if secret.startswith("change-me"):
                raise ValueError(
                    "SECURITY__SECRET_KEY must be set to a strong secret in production"
                )
        return self

    @model_validator(mode="after")
    def _validate_bootstrap_admin_credentials(self) -> Settings:
        if (self.app.environment or "development").lower() == "development":
            return self

        password = self.admin_password.get_secret_value() if self.admin_password else ""
        if not password.strip():
            raise ValueError("ADMIN_PASSWORD must be set when not running in development")
        if password == DEFAULT_BOOTSTRAP_ADMIN_PASSWORD:
            raise ValueError("ADMIN_PASSWORD must not use the default bootstrap password outside development")
        if self.demo_mode and (
            not self.demo_viewer_username.strip() or not (self.demo_viewer_password and self.demo_viewer_password.get_secret_value().strip())
        ):
            raise ValueError("DEMO_VIEWER_USERNAME and DEMO_VIEWER_PASSWORD must be set when DEMO_MODE is enabled")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached ``Settings`` singleton."""
    return Settings()


# Instantiated once at import time; all readers share this object via get_settings().
settings: Settings = get_settings()
