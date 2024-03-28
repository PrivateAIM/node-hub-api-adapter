"""Endpoints for the pod orchestrator."""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# Fake models for frontend
class ContainerData(BaseModel):
    """Formatted container information."""
    id: UUID
    name: str
    job_id: UUID
    image: UUID | None = None  # TODO remove null allowance
    state: str | None = None
    status: str | None = None
    next_tag: str
    repo: str
    train_class_id: str


class ContainerResponse(BaseModel):
    """Response model for container call."""
    containers: list[ContainerData]


class ImageData(BaseModel):
    """Image data."""
    id: UUID
    train_class_id: str
    repo_tag: str
    job_id: UUID
    status: str


class PulledImageData(ImageData):
    """Pulled image data."""
    status: str = "pulled"
    labels: Optional[dict] = None


class ToPushImageData(ImageData):
    """Data for images to be pushed."""
    status: str = "waiting_to_push"


class ImageDataResponse(BaseModel):
    """Response model for image call."""
    pullImages: list[PulledImageData]
    pushImages: list[ToPushImageData]
