"""Adapter API Settings."""

import os
from dataclasses import dataclass


# Init settings
@dataclass(frozen=True)
class Settings:
    """Settings for Hub Adapter API."""

    API_ROOT_PATH: str = os.getenv("API_ROOT_PATH", "")

    HTTP_PROXY: str = os.getenv("HTTP_PROXY", "")
    HTTPS_PROXY: str = os.getenv("HTTPS_PROXY", "")

    EXTRA_CA_CERTS: str = os.getenv("EXTRA_CA_CERTS")

    # IDP Settings
    IDP_URL: str = os.getenv("IDP_URL", "http://localhost:8080")  # User
    # If using a different service for node OIDC, set this to the URL of that service
    NODE_SVC_OIDC_URL: str = os.getenv("NODE_SVC_OIDC_URL", os.getenv("IDP_URL", "http://localhost:8080"))

    # JWKS URI to override the endpoints fetched from the IDP issuer (meant for local testing)
    OVERRIDE_JWKS: str = os.getenv("OVERRIDE_JWKS")

    # Service URLs
    RESULTS_SERVICE_URL: str = os.getenv("RESULTS_SERVICE_URL", "http://localhost:8000")
    KONG_ADMIN_SERVICE_URL: str = os.getenv("KONG_ADMIN_SERVICE_URL", "http://localhost:8000")
    KONG_PROXY_SERVICE_URL: str = os.getenv("KONG_PROXY_SERVICE_URL")
    PODORC_SERVICE_URL: str = os.getenv("PODORC_SERVICE_URL", "http://localhost:18080")

    # User IDP client ID and secret for the hub adapter
    API_CLIENT_ID: str = os.getenv("API_CLIENT_ID", "hub-adapter")
    API_CLIENT_SECRET: str = os.getenv("API_CLIENT_SECRET")  # Not used currently

    # Hub
    HUB_AUTH_SERVICE_URL: str = os.getenv("HUB_AUTH_SERVICE_URL", "https://auth.privateaim.dev")
    HUB_SERVICE_URL: str = os.getenv("HUB_SERVICE_URL", "https://core.privateaim.dev")
    HUB_ROBOT_USER: str = os.getenv("HUB_ROBOT_USER")
    HUB_ROBOT_SECRET: str = os.getenv("HUB_ROBOT_SECRET")

    # RBAC
    ROLE_CLAIM_NAME: str = os.getenv("ROLE_CLAIM_NAME")
    ADMIN_ROLE: str = os.getenv("ADMIN_ROLE", "admin")
    STEWARD_ROLE: str = os.getenv("STEWARD_ROLE")
    RESEARCHER_ROLE: str = os.getenv("RESEARCHER_ROLE")
