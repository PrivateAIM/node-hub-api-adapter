"""Package initialization step."""

import json
import logging.config
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

root_dir = Path(__file__).parent.resolve()

# Node ID Pickle
cache_dir = root_dir.joinpath("cache")
cache_dir.mkdir(parents=True, exist_ok=True)
node_id_pickle_path = cache_dir.joinpath("nodeId")


# Logging
class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "_msg": record.getMessage(),
        }
        if hasattr(record, "service"):
            payload["service"] = record.service
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


log_dir = root_dir.joinpath("logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
)

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
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
            "level": "INFO",
        },
        "console_handler": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "console_formatter",
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
