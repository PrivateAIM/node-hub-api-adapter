"""Models for API."""
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from minio import Minio
from fastapi.encoders import jsonable_encoder
from project.config import MinioBucketConfig, Settings as ResultSettings

from pydantic import BaseModel, ConfigDict, HttpUrl, BeforeValidator

from pydantic import (
    AfterValidator,
    PlainSerializer,
    TypeAdapter,
    WithJsonSchema,
)


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


def convert_url(settings: ResultSettings) -> ResultSettings:
    """Convert the Url class to str to avoid breaking pydantic. The HttpUrl model in pydantic has a bug currently in
    which it doesn't properly convert to a str during validation and this is a temporary workaround."""
    settings.oidc.certs_url = str(settings.oidc.certs_url)
    return settings


class ScratchRequest(BaseModel):
    """Request model for read_from_scratch."""

    client_id: str = "575a9ab0-2204-47c2-af7c-bb9f9b3390d5"
    # settings: Annotated[ResultSettings, AfterValidator(convert_url)]
    # settings: dict
    # minio: MinioBucketConfig
