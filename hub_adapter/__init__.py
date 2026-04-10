"""Package initialization step."""

import json
import logging.config
import sys
from contextvars import ContextVar
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


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + f".{record.msecs:03.0f}Z",
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "msg": record.getMessage(),
            # Just for the Hub Adapter
            "service": getattr(record, "service", "unknown"),
            "user_id": getattr(record, "user_id", None),
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
            "filename": str(log_dir.joinpath("node_hub_api_adapter.log")),
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
    },
}

logging.config.dictConfig(logging_config)
