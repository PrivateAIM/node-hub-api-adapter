"""Adapter API Settings."""

import os

from pydantic import BaseModel


# Init settings
class Settings(BaseModel):
    """Settings for Hub Adapter API."""

    API_ROOT_PATH: str = os.getenv("API_ROOT_PATH", "")

    # IDP Settings
    IDP_URL: str = os.getenv("IDP_URL", "http://localhost:8080")  # User
    # If using a different service for node OIDC, set this to the URL of that service
    NODE_SVC_OIDC_URL: str = os.getenv("NODE_SVC_OIDC_URL", os.getenv("IDP_URL", "http://localhost:8080"))

    # Service URLs
    RESULTS_SERVICE_URL: str = os.getenv("RESULTS_SERVICE_URL", "http://localhost:8000")
    KONG_ADMIN_SERVICE_URL: str = os.getenv("KONG_ADMIN_SERVICE_URL", "http://localhost:8000")
    PODORC_SERVICE_URL: str = os.getenv("PODORC_SERVICE_URL", "http://localhost:18080")

    # User IDP client ID and secret for the hub adapter
    API_CLIENT_ID: str = os.getenv("API_CLIENT_ID", "hub-adapter")
    API_CLIENT_SECRET: str = os.getenv("API_CLIENT_SECRET")  # Not used currently

    # Hub
    HUB_AUTH_SERVICE_URL: str = os.getenv("HUB_AUTH_SERVICE_URL", "https://auth.privateaim.dev")
    HUB_SERVICE_URL: str = os.getenv("HUB_SERVICE_URL", "https://core.privateaim.dev")
    HUB_ROBOT_USER: str = os.getenv("HUB_ROBOT_USER")
    HUB_ROBOT_SECRET: str = os.getenv("HUB_ROBOT_SECRET")


hub_adapter_settings = Settings()
