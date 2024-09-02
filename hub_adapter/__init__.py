"""Package initialization."""
import sys
import logging

from pathlib import Path
import logging.handlers as handlers

# Logging
root_dir = Path(__file__).parent.resolve()
log_dir = root_dir.joinpath("logs")
log_dir.mkdir(parents=True, exist_ok=True)

main_logger = logging.getLogger("hub_adapter")

# Log Handler
logHandler = handlers.RotatingFileHandler(
    filename=log_dir.joinpath("node_hub_api_adapter.log"),
    mode="a",
    maxBytes=4098 * 10,  # 4MB file max
    backupCount=5,
)
logh_format = logging.Formatter("%(levelname)s - %(module)s:L%(lineno)d - %(asctime)s - %(message)s")
logHandler.setFormatter(logh_format)
logHandler.setLevel(logging.DEBUG)

# Console Handler
streamHandler = logging.StreamHandler(stream=sys.stderr)
stream_format = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
streamHandler.setFormatter(stream_format)
streamHandler.setLevel(logging.DEBUG)

main_logger.addHandler(logHandler)
main_logger.addHandler(streamHandler)
