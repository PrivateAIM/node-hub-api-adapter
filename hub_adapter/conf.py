"""Adapter API Settings."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for Hub Adapter API."""

    api_root_path: str = ""

    http_proxy: str | None = None
    https_proxy: str | None = None
    extra_ca_certs: str | None = None

    # IDP Settings
    idp_url: str = "http://localhost:8080"  # User
    # If using a different service for node OIDC, set this to the URL of that service
    NODE_SVC_OIDC_URL: str = os.getenv(
        "NODE_SVC_OIDC_URL", os.getenv("IDP_URL", "http://localhost:8080")
    )

    # JWKS URI to override the endpoints fetched from the IDP issuer (meant for local testing)
    override_jwks: str | None = None

    # Service URLs
    storage_service_url: str = "http://localhost:8000"
    kong_admin_service_url: str = "http://localhost:8000"
    kong_proxy_service_url: str = "http://localhost:8000"
    podorc_service_url: str = "http://localhost:5000"

    # User IDP client ID and secret for the hub adapter
    api_client_id: str = "hub-adapter"
    api_client_secret: str | None = None

    # Hub

    hub_auth_service_url: str = "https://auth.privateaim.dev"
    hub_service_url: str = "https://core.privateaim.dev"
    hub_robot_user: str | None = None
    hub_robot_secret: str | None = None

    # RBAC
    role_claim_name: str | None = None
    admin_role: str | None = "admin"
    steward_role: str | None = None
    researcher_role: str | None = None

    # Event logging
    log_events: bool = True
    postgres_event_user: str | None = None
    postgres_event_password: str | None = None
    postgres_event_db: str | None = None
    postgres_event_host: str | None = "localhost"
    postgres_event_port: str | None = "5432"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
