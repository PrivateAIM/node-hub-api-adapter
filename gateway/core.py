import functools
from typing import Union, Sequence

import async_timeout
from aiohttp import JsonPayload, ClientSession
from aiohttp.client_exceptions import ClientConnectorError, ContentTypeError
from fastapi import HTTPException, params, status
from fastapi.datastructures import Headers
from fastapi.requests import Request
from fastapi.responses import StreamingResponse, JSONResponse, Response

from gateway.conf import gateway_settings


async def make_request(
        url: str,
        method: str,
        headers: Union[Headers, dict],
        data: Union[JsonPayload, dict] = None,
        is_stream: bool = False,
) -> tuple[Union[JSONResponse, StreamingResponse], int]:
    """Make an asynchronous request by creating a temporary session.

    Parameters
    ----------
    url : str
        The URL of the forwarded microservice
    method : str
        HTTP method e.g. GET, POST, PUT, DELETE
    headers : Union[Headers, dict]
        A dictionary-like object defining the request headers
    data : Union[JsonPayload, dict]
        A dictionary-like object defining the payload

    Returns
    -------
    tuple[dict, int]
        Returns the response as a dictionary and an HTTP status code.

    """
    if not data:
        data = {}

    with async_timeout.timeout(gateway_settings.GATEWAY_TIMEOUT):
        if is_stream:
            async def process_response_stream():  # Need to keep session open while streaming response
                async with ClientSession() as sess:
                    req = getattr(sess, method)
                    async with req(url, json=data, headers=headers) as r:
                        async for chunk in r.content.iter_chunked(128):
                            yield chunk

            resp = StreamingResponse(process_response_stream(), media_type="application/octet-stream")
            return resp, resp.status_code

        else:
            async with ClientSession() as session:
                request = getattr(session, method)
                async with request(url, json=data, headers=headers) as resp:
                    resp_data = await resp.json()
                    return resp_data, resp.status


def route(
        request_method,
        path: str,
        service_url: str,
        status_code: int | None = None,
        payload_key: str | None = None,  # None for GET reqs, otherwise POST and match payload_key to model
        response_model: str = None,
        tags: list[str] = None,
        dependencies: Sequence[params.Depends] | None = None,
        summary: str | None = None,
        description: str | None = None,
        response_stream: bool = False,
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
    payload_key : str | None
        Reference name for the forwarded request load in the body.
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
    response_stream: bool
        Whether the expected response from the microservice is a StreamingResponse


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

            payload_obj = kwargs.get(payload_key)
            payload = payload_obj.dict() if payload_obj else {}

            microsvc_path = f"{service_url}{downstream_path}"

            try:
                resp_data, status_code_from_service = await make_request(
                    url=microsvc_path,
                    method=method,
                    data=payload,
                    headers=request.headers,
                    is_stream=response_stream,
                )

            except ClientConnectorError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service is unavailable",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            except ContentTypeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service error",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            response.status_code = status_code_from_service

            return resp_data

    return wrapper
