"""Methods for verifying auth."""
from typing import Annotated

import requests
import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from starlette import status
from starlette.middleware.cors import CORSMiddleware

from gateway.auth import realm_idp_settings
from gateway.models import HealthCheck
from gateway.models.conf import Token
from gateway.routers.hub import hub_router
from gateway.routers.k8s import k8s_router
from gateway.routers.kong import kong_router
from gateway.routers.metadata import metadata_router
from gateway.routers.results import results_router

# API metadata
tags_metadata = [
    {"name": "Results", "description": "Endpoints for the Results service."},
    {"name": "PodOrc", "description": "Endpoints for the Pod Orchestration service."},
    {"name": "Hub", "description": "Endpoints for the central Hub service."},
    {"name": "Kong", "description": "Endpoints for the Kong gateway service."},
]

app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME API",
    description="Test API for FLAME project",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        # Auth fill client ID for the docs with the below value
        "clientId": realm_idp_settings.client_id,  # default client-id is Keycloak
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


@app.get(
    "/healthz",
    tags=["healthcheck"],
    summary="Perform a Health Check",
    response_description="Return HTTP Status Code 200 (OK)",
    status_code=status.HTTP_200_OK,
    response_model=HealthCheck,
)
def get_health() -> HealthCheck:
    """
    ## Perform a Health Check
    Endpoint to perform a healthcheck on. This endpoint can primarily be used Docker
    to ensure a robust container orchestration and management is in place. Other
    services which rely on proper functioning of the API service will not deploy if this
    endpoint returns any other HTTP status code except 200 (OK).
    Returns:
        HealthCheck: Returns a JSON response with the health status
    """
    return HealthCheck(status="OK")


@app.post(
    "/token",
    summary="Get a token from the IDP",
    status_code=status.HTTP_200_OK,
    response_model=Token,
)
def get_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """Get a token from the IDP."""
    payload = {
        "username": form_data.username,
        "password": form_data.password,
        "client_id": realm_idp_settings.client_id,
        "client_secret": realm_idp_settings.client_secret,
        "grant_type": "password",
        "scope": "openid",
    }
    resp = requests.post(realm_idp_settings.token_url, data=payload)
    if not resp.ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=resp.json(),  # Invalid authentication credentials
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = resp.json()
    return Token(**token_data)


app.include_router(
    k8s_router,
)

app.include_router(
    results_router,
)

app.include_router(
    metadata_router,
)

app.include_router(
    hub_router,
)

app.include_router(
    kong_router,
)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8081)
