"""Create decorator function to apply to endpoints."""
import functools

import aiohttp
from fastapi import Request, Response, HTTPException, status

from session import make_request


def route(
    request_method,
    path: str,
    status_code: int,
    service_url: str,
    payload_key: str | None = None,  # None for GET reqs, otherwise POST and match payload_key to model
    # authentication_required: bool = False,
    response_model: str = None,
    tags: list[str] = None,
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
        HTTP status code
    service_url : str
        Root endpoint of the service for the forward request
    payload_key : str
        Reference name for the forwarded request load in the body
    response_model
        Response model of the forwarded request. Can be imported from other packages.
    tags : list[str]
        List of tags used to classify methods

    Returns
    -------
    Response from the microservice

    """

    restful_call = request_method(
        path, status_code=status_code, response_model=response_model, tags=tags
    )

    def wrapper(f):
        @restful_call  # Wrap fastapi http method decorator
        @functools.wraps(f)
        async def inner(request: Request, response: Response, **kwargs):
            service_headers = {}

            scope = request.scope

            method = scope["method"].lower()
            ep = scope["path"]

            payload_obj = kwargs.get(payload_key)
            payload = payload_obj.dict() if payload_obj else {}

            url = f"{service_url}{ep}"

            try:
                resp_data, status_code_from_service = await make_request(
                    url=url,
                    method=method,
                    data=payload,
                    headers=service_headers,
                )

            except aiohttp.client_exceptions.ClientConnectorError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service is unavailable.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            except aiohttp.client_exceptions.ContentTypeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service error.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_418_IM_A_TEAPOT,
                    detail=str(e),
                    headers={"WWW-Authenticate": "Bearer"},
                )

            response.status_code = status_code_from_service

            return resp_data

    return wrapper
