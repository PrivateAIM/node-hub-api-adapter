"""Auth related endpoints."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Body, Form, HTTPException
from jose import jwt
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter.auth import realm_idp_settings
from hub_adapter.core import route
from hub_adapter.models.conf import Token

auth_router = APIRouter(
    tags=["Auth"],
    responses={404: {"description": "Not found"}},
)


@auth_router.post(
    "/token",
    summary="Get a token from the IDP",
    status_code=status.HTTP_200_OK,
    response_model=Token,
)
def get_token(
    username: Annotated[str, Form(description="Keycloak username")],
    password: Annotated[str, Form(description="Keycloak password")],
) -> Token:
    """Get a JWT from the IDP by passing a valid username and password.

    This token can then be used to authenticate
    yourself with this API. If no client ID/secret is provided, it will be autofilled using the hub adapter.
    """
    payload = {
        "username": username,
        "password": password,
        "client_id": realm_idp_settings.client_id,
        "client_secret": realm_idp_settings.client_secret,
        "grant_type": "password",
        "scope": "openid",
    }
    resp = httpx.post(realm_idp_settings.token_url, data=payload)
    if not resp.status_code == httpx.codes.OK:
        raise HTTPException(
            status_code=resp.status_code,
            detail=resp.text,  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = resp.json()
    return Token(**token_data)


@auth_router.post(
    "/token/inspect",
    summary="Get information about a provided token from the IDP",
    status_code=status.HTTP_200_OK,
)
def inspect_token(
    token: Annotated[str, Body(description="JSON web token")],
) -> dict:
    """Return information about the provided token."""
    public_key = (
        "-----BEGIN PUBLIC KEY-----\n"
        f"{httpx.get(realm_idp_settings.issuer_url).json().get('public_key')}"
        "\n-----END PUBLIC KEY-----"
    )
    decoded = jwt.decode(
        token,
        key=public_key,
        options={"verify_signature": True, "verify_aud": False, "exp": True},
    )
    return decoded


@route(
    request_method=auth_router.post,
    path="/authorize",
    # status_code=status.HTTP_200_OK,
    service_url=realm_idp_settings.authorization_url,
)
async def authorize(
    request: Request,
    response: Response,
):
    """Check token authorization."""
    pass


@route(
    request_method=auth_router.post,
    path="/userinfo",
    # status_code=status.HTTP_200_OK,
    service_url=realm_idp_settings.user_info,
)
async def user_info(
    request: Request,
    response: Response,
):
    """Get user information."""
    pass
