"""Models for Hub endpoints."""

from flame_hub.models import NodeType
from pydantic import BaseModel


class NodeTypeResponse(BaseModel):
    type: NodeType
