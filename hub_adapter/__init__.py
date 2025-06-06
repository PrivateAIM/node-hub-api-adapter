"""Package initialization step."""

import logging
import logging.handlers as handlers
from pathlib import Path

root_dir = Path(__file__).parent.resolve()

# Node ID Pickle
cache_dir = root_dir.joinpath("cache")
cache_dir.mkdir(parents=True, exist_ok=True)
node_id_pickle_path = cache_dir.joinpath("nodeId")

# Logging

log_dir = root_dir.joinpath("logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.WARNING,
    force=True,
)

main_logger = logging.getLogger("hub_adapter")
main_logger.setLevel(logging.DEBUG)

# Log Handler
logHandler = handlers.RotatingFileHandler(
    filename=log_dir.joinpath("node_hub_api_adapter.log"),
    encoding="utf-8",
    mode="a",
    maxBytes=4098 * 10,  # 4MB file max
    backupCount=5,
)
logh_format = logging.Formatter(
    fmt="%(levelname)s - %(module)s:L%(lineno)d - %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logHandler.setFormatter(logh_format)
logHandler.setLevel(logging.DEBUG)

main_logger.addHandler(logHandler)

# Console Handler
# streamHandler = logging.StreamHandler()
# stream_format = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
# streamHandler.setFormatter(stream_format)
# streamHandler.setLevel(logging.INFO)
#
# main_logger.addHandler(streamHandler)
