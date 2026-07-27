"""EPs for checking the API health and the health of the downstream microservices."""

import logging
from typing import Annotated

import httpx2
from fastapi import APIRouter, Depends
from httpx2 import ConnectError, RemoteProtocolError, TimeoutException
from starlette import status

from hub_adapter.conf import Settings
from hub_adapter.constants import ServiceTag
from hub_adapter.dependencies import get_settings
from hub_adapter.schemas.health import DownstreamHealthCheck, HealthCheck

health_router = APIRouter(
    tags=[ServiceTag.HEALTH],
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
def get_health_downstream_services(
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Return the health of the downstream microservices."""
    health_eps = {
        "po": settings.podorc_service_url.rstrip("/") + "/po/healthz",
        "storage": settings.storage_service_url.rstrip("/") + "/healthz",
        "hub_core": settings.hub_service_url,
        "hub_auth": settings.hub_auth_service_url,
        "kong": settings.kong_admin_service_url.rstrip("/") + "/status",
        "idp": settings.idp_url.rstrip("/") + "/.well-known/openid-configuration",
    }

    if settings.victoria_logs_url:
        health_eps.update({"victoria_logs": settings.victoria_logs_url.rstrip("/") + "/health"})

    if settings.message_broker_url:
        health_eps.update({"message_broker": settings.message_broker_url.rstrip("/") + "/health"})

    if settings.s3_url:
        health_eps.update({"s3": settings.s3_url.rstrip("/") + "/healthz"})

    if settings.fhir_url:
        health_eps.update({"fhir": settings.fhir_url.rstrip("/") + "/health"})

    health_checks = {}
    for service, ep in health_eps.items():
        status_code, svc_status, message = None, None, None
        try:
            resp = httpx2.get(ep)
            status_code = resp.status_code
            if resp.status_code == httpx2.codes.OK:
                svc_status = "OK"

            else:
                svc_status = "ERROR"
                message = resp.text

        except (TimeoutException, RemoteProtocolError, ConnectError) as e:
            logger.error(f"Error connecting to {service} service: {e}")
            status_code = 503
            svc_status = "ERROR"
            message = repr(e)
            resp = None

        if service == "kong" and resp is not None and svc_status == "OK":
            # Kong answers 200 on /status even when it cannot reach its own database
            kong_body = resp.json()
            if not kong_body.get("database", {}).get("reachable", True):
                svc_status = "ERROR"
                message = "Kong cannot reach its database"
                status_code = 503

        health_checks[service] = {
            "status": svc_status,
            "message": message,
            "status_code": status_code,
        }

    return health_checks
