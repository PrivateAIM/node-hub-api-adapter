"""Adapter API Settings."""
import logging
import logging.handlers as handlers
import os
import sys
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    """Default settings for API."""

    API_ROOT_PATH: str = os.getenv("API_ROOT_PATH", "")

    HUB_REALM_UUID: str = os.getenv("HUB_REALM_UUID")

    # IDP Settings
    IDP_URL: str = os.getenv("IDP_URL", "http://localhost:8080")
    IDP_REALM: str = os.getenv("IDP_REALM", "flame")

    # Service URLs
    RESULTS_SERVICE_URL: str = os.getenv("RESULTS_SERVICE_URL", "http://localhost:8000")
    KONG_ADMIN_SERVICE_URL: str = os.getenv("KONG_ADMIN_SERVICE_URL", "http://localhost:8000")
    PODORC_SERVICE_URL: str = os.getenv("PODORC_SERVICE_URL", "http://localhost:18080")

    # UI ID and secret
    API_CLIENT_ID: str = os.getenv("API_CLIENT_ID", "hub-adapter")
    API_CLIENT_SECRET: str = os.getenv("API_CLIENT_SECRET")  # Not used currently

    # Hub
    HUB_AUTH_SERVICE_URL: str = os.getenv("HUB_AUTH_SERVICE_URL", "https://auth.privateaim.dev")
    HUB_SERVICE_URL: str = os.getenv("HUB_SERVICE_URL", "https://core.privateaim.dev")
    HUB_ROBOT_USER: str = os.getenv("HUB_ROBOT_USER")
    HUB_ROBOT_SECRET: str = os.getenv("HUB_ROBOT_SECRET")


hub_adapter_settings = Settings()

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
