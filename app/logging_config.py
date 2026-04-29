"""Structured JSON logging configuration using structlog with ECS-compatible fields."""

import logging
import sys

import structlog

from app.config import settings


def _add_service_context(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Add service metadata to every log entry."""
    event_dict["service.name"] = settings.service_name
    event_dict["service.version"] = settings.service_version
    event_dict["service.environment"] = settings.environment
    return event_dict


def _rename_event_to_message(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Rename structlog's 'event' key to ECS 'message'."""
    event_dict["message"] = event_dict.pop("event", "")
    return event_dict


def _rename_level_to_ecs(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Rename 'level' to ECS 'log.level'."""
    level = event_dict.pop("level", None)
    if level is not None:
        event_dict["log.level"] = level
    return event_dict


def _add_logger_name(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Ensure 'logger' field is present."""
    if "logger" not in event_dict:
        record = event_dict.get("_record")
        if record is not None and hasattr(record, "name"):
            event_dict["logger"] = record.name
        else:
            event_dict["logger"] = "root"
    return event_dict


def _add_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Inject correlation_id / trace.id from contextvars if available."""
    from app.middleware import get_correlation_id

    cid = get_correlation_id()
    if cid:
        event_dict.setdefault("correlation_id", cid)
        event_dict.setdefault("trace.id", cid)
    return event_dict


shared_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", key="@timestamp"),
    _add_service_context,
    _add_correlation_id,
    _add_logger_name,
    _rename_level_to_ecs,
    _rename_event_to_message,
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
]


def setup_logging() -> None:
    """Configure structlog and stdlib logging based on settings."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    use_json = settings.log_format.lower() == "json"

    if use_json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    for noisy in ("azure", "urllib3", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
