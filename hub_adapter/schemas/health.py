import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    """Health of a service as reported by a live probe.

    Defined as an enum rather than a Literal so that it appears as a named schema in openapi.json
    and the frontend can import it instead of hardcoding the strings.
    """

    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ServiceCheckStatus(StrEnum):
    """Outcome of a single recorded probe. Only these two values are ever stored."""

    OK = "OK"
    ERROR = "ERROR"


class ServiceMonitoringStatus(StrEnum):
    """Whether a downstream service is being monitored on this node."""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class HealthCheck(BaseModel):
    """Response model to validate and return when performing a health check."""

    status: HealthStatus
    status_code: int | None = None
    message: str | None = None
    latency_ms: float | None = None


class DownstreamHealthCheck(BaseModel):
    """Response model for downstream health checks."""

    po: HealthCheck
    storage: HealthCheck
    hub_core: HealthCheck
    hub_auth: HealthCheck
    idp: HealthCheck
    kong: HealthCheck
    victoria_logs: HealthCheck | None = None
    message_broker: HealthCheck | None = None
    s3: HealthCheck | None = None
    fhir: HealthCheck | None = None


class ServiceHealthPoint(BaseModel):
    """A single recorded probe of a downstream service."""

    checked_at: datetime
    status: ServiceCheckStatus
    status_code: int | None = None
    latency_ms: float | None = None
    message: str | None = None
    sweep_id: uuid.UUID | None = Field(
        default=None,
        description="Identifies the probe cycle this check belongs to, shared by every service checked at the "
                    "same time",
    )


class ServiceHealthSummary(BaseModel):
    """Aggregated health of a single downstream service over the requested timeframe."""

    configured: bool = Field(description="Whether a URL is configured for this service on this node")
    status: ServiceMonitoringStatus = Field(description="DISABLED means the service is not being monitored")
    url: str | None = Field(default=None, description="Health endpoint that is probed")
    detail: str | None = Field(default=None, description="Why the service is not being monitored, if applicable")

    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    uptime_percentage: float | None = None

    min_latency_ms: float | None = None
    avg_latency_ms: float | None = None
    max_latency_ms: float | None = None

    last_status: ServiceCheckStatus | None = None
    last_status_code: int | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None

    checks_returned: int = Field(default=0, description="Number of raw datapoints included below")
    checks: list[ServiceHealthPoint] = Field(
        default_factory=list,
        description="Raw datapoints in the timeframe, newest first, capped by the limit parameter",
    )


class ServiceHealthHistory(BaseModel):
    """Response model for the stored health history of the downstream services."""

    monitoring_enabled: bool = Field(description="Whether health checks are being recorded to Postgres")
    monitoring_detail: str | None = Field(default=None, description="Why monitoring is disabled, if applicable")
    interval_seconds: int | None = Field(default=None, description="How often the services are probed")
    retention_days: int | None = Field(default=None, description="How long recorded checks are kept")
    start: datetime
    end: datetime
    services: dict[str, ServiceHealthSummary]
