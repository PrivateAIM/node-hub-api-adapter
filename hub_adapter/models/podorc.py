"""Models for the pod orchestrator end points."""
from pydantic import BaseModel


class CreateAnalysis(BaseModel):
    analysis_id: str
    project_id: str
    registry_url: str
    registry_user: str
    registry_password: str


class LogResponse(BaseModel):
    logs: dict | None = None


class StatusResponse(BaseModel):
    status: dict | None = None


class PodResponse(BaseModel):
    pods: dict | None = None


class CreatePodResponse(BaseModel):
    status: str
