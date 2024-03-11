"""Models for API."""
import datetime
import uuid
from typing import Optional
from uuid import UUID

# from aiohttp import FormData, multipart, hdrs, payload
from pydantic import BaseModel


# Method models
class HealthCheck(BaseModel):
    """Response model to validate and return when performing a health check."""

    status: str = "OK"


# General
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


# class GatewayFormData(FormData):
#     """Specialized form model with methods for parsing field data as well as uploaded files."""
#
#     # This method is copied from a PR to fix form data being falsely reported as not processed during redirects
#     # https://github.com/aio-libs/aiohttp/pull/5583/files
#     def _gen_form_data(self) -> multipart.MultipartWriter:
#         """Encode a list of fields using the multipart/form-data MIME format"""
#         if self._is_processed:
#             return self._writer
#
#         for dispparams, headers, value in self._fields:
#             try:
#                 if "Content-Type" in headers:
#                     part = payload.get_payload(
#                         value,
#                         content_type=headers["Content-Type"],
#                         headers=headers,
#                         encoding=self._charset,
#                     )
#
#                 else:
#                     part = payload.get_payload(
#                         value, headers=headers, encoding=self._charset
#                     )
#
#             except Exception as exc:
#                 raise TypeError(
#                     "Can not serialize value type: %r\n "
#                     "headers: %r\n value: %r" % (type(value), headers, value)
#                 ) from exc
#
#             if dispparams:
#                 part.set_content_disposition(
#                     "form-data", quote_fields=self._quote_fields, **dispparams
#                 )
#                 # FIXME cgi.FieldStorage doesn't likes body parts with
#                 # Content-Length which were sent via chunked transfer encoding
#                 assert part.headers is not None
#                 part.headers.popall("Content-Length", None)
#
#             self._writer.append_payload(part)
#
#         self._is_processed = True
#         return self._writer
#
#     def add_www_form(self, name: str, value: any):
#         """Add specific field to simple form data if needed."""
#         self.add_field(name=name, value=value)
#
#     def add_multipart_form(
#             self,
#             name: str,
#             filename: str | None,
#             value: any,
#             content_type: str | None = None,
#     ):
#         """Add specific field to multipart form data if needed."""
#         self.add_field(
#             name=name, filename=filename, value=value, content_type=content_type
#         )
#
#     async def upload(self, key, value: UploadFile | str):
#         """Asynchronously upload and read file into bytes then add to form data."""
#         if isinstance(value, UploadFile):
#             bytes_file = await value.read()
#             self.add_multipart_form(
#                 name=key,
#                 filename=value.filename,
#                 value=bytes_file,
#                 content_type=value.content_type,
#             )
#
#         elif isinstance(value, str):  # If simply a string, then add to form
#             self.add_www_form(name=key, value=value)


# Metadata models
class KeycloakConfig(BaseModel):
    """Keycloak configuration."""
    realm: str
    url: str
    clientId: str


class ContainerData(BaseModel):
    """Formatted container information."""
    id: UUID
    name: str
    job_id: UUID
    image: UUID
    state: str
    status: str
    next_tag: str
    repo: str
    train_class_id: str


class ContainerResponse(BaseModel):
    """Response model for container call."""
    containers: list[ContainerData]


class ImageData(BaseModel):
    """Image data."""
    id: UUID
    train_class_id: str
    repo_tag: str
    job_id: UUID
    status: str


class PulledImageData(ImageData):
    """Pulled image data."""
    status: str = "pulled"
    labels: Optional[dict] = None


class ToPushImageData(ImageData):
    """Data for images to be pushed."""
    status: str = "waiting_to_push"


class ImageDataResponse(BaseModel):
    """Response model for image call."""
    pullImages: list[PulledImageData]
    pushImages: list[ToPushImageData]


# Hub Models
class ProjectResponse(BaseModel):
    """Single project response model."""
    id: uuid.UUID
    name: str
    analyses: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    realm_id: uuid.UUID
    user_id: uuid.UUID
    master_image_id: uuid.UUID | None = None


class AllProjects(BaseModel):
    """List of all projects."""
    data: list[ProjectResponse]
