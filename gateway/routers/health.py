"""EPs for checking the API health and the health of the downstream microservices."""
import logging

from fastapi import APIRouter
from starlette import status

from gateway.conf import gateway_settings
from gateway.models.health import HealthCheck, DownstreamHealthCheck

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


@health_router.get(
    "/health/services",
    summary="Perform a Health Check on the downstream microservices",
    response_description="Return HTTP Status code for downstream services",
    status_code=status.HTTP_200_OK,
    response_model=DownstreamHealthCheck,
)
def get_health_downstream_services() -> DownstreamHealthCheck:
    """Return the health of the downstream microservices."""
    health_eps = {
        "po": gateway_settings.PODORC_SERVICE_URL.rstrip("/") + "/healthz",
        "results": gateway_settings.RESULTS_SERVICE_URL.rstrip("/") + "/healthz",
        "hub": gateway_settings.HUB_SERVICE_URL,
        "kong": gateway_settings.KONG_ADMIN_SERVICE_URL,
    }
    return health_eps
