"""Structured logging configuration via ``logging.config.dictConfig``.

Call ``configure_logging()`` once at process startup (e.g. from
``app/lifespan.py``) or from standalone ``scripts/`` entry points::

    from app.core.logging_config import configure_logging, get_logger

    configure_logging()
    logger = get_logger(__name__)
    logger.info("ready")

Output format and level are driven by ``settings.logging`` (JSON by default).
"""

from __future__ import annotations

import json
import logging
import logging.config
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Mapping

from app.core.config import settings

__all__ = [
    "JSONFormatter",
    "SensitiveDataFilter",
    "TextFormatter",
    "build_logging_config",
    "configure_logging",
    "get_logger",
    "reset_logging",
]

_SENSITIVE_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|access[_-]?key|authorization|"
    r"credential|private[_-]?key|session)",
    re.IGNORECASE,
)
_REDACTED: Final[str] = "***REDACTED***"

_CONFIGURED: bool = False
_LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "driftwatch.log"


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


class DriftWatchFileFormatter(logging.Formatter):
    """Format drift diagnostics as one line per event."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        line = (
            f"{timestamp} | {record.levelname:<5} | "
            f"{record.name}:{record.funcName} | {record.getMessage()}"
        )
        if record.exc_info:
            traceback_text = "".join(traceback.format_exception(*record.exc_info)).strip()
            line = f"{line} | traceback: {traceback_text.replace(chr(10), ' | ')}"
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


def build_logging_config() -> dict[str, Any]:
    """
    Build a ``dictConfig`` dictionary from ``settings.logging``.

    The active formatter follows ``settings.logging.format`` (``json`` or
    ``text``). Third-party loggers are tuned by name without importing those
    frameworks.
    """
    log_cfg = settings.logging
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    level = log_cfg.level.upper()
    formatter_name = "json" if log_cfg.format == "json" else "text"
    access_level = "INFO" if log_cfg.access_log else "CRITICAL"
    framework_level = level

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "sensitive_data": {
                "()": f"{__name__}.SensitiveDataFilter",
            },
        },
        "formatters": {
            "json": {
                "()": f"{__name__}.JSONFormatter",
            },
            "text": {
                "()": f"{__name__}.TextFormatter",
            },
            "driftwatch_file": {
                "()": f"{__name__}.DriftWatchFileFormatter",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": formatter_name,
                "stream": "ext://sys.stderr",
                "filters": ["sensitive_data"],
                "level": level,
            },
            "driftwatch_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "driftwatch_file",
                "filename": str(_LOG_FILE),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 3,
                "encoding": "utf-8",
                "level": level,
            },
        },
        "root": {
            "handlers": ["console", "driftwatch_file"],
            "level": level,
        },
        "loggers": {
            "uvicorn.access": {
                "handlers": ["console"],
                "level": access_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "level": framework_level,
                "propagate": True,
            },
            "asyncio": {
                "level": framework_level,
                "propagate": True,
            },
        },
    }


def configure_logging(*, force: bool = False) -> None:
    """
    Apply structured logging via ``logging.config.dictConfig``.

    Idempotent: repeated calls are no-ops unless ``force=True``.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    logging.config.dictConfig(build_logging_config())
    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Return a named logger using the application logging configuration.

    Lazily calls ``configure_logging()`` when logging has not yet been set up.
    """
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name if name else "app")


def reset_logging() -> None:
    """Clear configuration state (intended for tests only)."""
    global _CONFIGURED
    root = logging.getLogger()
    root.handlers.clear()
    logging.config.dictConfig({"version": 1, "disable_existing_loggers": False})
    _CONFIGURED = False
