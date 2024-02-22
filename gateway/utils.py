"""Utility methods."""
from typing import Union

from aiohttp import JsonPayload

from gateway.models import CustomFormData


def create_request_data(
        form: CustomFormData | None,
        body: JsonPayload | None
) -> Union[CustomFormData, JsonPayload] | None:
    if form:
        return form
    return body
