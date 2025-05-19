"""Auth related endpoints."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Form, HTTPException
from starlette import status

from hub_adapter.auth import user_oidc_config
from hub_adapter.conf import hub_adapter_settings
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
        "client_id": hub_adapter_settings.API_CLIENT_ID,
        "client_secret": hub_adapter_settings.API_CLIENT_SECRET,
        "grant_type": "password",
        "scope": "openid",
    }
    resp = httpx.post(user_oidc_config.token_endpoint, data=payload)
    if not resp.status_code == httpx.codes.OK:
        raise HTTPException(
            status_code=resp.status_code,
            detail=resp.text,  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = resp.json()
    return Token(**token_data)
