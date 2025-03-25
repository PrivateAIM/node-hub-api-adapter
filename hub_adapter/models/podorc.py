"""Models for the pod orchestrator end points."""

from enum import Enum

from pydantic import BaseModel


class AnalysisStatus(Enum):
    STARTED = "started"
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


class CreateAnalysis(BaseModel):
    analysis_id: str
    project_id: str
    registry_url: str
    registry_user: str
    registry_password: str


class LogResponse(BaseModel):
    analysis: dict | None = None
    nginx: dict | None = None


class StatusResponse(BaseModel):
    status: dict | None = None


class PodResponse(BaseModel):
    pods: list | None = None


class CreatePodResponse(BaseModel):
    status: AnalysisStatus
