"""Package initialization step."""

import json
import logging.config
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)

root_dir = Path(__file__).parent.resolve()

# Node ID Pickle
cache_dir = root_dir.joinpath("cache")
cache_dir.mkdir(parents=True, exist_ok=True)
node_id_pickle_path = cache_dir.joinpath("nodeId")


# Logging
class UserContextFilter(logging.Filter):
    """Inject the current request's user_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.user_id = current_user_id.get()
        return True


class HealthCheckFilter(logging.Filter):
    """Suppress uvicorn access log entries for the /healthz endpoint."""

    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn.access args: (client_addr, method, full_path, http_version, status_code)
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            path = str(args[2]).split("?")[0]
            return path != "/healthz"
        return True


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": (
                datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            ),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "msg": record.getMessage(),
            # Just for the Hub Adapter
            "service": getattr(record, "service", "Unknown"),
            "status_code": getattr(record, "status_code", None),
            "user": getattr(record, "user", None),
            "event_name": getattr(record, "event_name", None),
            "event_description": getattr(record, "event_description", None),
        }

        if record.exc_info:
            log["error"] = self.formatException(record.exc_info)

        return json.dumps(log, default=str)  # for non-serializable msgs


log_dir = root_dir.joinpath("logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "user_context": {
            "()": UserContextFilter,
        },
        "no_health_checks": {
            "()": HealthCheckFilter,
        },
    },
    "formatters": {
        "file_formatter": {
            "format": "%(levelname)s - %(module)s:L%(lineno)d - %(asctime)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "console_formatter": {
            "()": JsonFormatter,
            "format": "%(asctime)s [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "file_handler": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_dir.joinpath("node_hub_api_adapter.log").absolute(),
            "encoding": "utf-8",
            "mode": "a",
            "maxBytes": 4098 * 10,  # 4MB file max
            "backupCount": 5,
            "formatter": "file_formatter",
            "filters": ["user_context"],
            "level": "DEBUG",
        },
        "console_handler": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "console_formatter",
            "filters": ["user_context"],
            "level": "INFO",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["file_handler", "console_handler"],
    },
    "loggers": {
        "fastapi": {
            "handlers": ["file_handler", "console_handler"],
            "level": "INFO",
        },
        "httpx": {
            "level": "WARNING",
        },
        "uvicorn.access": {
            "handlers": ["file_handler", "console_handler"],
            "filters": ["no_health_checks"],
            "propagate": False,
        },
    },
}

logging.config.dictConfig(logging_config)
