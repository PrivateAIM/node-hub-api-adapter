"""Utility methods."""

import os

import jwt
from fastapi import UploadFile
from fastapi.routing import serialize_response
from starlette.datastructures import FormData
from starlette.requests import Request

from hub_adapter.models.events import EventTag


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
    req_params: dict | None = None,
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


def annotate_event(event_name: str, status_code: int, tags: list[EventTag] | None = None) -> tuple[str, list[EventTag]]:
    """Append suffix to event name indicating if request was a "success" or "failure" and add tag."""
    if status_code in (401, 403):
        log_tag = EventTag.WARNING

    elif status_code >= 400:
        log_tag = EventTag.ERROR

    else:
        log_tag = EventTag.INFO

    if tags:
        tags.append(log_tag)

    else:
        tags = [log_tag]

    suffix = ".failure" if status_code >= 400 else ".success"
    annotated_event_name = f"{event_name}{suffix}"

    return annotated_event_name, tags


def _check_data_required(node_type: str, data_requirement_setting: bool) -> bool:
    """Check if data access is required for the current node. Aggregators do not require data nor if DATA_REQUIRED is
    disabled in the settings."""
    return False if node_type == "aggregator" else data_requirement_setting
