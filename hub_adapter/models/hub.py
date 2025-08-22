"""Models for Hub endpoints."""

from flame_hub.models import Analysis, MasterImage, Project, Registry, NodeType
from pydantic import BaseModel


class DetailedAnalysis(Analysis):
    """Model representing a single detailed analysis."""

    registry: Registry | None = None
    project: Project | None = None
    master_image: MasterImage | None = None


class AnalysisImageUrl(BaseModel):
    image_url: str
    project_id: str | None = None
    kong_token: str | None = None
    analysis_id: str
    registry_url: str
    registry_user: str | None = None
    registry_password: str | None = None


class NodeTypeResponse(BaseModel):
    type: NodeType
