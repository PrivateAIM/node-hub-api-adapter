"""Models for configuration settings."""
from pydantic import BaseModel


class KeycloakConfig(BaseModel):
    """Keycloak configuration."""
    realm: str
    url: str
    clientId: str


class AuthConfiguration(BaseModel):
    """Auth config model."""

    server_url: str
    realm: str
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    issuer_url: str
