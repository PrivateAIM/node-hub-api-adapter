"""Models for the pod orchestrator end points."""

import uuid
from enum import Enum

from pydantic import BaseModel, RootModel


class CleanUpType(str, Enum):
    """Canned strings for cleanup endpoint"""

    all = "all"
    analyzes = "analyzes"
    services = "services"
    mb = "mb"
    rs = "rs"
    keycloak = "keycloak"
    zombies = "zombies"


class CreateAnalysis(BaseModel):
    """Required body params for PO analysis creation"""

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
    """Response for log endpoint"""

    analysis: LogReport | None = None
    nginx: LogReport | None = None


class PodResponse(RootModel[dict[uuid.UUID, list[str | None]]]):
    pass


class PodStatus(str, Enum):
    """Custom PO run statuses."""

    STARTING = "starting"
    STARTED = "started"

    STUCK = "stuck"
    RUNNING = "running"

    STOPPING = "stopping"
    STOPPED = "stopped"

    FINISHED = "finished"
    FAILED = "failed"


class AnalysisStatus(BaseModel):
    """Status report for an analysis from the PodOrchestrator"""

    status: PodStatus
    progress: int | None = None


class StatusResponse(RootModel[dict[uuid.UUID, AnalysisStatus]]):
    """Response with dynamic UUID keys and dynamic analysis keys"""

    pass


class CleanupPodResponse(BaseModel):
    """Response model for cleanup endpoint"""

    all: str | None = None
    analyzes: str | None = None
    services: str | None = None
    mb: str | None = None
    rs: str | None = None
    zombies: str | None = None
