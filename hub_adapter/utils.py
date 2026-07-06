"""Utility methods."""

import os
import re
import uuid

import jwt
from fastapi import UploadFile
from fastapi.routing import serialize_response
from starlette.datastructures import FormData, QueryParams
from starlette.requests import Request

from hub_adapter.user_settings import load_persistent_settings


def create_request_data(form: dict | None, body: dict | None) -> dict | None:
    """Package data into JSON or form depending on what is present."""
    return form or body  # If form then return form else return body i.e. JSON


async def serialize_query_content(key, value) -> dict:
    """For each key, value, serialize the content and return as such."""
    serialized_data = await serialize_response(response_content=value)
    serialized = serialized_data if isinstance(serialized_data, dict) else {key: serialized_data}

    return serialized


async def unzip_query_params(
    additional_params: dict,
    necessary_params: list[str] | None = None,
    req_params: dict | QueryParams | None = None,
) -> dict:
    """Prepare query parameters to be added to URL of downstream microservice."""
    response_query_params = {}

    if req_params:
        for k, v in req_params.items():
            serialized_dict = await serialize_query_content(key=k, value=v)
            response_query_params.update(serialized_dict)

    elif necessary_params:
        for key in necessary_params:
            value = additional_params.get(key)

            if not value:  # if value is None, then skip
                continue

            serialized_dict = await serialize_query_content(key=key, value=value)
            response_query_params.update(serialized_dict)

    return response_query_params


async def unzip_body_object(
    additional_params: dict,
    specified_params: list[str] | None = None,
) -> dict | None:
    """Gather body data and package for forwarding."""
    if specified_params:
        response_body_dict = {}

        for key in specified_params:
            value = additional_params.get(key)
            _body_dict = await serialize_response(response_content=value)
            response_body_dict[key] = _body_dict

        return response_body_dict
    return None


async def unzip_form_params(
    additional_params: dict,
    specified_params: list[str] | None = None,
    request_form: FormData | None = None,
) -> dict | None:
    """Gather form data and package for forwarding."""
    if specified_params or request_form:
        body_form = dict()
        if specified_params:
            for key in specified_params:
                value = additional_params.get(key)
                _form_dict = await serialize_response(response_content=value)
                body_form[key] = _form_dict

        if request_form:
            for key in request_form:
                body_form[key] = request_form[key]

        return body_form
    return None


async def unzip_file_params(
    additional_params: dict,
    specified_params: list[str] | None = None,
) -> dict | None:
    """Gather binary or text data and package for forwarding."""
    if specified_params:
        files = {}
        for key in specified_params:
            file: UploadFile = additional_params.get(key)
            if file:
                files[key] = file.file.read()

        return files
    return None


def remove_file(path: str) -> None:
    os.unlink(path)


def _extract_user_from_token(request: Request) -> dict | None:
    """Extract user information from JWT token in request headers."""
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.replace("Bearer ", "")

    try:
        decoded_token = jwt.decode(token, options={"verify_signature": False})

        # Extract common user identifiers from JWT
        user_info = {
            "id": decoded_token.get("sub"),  # Subject (user ID)
            "username": decoded_token.get("preferred_username") or decoded_token.get("username"),
            "email": decoded_token.get("email"),
            "client_id": decoded_token.get("azp") or decoded_token.get("client_id"),  # For service accounts
        }

        # Remove None values
        return {k: v for k, v in user_info.items() if v is not None}

    except (jwt.DecodeError, jwt.InvalidTokenError):
        return None


def _check_data_required(node_type: str) -> bool:
    """Check if data access is required for the current node. Aggregators do not require data nor if DATA_REQUIRED is
    disabled in the settings."""
    node_settings = load_persistent_settings()
    return False if node_type == "aggregator" else node_settings.require_data_store


# Kong utility functions and definitions

HEALTH_TAG = "health"

# Kong can use ',' and '/' in tags
_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._~-]+$")


def is_uuid(value: str) -> bool:
    """Return True if the value parses as a UUID."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def validate_datastore_name(name: str) -> str:
    """Validate an admin-chosen data store display name, returning it unchanged."""
    if not name or not _NAME_PATTERN.match(name):
        raise ValueError(f"Invalid data store name {name!r}: only letters, digits, '.', '_', '~', and '-' are allowed")

    if is_uuid(name):
        raise ValueError(f"Invalid data store name {name!r}: bare UUIDs cannot be used as names")

    return name


def project_tag(project_id: str | uuid.UUID) -> str:
    return f"project:{project_id}"


def datastore_tag(service_id: str | uuid.UUID) -> str:
    return f"datastore:{service_id}"


def type_tag(ds_type) -> str:
    ds = ds_type.value if hasattr(ds_type, "value") else ds_type
    return f"type:{ds}"


def analysis_tag(analysis_id: str | uuid.UUID) -> str:
    return f"analysis:{analysis_id}"


def analysis_username(analysis_id: str | uuid.UUID) -> str:
    return f"analysis-{analysis_id}"


def health_username(project_id: str | uuid.UUID) -> str:
    return f"health-{project_id}"


def link_path(project_id: str | uuid.UUID, service_id: str | uuid.UUID) -> str:
    return f"/{project_id}/{service_id}"


def parse_tags(tags: list[str] | None) -> dict[str, str]:
    """Parse ['project:abc', 'health'] into {'project': 'abc'}; valueless tags are skipped."""
    parsed = {}
    for tag in tags or []:
        key, sep, value = tag.partition(":")
        if sep:
            parsed[key] = value

    return parsed
