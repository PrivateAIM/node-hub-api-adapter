"""Adapter API Settings."""
import os

from pydantic import BaseModel


class Settings(BaseModel):
    """Default settings for API."""

    ACCESS_TOKEN_DEFAULT_EXPIRE_MINUTES: int = 360
    GATEWAY_TIMEOUT: int = 59

    # Service URLs
    RESULTS_SERVICE_URL: str = os.getenv("RESULTS_SERVICE_URL")
    PODORC_SERVICE_URL: str = os.getenv("PODORC_SERVICE_URL")
    HUB_SERVICE_URL: str = os.getenv("HUB_SERVICE_URL")


settings = Settings()
