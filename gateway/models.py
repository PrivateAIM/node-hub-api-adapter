"""Models for API."""

from aiohttp import FormData, multipart, hdrs, payload
from pydantic import BaseModel
from starlette.datastructures import UploadFile  # Needs to be from starlette else isinstance() fails


# Method models
class HealthCheck(BaseModel):
    """Response model to validate and return when performing a health check."""

    status: str = "OK"


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
    """Auth config model."""

    server_url: str
    realm: str
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    issuer_url: str


class GatewayFormData(FormData):
    """Specialized form model with methods for parsing field data as well as uploaded files."""

    # This method is copied from a PR to fix form data being falsely reported as not processed during redirects
    # https://github.com/aio-libs/aiohttp/pull/5583/files
    def _gen_form_data(self) -> multipart.MultipartWriter:
        """Encode a list of fields using the multipart/form-data MIME format"""
        if self._is_processed:
            return self._writer
        for dispparams, headers, value in self._fields:
            try:
                if hdrs.CONTENT_TYPE in headers:
                    part = payload.get_payload(
                        value,
                        content_type=headers[hdrs.CONTENT_TYPE],
                        headers=headers,
                        encoding=self._charset,
                    )
                else:
                    part = payload.get_payload(
                        value, headers=headers, encoding=self._charset
                    )
            except Exception as exc:
                raise TypeError(
                    "Can not serialize value type: %r\n "
                    "headers: %r\n value: %r" % (type(value), headers, value)
                ) from exc

            if dispparams:
                part.set_content_disposition(
                    "form-data", quote_fields=self._quote_fields, **dispparams
                )
                # FIXME cgi.FieldStorage doesn't likes body parts with
                # Content-Length which were sent via chunked transfer encoding
                assert part.headers is not None
                part.headers.popall(hdrs.CONTENT_LENGTH, None)

            self._writer.append_payload(part)

        self._is_processed = True
        return self._writer

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
