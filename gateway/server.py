"""Methods for verifying auth."""
import json
import logging.config
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Form
from starlette import status
from starlette.middleware.cors import CORSMiddleware

from gateway.auth import realm_idp_settings
from gateway.models import HealthCheck
from gateway.models.conf import Token
from gateway.routers.hub import hub_router
from gateway.routers.kong import kong_router
from gateway.routers.metadata import metadata_router
from gateway.routers.podorc import po_router
from gateway.routers.results import results_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Actions for lifespan of API."""
    root_dir = Path.cwd().parent
    root_dir.joinpath("logs").mkdir(parents=True, exist_ok=True)

    log_config_path = root_dir.joinpath("logging.json")
    with open(log_config_path, "r") as logf:
        log_config = json.load(logf)

    logging.config.dictConfig(log_config)

    yield


# API metadata
tags_metadata = [
    {"name": "Auth", "description": "Endpoints for authorization specific tasks."},
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
    lifespan=lifespan,
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
    po_router,
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
