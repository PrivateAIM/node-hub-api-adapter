"""Utility methods."""

import json
import os

from aiohttp import JsonPayload
from fastapi.routing import serialize_response
from starlette.datastructures import FormData

from gateway.models import GatewayFormData


def create_request_data(
        form: GatewayFormData | None,
        body: JsonPayload | None
) -> GatewayFormData | JsonPayload | None:
    """Package data into JSON or form depending on what is present."""
    return form or body  # If form then return form else return body i.e. JSON


async def unzip_body_object(
        additional_params: dict[str, any],
        specified_params: list[str] | None = None,
) -> JsonPayload | None:
    """Gather body data and package for forwarding."""
    if specified_params:
        response_body_dict = {}
        for key in specified_params:
            value = additional_params.get(key)
            _body_dict = await serialize_response(response_content=value)
            response_body_dict.update(_body_dict)
        return JsonPayload(value=response_body_dict, dumps=json.dumps)


async def unzip_form_params(
        additional_params: dict[str, any],
        specified_params: list[str] | None = None,
        request_form: FormData | None = None,
) -> GatewayFormData | None:
    """Gather form data and package for forwarding."""
    if specified_params or request_form:
        body_form = GatewayFormData()
        if specified_params:
            for key in specified_params:
                value = additional_params.get(key)
                await body_form.upload(key=key, value=value)

        if request_form:
            for key in request_form:
                await body_form.upload(key=key, value=request_form[key])

        return body_form


def remove_file(path: str) -> None:
    os.unlink(path)
