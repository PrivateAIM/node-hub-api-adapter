"""Models for API."""

from pydantic import BaseModel


# Method models
class User(BaseModel):
    """Example User output"""

    id: str
    username: str
    email: str | None
    first_name: str
    last_name: str
    realm_roles: list | None
    client_roles: list | None


class AuthConfiguration(BaseModel):
    """Example auth config."""

    server_url: str
    realm: str
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    issuer_url: str


class ScratchRequest(BaseModel):
    """Request model for read_from_scratch."""

    client_id: str = "575a9ab0-2204-47c2-af7c-bb9f9b3390d5"
