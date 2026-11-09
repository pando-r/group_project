from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "mrn",
    "name",
    "patient_name",
    "phone",
    "note",
    "narrative",
    "document",
    "source_text",
    "authorization",
    "cookie",
}


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if key.lower() in SENSITIVE_KEYS else _redact_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def redact_payload(value: Any) -> Any:
    """Redact sensitive keys before persisting telemetry or emitting events."""

    return _redact_value(value)


def redact_event(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return _redact_value(event_dict)


def configure_logging(*, debug: bool = False) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )
    # Keep third-party debug chatter out of the demo console unless explicitly enabled.
    for noisy_logger in ("aiosqlite", "sqlalchemy.engine", "sqlalchemy.pool", "httpx"):
        logging.getLogger(noisy_logger).setLevel(logging.DEBUG if debug else logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_event,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG if debug else logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "medrisk") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
