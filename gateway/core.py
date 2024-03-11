import functools
from typing import Sequence

import httpx
from fastapi import HTTPException, params, status
from fastapi.datastructures import Headers
from fastapi.requests import Request
from fastapi.responses import StreamingResponse, JSONResponse
from httpx import ConnectError, DecodingError
from starlette.responses import Response

from gateway.constants import CONTENT_TYPE
# from gateway.models import GatewayFormData
from gateway.utils import unzip_form_params, unzip_body_object, create_request_data, unzip_query_params


async def make_request(
        url: str,
        method: str,
        headers: Headers | dict,
        query: dict | None = None,
        data: dict | None = None,
) -> tuple[[JSONResponse | StreamingResponse], int]:
    """Make an asynchronous request by creating a temporary session.

    Parameters
    ----------
    url : str
        The URL of the forwarded microservice
    method : str
        HTTP method e.g. GET, POST, PUT, DELETE
    headers : Headers | dict
        A dictionary-like object defining the request headers
    query : dict | None
        Serialized query parameters to be added to the request.
    data : JsonPayload | dict | GatewayFormData | None
        A dictionary-like object defining the payload

    Returns
    -------
    tuple[dict, int]
        Returns the response as a dictionary and an HTTP status code.

    """
    if not data:  # Always package data else error
        data = {}

    if not query:
        query = {}

    async with httpx.AsyncClient(headers=headers) as client:
        r = await client.request(url=url, method=method, params=query, data=data)
        resp_data = r.json()
        return resp_data, r.status_code

    # with async_timeout.timeout(gateway_settings.GATEWAY_TIMEOUT):
    #     async with ClientSession(headers=headers) as session:
    #         async with session.request(url=url, method=method, data=data) as resp:
    #
    #             if hdrs.CONTENT_TYPE not in resp.headers or resp.headers[hdrs.CONTENT_TYPE] == 'application/json':
    #                 resp_data = await resp.json()
    #                 return resp_data, resp.status
    #
    #             elif resp.headers[hdrs.CONTENT_TYPE] == 'application/octet-stream':
    #                 with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as temp_file:
    #                     async for chunk, _ in resp.content.iter_chunks():  # iterates over chunks received from microsvc
    #                         temp_file.write(chunk)
    #
    #                 def cleanup():
    #                     os.remove(temp_file.name)
    #
    #                 return FileResponse(
    #                     temp_file.name,
    #                     background=BackgroundTask(cleanup),
    #                     headers=resp.headers
    #                 ), resp.status


def route(
        request_method,
        path: str,
        service_url: str,
        status_code: int | None = None,
        query_params: list[str] | None = None,
        form_params: list[str] | None = None,
        body_params: list[str] | None = None,
        response_model: any = None,  # TODO: Make specific for pydantic models
        tags: list[str] = None,
        dependencies: Sequence[params.Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
        # params from fastapi http methods can be added here later and then added to `request_method()`
):
    """A decorator for the FastAPI router, its purpose is to make FastAPI
    acts as a gateway API in front of available microservices.

    Parameters
    ----------
    request_method
        FastAPI HTTP method e.g. 'app.get' or 'app.post'
    path : str
        Downstream path to route request to (e.g. '/api/users/')
    status_code : int
        HTTP status code.
    service_url : str
        Root endpoint of the microservice for the forwarded request.
    query_params : list[str] | None
        Keys passed referencing query model parameters to be sent to downstream microservice
    form_params : list[str] | None
        Keys passed referencing form model parameters to be sent to downstream microservice
    body_params : list[str] | None
        Keys passed referencing body data parameters to be sent to downstream microservice
    response_model
        Response model of the forwarded request. Can be imported from other packages.
    tags : list[str]
        List of tags used to classify methods
    dependencies: Sequence[params.Depends] | None
        Other methods required for this to work. E.g. An IDP token.
    summary: str | None
        Summary of the method (usually short).
    description: str | None
        Longer explanation of the method.


    Returns
    -------
    Response from the microservice

    """

    restful_call = request_method(
        path,
        status_code=status_code,
        response_model=response_model,
        tags=tags,
        dependencies=dependencies,
        summary=summary,
        description=description,
    )

    def wrapper(func):
        @restful_call  # Wrap fastapi http method decorator
        @functools.wraps(func)
        async def inner(request: Request, response: Response, **kwargs):
            scope = request.scope
            method = scope["method"].lower()

            downstream_path = scope['path']

            content_type = str(request.headers.get(CONTENT_TYPE))
            www_request_form = await request.form() if 'x-www-form-urlencoded' in content_type else None

            # Prune headers
            request_headers = dict(request.headers)
            request_headers.pop("content-length", None)  # Let aiohttp configure content-length
            request_headers.pop("content-type", None)  # Let aiohttp configure content-type
            request_headers.pop("host", None)

            # Prepare query params
            request_query = await unzip_query_params(
                necessary_params=query_params, all_params=kwargs
            )

            # Prepare body and form data
            request_body = await unzip_body_object(
                specified_params=body_params,
                additional_params=kwargs,
            )

            request_form = await unzip_form_params(
                request_form=www_request_form,  # Specific form passed
                specified_params=form_params,  # Specific form keys passed i.e. uploaded file
                additional_params=kwargs
            )

            request_data = create_request_data(form=request_form, body=request_body)  # Either JSON or Form

            microsvc_path = f"{service_url}{downstream_path}"

            try:
                resp_data, status_code_from_service = await make_request(
                    url=microsvc_path,
                    method=method,
                    query=request_query,
                    data=request_data,
                    headers=request_headers,
                )

            except ConnectError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service is unavailable",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            except DecodingError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service error",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            response.status_code = status_code_from_service

            return resp_data

    return wrapper
