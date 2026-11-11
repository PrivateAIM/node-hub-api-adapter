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
