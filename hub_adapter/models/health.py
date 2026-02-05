from pydantic import BaseModel


class HealthCheck(BaseModel):
    """Response model to validate and return when performing a health check."""

    status: str = "OK"


class DownstreamHealthCheck(BaseModel):
    """Response model for downstream health checks."""

    po: HealthCheck | str
    results: HealthCheck | str
    # hub: dict | str
    kong: HealthCheck | str
