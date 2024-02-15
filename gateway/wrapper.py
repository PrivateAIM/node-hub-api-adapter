"""Create decorator function to apply to endpoints."""
import functools

import aiohttp
from fastapi import Request, Response, HTTPException, status

from session import make_request


def route(
    request_method,
    path: str,
    status_code: int,
    payload_key: str,
    service_url: str,
    # authentication_required: bool = False,
    response_model: str = None,
    tags: list[str] = None,
):
    """
    it is an advanced wrapper for FastAPI router, purpose is to make FastAPI
    acts as a gateway API in front of anything

    Args:
        request_method: is a callable like (app.get, app.post and so on.)
        path: is the path to bind (like app.post('/api/users/'))
        status_code: expected HTTP(status.HTTP_200_OK) status code
        payload_key: used to easily fetch payload data in request body
        service_url: root endpoint for service
        # authentication_required: whether the route requires authentication via IDP
        response_model: shows return type and details on api docs
        tags: list of metadata tags

    Returns:
        wrapped endpoint result as is

    """

    restful_call = request_method(
        path, status_code=status_code, response_model=response_model, tags=tags
    )

    def wrapper(f):
        @restful_call
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

            response.status_code = status_code_from_service

            return resp_data

    return wrapper
