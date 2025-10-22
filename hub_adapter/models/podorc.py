"""Models for the pod orchestrator end points."""

import uuid
from enum import Enum

from pydantic import BaseModel, RootModel, field_validator


class CleanUpType(str, Enum):
    all = "all"
    analyzes = "analyzes"
    services = "services"
    mb = "mb"
    rs = "rs"
    keycloak = "keycloak"


class CreateAnalysis(BaseModel):
    analysis_id: str
    project_id: str
    registry_url: str
    registry_user: str
    registry_password: str
    kong_token: str
    image_url: str


class LogReport(RootModel[dict[uuid.UUID, list[str | None]]]):
    """Response with dynamic UUID keys and dynamic analysis log keys"""

    pass


class LogResponse(BaseModel):
    analysis: LogReport | None = None
    nginx: LogReport | None = None


class PodResponse(RootModel[dict[uuid.UUID, list[str | None]]]):
    pass


class PodStatus(str, Enum):
    STARTING = "starting"
    STARTED = "started"

    STUCK = "stuck"
    RUNNING = "running"

    STOPPING = "stopping"
    STOPPED = "stopped"

    FINISHED = "finished"
    FAILED = "failed"


class AnalysisStatus(BaseModel):
    """Inner structure of StatusResponse"""

    model_config = {"extra": "allow"}

    @field_validator("*")
    @classmethod
    def validate_status(cls, v):
        if v not in [status.value for status in PodStatus]:
            raise ValueError(f"Status must be one of {[s.value for s in PodStatus]}, got: {v}")
        return v


class StatusResponse(RootModel[dict[uuid.UUID, PodStatus]]):
    """Response with dynamic UUID keys and dynamic analysis keys"""

    pass


class CleanupPodResponse(BaseModel):
    all: str | None = None
    analyzes: str | None = None
    services: str | None = None
    mb: str | None = None
    rs: str | None = None
    zombies: str | None = None
