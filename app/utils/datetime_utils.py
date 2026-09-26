from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def to_utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime to UTC.

    Naive datetimes are treated as already being UTC to keep serialization
    predictable across the app.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def format_datetime(
    value: datetime | None,
    *,
    timezone_name: str | None = "UTC",
    fmt: str | None = None,
) -> str:
    """Format a datetime for display.

    If no timezone is provided, the value is converted to UTC before formatting.
    The default output is ISO 8601 with a trailing Z for UTC.
    """
    if value is None:
        return ""

    dt = to_utc(value)
    if timezone_name:
        try:
            dt = dt.astimezone(ZoneInfo(timezone_name))
        except Exception:
            dt = dt.astimezone(timezone.utc)

    if fmt is not None:
        return dt.strftime(fmt)

    iso_value = dt.isoformat()
    return iso_value.replace("+00:00", "Z") if timezone_name in (None, "UTC") else iso_value


def format_utc(value: datetime | None, fmt: str | None = None) -> str:
    """Format a datetime in UTC."""
    return format_datetime(value, timezone_name="UTC", fmt=fmt)


__all__ = [
    "utcnow",
    "to_utc",
    "format_datetime",
    "format_utc",
]
