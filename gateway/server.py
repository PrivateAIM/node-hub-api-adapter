"""Methods for verifying auth."""

import uvicorn
from fastapi import FastAPI
from starlette import status
from starlette.middleware.cors import CORSMiddleware

from gateway.models import HealthCheck
from gateway.routers.kong import kong_router

# API metadata
tags_metadata = [
    {"name": "Results", "description": "Endpoints for the Results service."},
    {"name": "Analysis", "description": "Endpoints for the Analysis service."},
    {"name": "PodOrc", "description": "Endpoints for the Pod Orchestration service."},
    {"name": "Hub", "description": "Endpoints for the central Hub service."},
]

app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME API",
    description="Test API for FLAME project",
    # swagger_ui_init_oauth={
    #     "usePkceWithAuthorizationCodeGrant": True,
    #     # Auth fill client ID for the docs with the below value
    #     "clientId": realm_idp_settings.client_id,  # default client-id is Keycloak
    #     "clientSecret": realm_idp_settings.client_secret,
    # },
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
    "/health",
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


# app.include_router(
#     k8s_router,
# )
#
# app.include_router(
#     results_router,
# )
#
# app.include_router(
#     metadata_router,
# )
#
# app.include_router(
#     hub_router,
# )

app.include_router(
    kong_router,
)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8081)
