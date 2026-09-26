"""Centralized logging infrastructure for IaC DriftWatch.

Every application layer imports this module for consistent, config-driven
logging::

    from app.core.logging import get_logger, setup_logging

    setup_logging()  # once at process start
    logger = get_logger(__name__)
    logger.info("service started")

Future external sinks (CloudWatch, ELK, Loki) plug in by implementing
``LogHandlerFactory`` and passing instances to ``setup_logging``::

    setup_logging(handler_factories=[StreamHandlerFactory(fmt), MyLokiFactory()])
"""

from __future__ import annotations

import json
import logging
import re
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Final, Mapping

from app.core.config import settings

_SENSITIVE_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|access[_-]?key|authorization|"
    r"credential|private[_-]?key|session)",
    re.IGNORECASE,
)
_REDACTED: Final[str] = "***REDACTED***"

_CONFIGURED: bool = False


def _record_timestamp(record: logging.LogRecord) -> str:
    """Return an ISO-8601 UTC timestamp derived from the log record."""
    dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
    return dt.isoformat(timespec="milliseconds")


def _redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``data`` with sensitive keys redacted."""
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if _SENSITIVE_KEY_PATTERN.search(str(key)):
            redacted[key] = _REDACTED
        elif isinstance(value, Mapping):
            redacted[key] = _redact_mapping(value)
        else:
            redacted[key] = value
    return redacted


class SensitiveDataFilter(logging.Filter):
    """Strip secrets from ``extra`` fields attached to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if key in logging.LogRecord.__dict__ or key.startswith("_"):
                continue
            if _SENSITIVE_KEY_PATTERN.search(key):
                setattr(record, key, _REDACTED)
        return True


class TextFormatter(logging.Formatter):
    """Human-readable formatter: timestamp, level, logger name, message."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        line = (
            f"{_record_timestamp(record)} | {record.levelname:<8} | "
            f"{record.name} | {record.message}"
        )
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter suitable for CloudWatch, ELK, and Loki."""

    _RESERVED: Final[frozenset[str]] = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "taskName",
            "asctime",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _record_timestamp(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._RESERVED and not key.startswith("_")
        }
        if extras:
            payload["extra"] = _redact_mapping(extras)

        return json.dumps(payload, default=str, ensure_ascii=False)


class LogHandlerFactory(ABC):
    """Extension point for future sinks (CloudWatch, ELK, Loki, etc.)."""

    @abstractmethod
    def create(self) -> logging.Handler:
        """Build and return a configured logging handler."""


class StreamHandlerFactory(LogHandlerFactory):
    """Emit logs to stderr (default production sink)."""

    def __init__(self, formatter: logging.Formatter) -> None:
        self._formatter = formatter

    def create(self) -> logging.Handler:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(self._formatter)
        handler.addFilter(SensitiveDataFilter())
        return handler


def _build_formatter(format_name: str) -> logging.Formatter:
    """Select a formatter from ``settings.logging.format``."""
    if format_name == "json":
        return JSONFormatter()
    if format_name == "text":
        return TextFormatter()
    raise ValueError(f"unsupported log format: {format_name!r}")


def _resolve_level(level_name: str) -> int:
    """Map a configured level name to a ``logging`` level constant."""
    level = logging.getLevelNamesMapping().get(level_name.upper())
    if level is None:
        raise ValueError(f"unsupported log level: {level_name!r}")
    return level


def _configure_third_party_loggers(level: int, access_log: bool) -> None:
    """Tune noisy framework loggers without importing those frameworks."""
    if level > logging.DEBUG:
        for name in ("uvicorn.error", "asyncio"):
            logging.getLogger(name).setLevel(logging.WARNING)

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.setLevel(logging.INFO if access_log else logging.CRITICAL)


def setup_logging(
    *,
    handler_factories: list[LogHandlerFactory] | None = None,
    force: bool = False,
) -> None:
    """
    Configure the root logger from ``settings.logging``.

    Idempotent: repeated calls are no-ops unless ``force=True``.
    Pass ``handler_factories`` to attach additional sinks without changing
    call sites elsewhere in the application.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    log_cfg = settings.logging
    level = _resolve_level(log_cfg.level)
    formatter = _build_formatter(log_cfg.format)

    factories = handler_factories or [StreamHandlerFactory(formatter)]
    handlers = [factory.create() for factory in factories]

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for handler in handlers:
        handler.setLevel(level)
        if not any(isinstance(f, SensitiveDataFilter) for f in handler.filters):
            handler.addFilter(SensitiveDataFilter())
        root.addHandler(handler)

    _configure_third_party_loggers(level, log_cfg.access_log)
    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Return a named logger that inherits the application logging configuration.

    Prefer ``get_logger(__name__)`` so log records carry a stable module path.
    """
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name if name else "app")


def bind_context(
    logger: logging.Logger,
    **context: Any,
) -> logging.LoggerAdapter[logging.Logger]:
    """
    Attach structured context to a logger (request id, tenant, etc.).

    Sensitive keys in ``context`` are redacted before emission.
    """
    return logging.LoggerAdapter(logger, _redact_mapping(context))


def reset_logging() -> None:
    """Clear configuration state (intended for tests only)."""
    global _CONFIGURED
    root = logging.getLogger()
    root.handlers.clear()
    _CONFIGURED = False
