"""Adapter API Settings."""
import os

from pydantic import BaseModel


class Settings(BaseModel):
    """Default settings for API."""

    # API Gateway settings
    ACCESS_TOKEN_DEFAULT_EXPIRE_MINUTES: int = 360
    GATEWAY_TIMEOUT: int = 59

    # K8s
    K8S_API_KEY: str = os.getenv("K8S_API_KEY")

    # IDP Settings
    IDP_URL: str = os.getenv("IDP_URL", "http://localhost:8080")
    IDP_REALM: str = os.getenv("IDP_REALM", "flame")

    # Service URLs
    RESULTS_SERVICE_URL: str = os.getenv("RESULTS_SERVICE_URL", "http://localhost:8000")
    KONG_ADMIN_SERVICE_URL: str = os.getenv("RESULTS_SERVICE_URL", "http://localhost:8001")
    PODORC_SERVICE_URL: str = os.getenv("PODORC_SERVICE_URL", "http://localhost:8002")

    # UI ID and secret
    API_CLIENT_ID: str = os.getenv("API_CLIENT_ID", "api-client")
    API_CLIENT_SECRET: str = os.getenv("API_CLIENT_SECRET")  # Not used currently

    # Hub
    HUB_AUTH_SERVICE_URL: str = os.getenv("HUB_AUTH_SERVICE_URL", "https://auth.privateaim.net")
    HUB_SERVICE_URL: str = os.getenv("HUB_SERVICE_URL", "https://api.privateaim.net")
    HUB_USERNAME: str = os.getenv("HUB_USERNAME")
    HUB_PASSWORD: str = os.getenv("HUB_PASSWORD")


gateway_settings = Settings()
