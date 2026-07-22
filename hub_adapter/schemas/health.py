from typing import Literal

from pydantic import BaseModel


class HealthCheck(BaseModel):
    """Response model to validate and return when performing a health check."""

    status: Literal["OK", "WARNING", "ERROR", "CRITICAL"]
    status_code: int | None = None
    message: str | None = None


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
