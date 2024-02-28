"""Models for API."""

from aiohttp import FormData
from pydantic import BaseModel
from starlette.datastructures import UploadFile  # Needs to be from starlette else isinstance() fails


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


class GatewayFormData(FormData):
    """Specialized form model with methods for parsing field data as well as uploaded files."""

    def add_www_form(self, name: str, value: any):
        """Add specific field to simple form data if needed."""
        self.add_field(name=name, value=value)

    def add_multipart_form(
            self,
            name: str,
            filename: str | None,
            value: any,
            content_type: str | None = None,
    ):
        """Add specific field to multipart form data if needed."""
        self.add_field(
            name=name, filename=filename, value=value, content_type=content_type
        )

    async def upload(self, key, value: UploadFile | str):
        """Asynchronously upload and read file into bytes then add to form data."""
        if isinstance(value, UploadFile):
            bytes_file = await value.read()
            self.add_multipart_form(
                name=key,
                filename=value.filename,
                value=bytes_file,
                content_type=value.content_type,
            )

        elif isinstance(value, str):  # If simply a string, then add to form
            self.add_www_form(name=key, value=value)
