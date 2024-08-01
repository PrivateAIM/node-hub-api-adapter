"""Models for the pod orchestrator end points."""
from pydantic import BaseModel


class LogResponse(BaseModel):
    logs: dict | None = None


class StatusResponse(BaseModel):
    status: dict | None = None


class PodResponse(BaseModel):
    pods: dict | None = None


class CreatePodResponse(BaseModel):
    status: str
