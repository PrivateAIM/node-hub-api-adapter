"""Adapter API Settings."""

import os

import httpx
from pydantic import BaseModel, model_validator


# Init settings
class Settings(BaseModel):
    """Settings for Hub Adapter API."""

    API_ROOT_PATH: str = os.getenv("API_ROOT_PATH", "")

    # Proxies
    HTTP_PROXY: str = os.getenv("HA_HTTP_PROXY")
    HTTPS_PROXY: str = os.getenv("HA_HTTPS_PROXY")
    PROXY_MOUNTS: dict | None = None

    @model_validator(mode="after")
    def set_proxy_mounts(self):
        if self.HTTP_PROXY or self.HTTPS_PROXY:
            self.PROXY_MOUNTS = {
                "http://": httpx.HTTPTransport(proxy=self.HTTP_PROXY or self.HTTPS_PROXY),
                "https://": httpx.HTTPTransport(proxy=self.HTTPS_PROXY or self.HTTP_PROXY),
            }
        else:
            self.PROXY_MOUNTS = {}
        return self

    # IDP Settings
    IDP_URL: str = os.getenv("IDP_URL", "http://localhost:8080")  # User
    # If using a different service for node OIDC, set this to the URL of that service
    NODE_SVC_OIDC_URL: str = os.getenv("NODE_SVC_OIDC_URL", os.getenv("IDP_URL", "http://localhost:8080"))

    # If deployed in a containerized setting e.g. k8s or docker, then set this to True to ensure internal communication
    STRICT_INTERNAL: str = os.getenv("STRICT_INTERNAL", False)

    # JWKS URI to override the endpoints fetched from the IDP issuer (meant for local testing)
    OVERRIDE_JWKS: str = os.getenv("OVERRIDE_JWKS")

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
