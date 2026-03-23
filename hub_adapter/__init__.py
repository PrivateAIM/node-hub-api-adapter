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
class AnsiColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        no_style = "\033[0m"
        bold = "\033[91m"
        grey = "\033[90m"
        yellow = "\033[93m"
        red = "\033[31m"
        red_light = "\033[91m"
        start_style = {
            "DEBUG": grey,
            "INFO": no_style,
            "WARNING": yellow,
            "ERROR": red,
            "CRITICAL": red_light + bold,
        }.get(record.levelname, no_style)
        end_style = no_style
        return f"{start_style}{super().format(record)}{end_style}"


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "message": record.getMessage(),
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
            "()": AnsiColorFormatter,
            "format": "%(asctime)s [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json_formatter": {
            "()": JsonFormatter,
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
            "formatter": "json_formatter",
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

fluent_log_handler: logging.Handler | None = None

_fluent_host = os.environ.get("FLUENT_HOST")
if _fluent_host:
    try:
        from fluent import handler as _fluent_handler

        _parsed = urlparse(_fluent_host if "://" in _fluent_host else f"tcp://{_fluent_host}")
        _fluent_host = _parsed.hostname
        _fluent_port = _parsed.port or int(os.environ.get("FLUENT_PORT", "24224"))

        class _FluentFormatter(_fluent_handler.FluentRecordFormatter):
            """FluentRecordFormatter that preserves the service extra field."""

            def format(self, record: logging.LogRecord) -> dict:
                data = super().format(record)
                if hasattr(record, "service"):
                    data["service"] = record.service
                return data

        _fmt = _FluentFormatter(
            {
                "level": "%(levelname)s",
                "logger": "%(name)s",
                "module": "%(module)s",
                "line": "%(lineno)d",
                "message": "%(message)s",
            }
        )
        _fh = _fluent_handler.FluentHandler("hub_adapter", host=_fluent_host, port=_fluent_port)
        _fh.setFormatter(_fmt)
        _fh.setLevel(logging.INFO)
        fluent_log_handler = _fh
        logging.getLogger().addHandler(_fh)
        logging.getLogger(__name__).info(f"Fluent handler enabled: {_fluent_host}:{_fluent_port}")

    except Exception as _e:
        logging.getLogger(__name__).warning(f"Could not configure Fluent handler: {_e}")
