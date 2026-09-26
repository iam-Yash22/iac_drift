"""Lightweight domain events for in-process pub/sub.

Publishers instantiate events when a significant domain action completes;
subscribers receive them without coupling to the publisher's service layer::

    from app.core.events import DriftDetectedEvent

    event = DriftDetectedEvent(
        account_id=account_id,
        scan_id=scan_id,
        resource_address="aws_instance.web",
        drift_type=DriftType.MODIFIED,
        severity=Severity.HIGH,
    )
    bus.publish(event)

Events are immutable dataclasses with no persistence or transport concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, ClassVar
from uuid import UUID, uuid4

from app.core.constants import DriftType, Severity

__all__ = [
    "AccountOnboardedEvent",
    "DomainEvent",
    "DriftDetectedEvent",
    "publish",
    "subscribe",
]


_subscribers: dict[str, list[Callable[[Any], Any]]] = {}


def subscribe(event_name: str, handler: Callable[[Any], Any]) -> None:
    """Register an in-process handler for an event name."""
    _subscribers.setdefault(event_name, []).append(handler)


def publish(event_name: str, payload: Any) -> None:
    """Publish an event payload to registered in-process handlers."""
    for handler in _subscribers.get(event_name, []):
        handler(payload)


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    """Base metadata shared by all domain events."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_utc_now)

    @classmethod
    def event_type(cls) -> str:
        """Return a stable identifier for pub/sub routing."""
        return cls.__name__


@dataclass(frozen=True, slots=True, kw_only=True)
class DriftDetectedEvent(DomainEvent):
    """Emitted when drift is detected between IaC and live infrastructure."""

    EVENT_NAME: ClassVar[str] = "drift.detected"

    account_id: UUID
    scan_id: UUID
    resource_address: str
    drift_type: DriftType
    severity: Severity
    resource_type: str | None = None
    region: str | None = None
    summary: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountOnboardedEvent(DomainEvent):
    """Emitted when a cloud account is successfully onboarded."""

    EVENT_NAME: ClassVar[str] = "account.onboarded"

    account_id: UUID
    account_name: str
    cloud_provider: str
    onboarded_by_user_id: UUID | None = None
    region: str | None = None
