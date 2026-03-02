"""Endpoints for manually retrieving an JWT."""

import ssl
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException
from starlette import status

from hub_adapter.auth import get_ssl_context
from hub_adapter.conf import Settings
from hub_adapter.dependencies import get_settings
from hub_adapter.models.conf import Token
from hub_adapter.oidc import get_svc_oidc_config

auth_router = APIRouter(
    tags=["Auth"],
    responses={404: {"description": "Not found"}},
)


@auth_router.post(
    "/token",
    summary="Get a token from the IDP",
    status_code=status.HTTP_200_OK,
    response_model=Token,
    name="auth.token.get",
)
def get_token(
    settings: Annotated[Settings, Depends(get_settings)],
    username: Annotated[str, Form(description="Keycloak username")],
    password: Annotated[str, Form(description="Keycloak password")],
    ssl_ctx: Annotated[ssl.SSLContext, Depends(get_ssl_context)],
) -> Token:
    """Get a JWT from the IDP by passing a valid username and password.

    This token can then be used to authenticate
    yourself with this API. If no client ID/secret is provided, it will be autofilled using the hub adapter.
    """
    payload = {
        "username": username,
        "password": password,
        "client_id": settings.api_client_id,
        "client_secret": settings.api_client_secret,
        "grant_type": "password",
        "scope": "openid",
    }
    oidc_config = get_svc_oidc_config()
    with httpx.Client(verify=ssl_ctx) as client:
        resp = client.post(oidc_config.token_endpoint, data=payload)

    if not resp.status_code == httpx.codes.OK:
        raise HTTPException(
            status_code=resp.status_code,
            detail=resp.text,  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = resp.json()
    return Token(**token_data)
