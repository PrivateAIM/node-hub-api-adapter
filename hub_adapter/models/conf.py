"""Models for configuration settings."""

from pydantic import BaseModel


class OIDCConfiguration(BaseModel):
    """OIDC config model."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str

    class ConfigDict:
        extra = "ignore"  # Ignore extra OIDC config fields


class Token(BaseModel):
    """IDP token model."""

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
    refresh_expires_in: int | None = None
