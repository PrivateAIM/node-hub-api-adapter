"""Package initialization step."""

import logging.config
import sys
from pathlib import Path

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
