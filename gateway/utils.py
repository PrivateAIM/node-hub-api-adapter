"""Utility methods."""

import os

from fastapi.routing import serialize_response
from starlette.datastructures import FormData


# from gateway.models import GatewayFormData


def create_request_data(
        form: dict | None,
        body: dict | None
) -> dict | None:
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
        all_params: dict[str, any],
        necessary_params: list[str] | None = None,
) -> dict[str, any] | None:
    """Prepare query parameters to be added to URL of downstream microservice."""
    if necessary_params:
        response_query_params = {}

        for key in necessary_params:
            value = all_params.get(key)
            serialized_dict = await serialize_query_content(key=key, value=value)
            response_query_params.update(serialized_dict)

        return response_query_params

    return


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
            response_body_dict.update(_body_dict)

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
                # await body_form.upload(key=key, value=value)
                body_form[key] = value

        if request_form:
            for key in request_form:
                # await body_form.upload(key=key, value=request_form[key])
                body_form[key] = request_form[key]

        return body_form


def remove_file(path: str) -> None:
    os.unlink(path)
