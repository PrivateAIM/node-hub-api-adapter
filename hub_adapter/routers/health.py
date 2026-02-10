"""EPs for checking the API health and the health of the downstream microservices."""

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from httpx import ConnectError
from starlette import status

from hub_adapter.conf import Settings
from hub_adapter.dependencies import get_settings
from hub_adapter.models.health import DownstreamHealthCheck, HealthCheck

health_router = APIRouter(
    tags=["Health"],
)

logger = logging.getLogger(__name__)


@health_router.get(
    "/healthz",
    summary="Perform a Health Check",
    response_description="Return HTTP Status Code 200 (OK)",
    status_code=status.HTTP_200_OK,
    response_model=HealthCheck,
    name="health.status.get",
)
async def get_health() -> HealthCheck:
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


@health_router.get(
    "/health/services",
    summary="Perform a Health Check on the downstream microservices",
    response_description="Return HTTP Status code for downstream services",
    status_code=status.HTTP_200_OK,
    response_model=DownstreamHealthCheck,
    name="health.status.services.get",
)
def get_health_downstream_services(settings: Annotated[Settings, Depends(get_settings)]):
    """Return the health of the downstream microservices."""
    health_eps = {
        "po": settings.PODORC_SERVICE_URL.rstrip("/") + "/po/healthz",
        "results": settings.STORAGE_SERVICE_URL.rstrip("/") + "/healthz",
        # "hub": settings.HUB_SERVICE_URL,
        "kong": settings.KONG_ADMIN_SERVICE_URL.rstrip("/") + "/status",
    }

    health_checks = {}
    for service, ep in health_eps.items():
        try:
            resp = httpx.get(ep).json()

        except ConnectError as e:
            logger.error(f"Error connecting to {service} service: {e}")
            resp = str(e)

        if service == "kong":  # Returns its own response : {"database": {"reachable": true}, ...}
            if isinstance(resp, dict) and "database" in resp:
                kong_status: bool = resp.get("database").get("reachable")
                resp = {"status": "ok" if kong_status else "fail"}

        health_checks[service] = resp

    return health_checks
