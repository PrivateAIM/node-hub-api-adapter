"""Utility methods."""

import os

from fastapi import UploadFile
from fastapi.routing import serialize_response
from starlette.datastructures import FormData


def create_request_data(form: dict | None, body: dict | None) -> dict | None:
    """Package data into JSON or form depending on what is present."""
    return form or body  # If form then return form else return body i.e. JSON


async def serialize_query_content(key, value) -> dict:
    """For each key, value, serialize the content and return as such."""
    serialized_data = await serialize_response(response_content=value)
    if isinstance(serialized_data, dict):
        serialized = serialized_data

    else:
        serialized = {key: serialized_data}

    return serialized


async def unzip_query_params(
    additional_params: dict[str, any],
    necessary_params: list[str] | None = None,
    req_params=None,
) -> dict[str, any] | None:
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
    additional_params: dict[str, any],
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


async def unzip_form_params(
    additional_params: dict[str, any],
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


async def unzip_file_params(
    additional_params: dict[str, any],
    specified_params: list[str] | None = None,
) -> dict | None:
    """Gather binary or text data and package for forwarding."""
    if specified_params:
        files = {}
        for key in specified_params:
            file: UploadFile = additional_params.get(key)
            files[key] = file.file.read()

        return files


def remove_file(path: str) -> None:
    os.unlink(path)
