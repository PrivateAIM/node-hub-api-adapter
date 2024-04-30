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
    client_secret: str | None = None
    authorization_url: str
    token_url: str
    issuer_url: str


class Token(BaseModel):
    """IDP token model."""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
    refresh_expires_in: int | None = None
