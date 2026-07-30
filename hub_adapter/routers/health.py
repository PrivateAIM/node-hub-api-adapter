"""EPs for checking the API health and the health of the downstream microservices."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import peewee as pw
from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status
from starlette.concurrency import run_in_threadpool

from hub_adapter.conf import Settings
from hub_adapter.constants import ServiceTag
from hub_adapter.dependencies import get_settings
from hub_adapter.schemas.health import (
    DownstreamHealthCheck,
    HealthCheck,
    HealthStatus,
    ServiceCheckStatus,
    ServiceHealthHistory,
    ServiceHealthPoint,
    ServiceHealthSummary,
    ServiceMonitoringStatus,
)
from hub_adapter.service_health import (
    build_probe_targets,
    fetch_checks,
    fetch_last_checks,
    probe_all,
    summarize_range,
)

health_router = APIRouter(
    tags=[ServiceTag.HEALTH],
)

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_WINDOW = timedelta(days=1)


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
    Returns:
        HealthCheck: Returns a JSON response with the health status
    """
    return HealthCheck(status=HealthStatus.OK)


@health_router.get(
    "/health/services",
    summary="Perform a Health Check on the downstream microservices",
    response_description="Return HTTP Status code for downstream services",
    status_code=status.HTTP_200_OK,
    response_model=DownstreamHealthCheck,
    name="health.status.services.get",
)
async def get_health_downstream_services(
        settings: Annotated[Settings, Depends(get_settings)],
):
    """Return the health of the downstream microservices."""
    return await probe_all(settings)


@health_router.get(
    "/health/services/history",
    summary="Fetch the recorded health of the downstream microservices",
    response_description="Per service uptime, latency statistics and raw datapoints for a timeframe",
    status_code=status.HTTP_200_OK,
    response_model=ServiceHealthHistory,
    name="health.status.services.history.get",
)
async def get_health_downstream_services_history(
        settings: Annotated[Settings, Depends(get_settings)],
        start_date: Annotated[
            datetime | None,
            Query(description="Fetch checks from this timestamp using ISO8601 format. Defaults to 24 hours ago"),
        ] = None,
        end_date: Annotated[
            datetime | None,
            Query(description="Fetch checks up to this timestamp using ISO8601 format. Defaults to now"),
        ] = None,
        service: Annotated[
            list[str] | None,
            Query(description="Limit the response to these services. Can be repeated. Defaults to all services"),
        ] = None,
        include_checks: Annotated[
            bool,
            Query(description="Whether to include the raw datapoints alongside the summary"),
        ] = True,
        limit: Annotated[
            int,
            Query(gt=0, le=10000, description="Maximum number of raw datapoints to return per service, newest first"),
        ] = 500,
):
    """Return the recorded health of the downstream microservices within a timeframe.

    Checks are recorded by a background routine which requires Postgres. When no database connection could be made
    at startup, monitoring_enabled is false and monitoring_detail explains why.

    Services with no URL configured on this node are reported as "disabled".
    """
    from hub_adapter.managers import service_health_monitor  # avoid a circular import

    end = _as_utc(end_date) or datetime.now(UTC)
    start = _as_utc(start_date) or end - DEFAULT_HISTORY_WINDOW

    if start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "start_date must be earlier than end_date",
                "service": ServiceTag.HEALTH.value,
                "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            },
        )

    targets = build_probe_targets(settings)

    if service:
        unknown = sorted(set(service) - set(targets))
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": f"Unknown service(s): {', '.join(unknown)}. Valid services: {', '.join(targets)}",
                    "service": ServiceTag.HEALTH.value,
                    "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
                },
            )
        targets = {name: url for name, url in targets.items() if name in set(service)}

    services = {
        name: ServiceHealthSummary(
            configured=bool(url),
            status=ServiceMonitoringStatus.ACTIVE if url else ServiceMonitoringStatus.DISABLED,
            url=url,
            detail=None if url else "No URL configured for this service on this node",
        )
        for name, url in targets.items()
    }

    response = ServiceHealthHistory(
        monitoring_enabled=service_health_monitor.enabled,
        monitoring_detail=service_health_monitor.disabled_reason,
        interval_seconds=service_health_monitor.interval if service_health_monitor.enabled else None,
        retention_days=service_health_monitor.retention_days if service_health_monitor.enabled else None,
        start=start,
        end=end,
        services=services,
    )

    if not service_health_monitor.enabled:
        return response

    monitored = [name for name, summary in services.items() if summary.configured]

    try:
        # Peewee is synchronous, so the queries run in a worker thread to keep the event loop free
        summaries = await run_in_threadpool(
            summarize_range, service_health_monitor.database, start, end, monitored
        )
        last_checks = await run_in_threadpool(
            fetch_last_checks, service_health_monitor.database, start, end, monitored
        )
        raw_checks = (
            await run_in_threadpool(fetch_checks, service_health_monitor.database, start, end, monitored, limit)
            if include_checks
            else {}
        )

    except pw.PeeweeException as db_err:
        logger.error(f"Unable to fetch the service health history: {db_err}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": f"Unable to fetch the service health history from the database: {db_err}",
                "service": ServiceTag.HEALTH.value,
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            },
        ) from db_err

    for name in monitored:
        summary = services[name]

        for field, value in summaries.get(name, {}).items():
            setattr(summary, field, value)

        if last_check := last_checks.get(name):
            summary.last_status = last_check["status"]
            summary.last_status_code = last_check["status_code"]
            summary.last_checked_at = last_check["checked_at"]
            summary.last_error = last_check["message"] if last_check["status"] != ServiceCheckStatus.OK else None

        summary.checks = [ServiceHealthPoint.model_validate(check) for check in raw_checks.get(name, [])]
        summary.checks_returned = len(summary.checks)

    return response


def _as_utc(timestamp: datetime | None) -> datetime | None:
    """Treat a naive timestamp as UTC so it can be compared against the stored values."""
    if timestamp is None:
        return None

    return timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp
