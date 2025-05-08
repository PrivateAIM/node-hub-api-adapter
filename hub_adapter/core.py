import functools
import logging
import tempfile
from collections.abc import Sequence

import httpx
from fastapi import HTTPException, params, status
from fastapi.datastructures import Headers
from fastapi.requests import Request
from fastapi.responses import JSONResponse, StreamingResponse
from httpx import ConnectError, DecodingError, HTTPStatusError
from starlette.responses import FileResponse, Response

from hub_adapter import post_processing, pre_processing
from hub_adapter.conf import hub_adapter_settings
from hub_adapter.constants import CONTENT_TYPE
from hub_adapter.utils import (
    create_request_data,
    unzip_body_object,
    unzip_file_params,
    unzip_form_params,
    unzip_query_params,
)

logger = logging.getLogger(__name__)


async def make_request(
    url: str,
    method: str,
    headers: Headers | dict,
    query: dict | None = None,
    data: dict | None = None,
    files: dict | None = None,
    file_response: bool = False,
) -> tuple[[JSONResponse | StreamingResponse], int] | tuple[FileResponse, int]:
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
    data : JsonPayload | dict | None
        A dictionary-like object defining the payload
    files : dict | Nones
        For passing on uploaded files. Should be packaged using the same form param and the read bytes
    file_response : bool
        Whether a file or stream data is expected as the response. Defaults to False

    Returns
    -------
    tuple[dict, int]
        Returns the response as a dictionary and an HTTP status code.

    """
    if not data:  # Always package data else error
        data = {}

    if not query:
        query = {}

    if not files:
        files = {}

    async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
        r = await client.request(
            url=url,
            method=method,
            params=query,
            json=data,
            files=files,
            follow_redirects=True,
        )

        logger.info(
            f'HTTP Request: {method.upper()} {r.url} "{r.http_version} {r.status_code}"',
        )

        r.raise_for_status()

        if file_response:
            with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as temp_file:
                temp_file.write(r.content)

            filename = url.split("/")[-1]  # Get the UUID of object
            return (
                FileResponse(
                    temp_file.name,
                    headers=r.headers,
                    filename=filename,
                ),
                r.status_code,
            )

        else:  # Hopefully a JSONResponse
            resp_data = r.json()
            return resp_data, r.status_code


def route(
    request_method,
    path: str,
    service_url: str,
    status_code: int | None = None,
    query_params: list[str] | None = None,
    form_params: list[str] | None = None,
    body_params: list[str] | None = None,
    file_params: list[str] | None = None,
    file_response: bool = False,
    response_model: any = None,  # TODO: Make specific for pydantic models
    tags: list[str] = None,
    dependencies: Sequence[params.Depends] | None = None,
    summary: str | None = None,
    description: str | None = None,
    pre_processing_func: str | None = None,
    post_processing_func: str | None = None,
    all_query_params: bool = False,
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
    file_params : list[str] | None
        Keys passed referencing uploaded files parameters to be sent to downstream microservice
    file_response : bool
        Whether the downstream microservice will return a file response
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
    pre_processing_func: str | None
        Method from the pre_processing module to apply to the kwargs. E.g. format_dict
    post_processing_func: str | None
        Method from the post_processing module to apply to the response. E.g. parse_something
    all_query_params: bool
        Whether to accept all query params passed within the request. Defaults to False.


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
            service_tags = scope["route"].tags or []
            downstream_path = scope["path"]

            content_type = str(request.headers.get(CONTENT_TYPE))
            www_request_form = await request.form() if "x-www-form-urlencoded" in content_type else None

            # Prune headers
            request_headers = dict(request.headers)
            request_headers.pop("content-length", None)  # Let httpx configure content-length
            request_headers.pop("content-type", None)  # Let httpx configure content-type
            request_headers.pop("host", None)

            if pre_processing_func:  # all used pp functions found in post_processing
                f = getattr(pre_processing, pre_processing_func)
                kwargs = f(kwargs)

            # Prepare query params
            wildcard_params = request.query_params if all_query_params else None
            request_query = await unzip_query_params(
                necessary_params=query_params,
                additional_params=kwargs,
                req_params=wildcard_params,
            )

            # Prepare body and form data
            request_body = await unzip_body_object(
                specified_params=body_params,
                additional_params=kwargs,
            )

            request_form = await unzip_form_params(
                request_form=www_request_form,  # Specific form passed
                specified_params=form_params,  # Specific form keys passed i.e. uploaded file
                additional_params=kwargs,
            )

            request_files = await unzip_file_params(specified_params=file_params, additional_params=kwargs)

            request_data = create_request_data(form=request_form, body=request_body)  # Either JSON or Form

            microsvc_path = f"{service_url}{downstream_path.removeprefix(hub_adapter_settings.API_ROOT_PATH)}"

            try:
                resp_data, status_code_from_service = await make_request(
                    url=microsvc_path,
                    method=method,
                    query=request_query,
                    data=request_data,
                    headers=request_headers,
                    files=request_files,
                    file_response=file_response,
                )

            except ConnectError:
                err_msg = (
                    f"HTTP Request: {method.upper()} {microsvc_path} "
                    f"- HTTP Status: {status.HTTP_503_SERVICE_UNAVAILABLE} - Service is unavailable. "
                    f"Check the {service_tags[0]} service at {service_url}"
                )
                logger.error(err_msg)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "message": err_msg,
                        "service": service_tags[0],
                        "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                ) from HTTPException

            except DecodingError:
                logger.error(
                    f"HTTP Request: {method.upper()} {microsvc_path} "
                    f'"- HTTP Status: {status.HTTP_500_INTERNAL_SERVER_ERROR} - Service error"',
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service error",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from HTTPException

            except HTTPStatusError as http_error:
                err_msg = f"HTTP Request: {method.upper()} {microsvc_path} - {http_error}"
                logger.error(err_msg)
                raise HTTPException(
                    status_code=http_error.response.status_code,
                    detail={
                        "message": err_msg,
                        "service": service_tags[0],
                        "status_code": http_error.response.status_code,
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                ) from HTTPException

            response.status_code = status_code_from_service

            if post_processing_func:  # all used pp functions found in post_processing
                f = getattr(post_processing, post_processing_func)
                resp_data = f(resp_data)

            return resp_data

    return wrapper
