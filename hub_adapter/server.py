"""Methods for verifying auth."""
from typing import Annotated

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Form
from jose import jwt
from starlette import status
from starlette.middleware.cors import CORSMiddleware

from hub_adapter.auth import realm_idp_settings
from hub_adapter.models.conf import Token
from hub_adapter.routers.health import health_router
from hub_adapter.routers.hub import hub_router
from hub_adapter.routers.kong import kong_router
from hub_adapter.routers.metadata import metadata_router
from hub_adapter.routers.podorc import po_router
from hub_adapter.routers.results import results_router

# API metadata
tags_metadata = [
    {"name": "Auth", "description": "Endpoints for authorization specific tasks."},
    {"name": "Health", "description": "Endpoints for checking the health of this API and the downstream services."},
    {"name": "Hub", "description": "Endpoints for the central Hub service."},
    {"name": "Kong", "description": "Endpoints for the Kong gateway service."},
    {"name": "PodOrc", "description": "Endpoints for the Pod Orchestration service."},
    {"name": "Results", "description": "Endpoints for the Results service."},
]

app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME API",
    description="FLAME project API for interacting with various microservices within the node for the UI.",
    swagger_ui_init_oauth={
        # "usePkceWithAuthorizationCodeGrant": True,
        # Auth fill client ID for the docs with the below value
        "clientId": realm_idp_settings.client_id,  # default client-id is Keycloak
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        "identifier": "Apache-2.0",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.post(
    "/token",
    summary="Get a token from the IDP",
    tags=["Auth"],
    status_code=status.HTTP_200_OK,
    response_model=Token,
)
def get_token(
        username: Annotated[str, Form(description="Keycloak username")],
        password: Annotated[str, Form(description="Keycloak password")],
) -> Token:
    """Get a JWT from the IDP by passing a valid username and password. This token can then be used to authenticate
    yourself with this API."""
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
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=resp.json(),  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = resp.json()
    return Token(**token_data)


@app.post(
    "/token/inspect",
    summary="Get information about a provided token from the IDP",
    tags=["Auth"],
    status_code=status.HTTP_200_OK,
)
def inspect_token(
        token: Annotated[str, Form(description="JSON web token")],
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


@app.get(
    "/containers",
    status_code=status.HTTP_200_OK,
)
def fetch_containers() -> list:
    """Return information about the provided token."""
    data = [
        {
            "name": "Foo",
            "category": "TestInstance",
            "quantity": 1,
        },
        {
            "name": "API Cup",
            "category": "ShortAndStout",
            "quantity": 3,
        },
    ]
    return data


routers = (po_router, results_router, metadata_router, hub_router, kong_router, health_router)

for router in routers:
    app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8081)
