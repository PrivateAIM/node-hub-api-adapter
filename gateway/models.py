"""Models for API."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, HttpUrl
from pydantic_settings import BaseSettings


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


class MinioConnection(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str
    region: str = "us-east-1"
    use_ssl: bool = True

    model_config = ConfigDict(frozen=True)


class MinioBucketConfig(MinioConnection):
    bucket: str


class OIDCConfig(BaseModel):
    certs_url: HttpUrl
    client_id_claim_name: str = "client_id"

    model_config = ConfigDict(frozen=True)


class Settings(BaseSettings):
    minio: MinioBucketConfig
    remote: MinioBucketConfig
    oidc: OIDCConfig


class ScratchRequest(BaseModel):
    """Request model for read_from_scratch."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client_id: Annotated[str, "foo"]
    # settings: Annotated[ResultSettings, None]
    minio: Annotated[any, None]  # TODO fix "any"
