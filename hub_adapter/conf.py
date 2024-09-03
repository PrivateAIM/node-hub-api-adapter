"""Adapter API Settings."""

import os

from pydantic import BaseModel


# Init settings

class Settings(BaseModel):
    """Default settings for API."""

    API_ROOT_PATH: str = os.getenv("API_ROOT_PATH", "")

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
