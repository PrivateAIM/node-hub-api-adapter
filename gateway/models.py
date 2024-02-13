"""Models for API."""

from pydantic import BaseModel


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


# class ScratchRequest(BaseModel):
#     """Request model for read_from_scratch."""
#
#     client_id: Annotated[str, "foo"]
#     object_id: uuid.UUID
#     settings: Annotated[project.config.Settings, None]
#     minio: Annotated[Minio, None]
