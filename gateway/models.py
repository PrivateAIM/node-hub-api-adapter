"""Models for API."""
from project.config import Settings

from typing import Annotated

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client_id: Annotated[str, "foo"]
    settings: Annotated[Settings, None]
    minio: Annotated[any, None]  # TODO fix "any"
