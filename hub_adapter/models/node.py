"""Models for the Node endpoints."""

from pydantic import BaseModel


class NodeSettings(BaseModel):
    data_required: bool | None = True
