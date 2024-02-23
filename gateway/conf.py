"""Adapter API Settings."""
import os

# from dotenv import load_dotenv  # TODO remove
from pydantic import BaseModel


# load_dotenv(dotenv_path="../env/.env.dev")


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
    RESULTS_SERVICE_URL: str = os.getenv("RESULTS_SERVICE_URL")
    PODORC_SERVICE_URL: str = os.getenv("PODORC_SERVICE_URL")
    HUB_SERVICE_URL: str = os.getenv("HUB_SERVICE_URL")

    # UI ID and secret
    UI_CLIENT_ID: str = os.getenv("UI_CLIENT_ID", "test-client")
    UI_CLIENT_SECRET: str = os.getenv("UI_CLIENT_SECRET", "someSecret")


gateway_settings = Settings()
