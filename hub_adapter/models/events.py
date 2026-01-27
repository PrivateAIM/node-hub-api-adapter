import datetime
from enum import Enum

from node_event_logging import AttributesModel
from pydantic import BaseModel
from starlette.datastructures import Address


class EventTag(str, Enum):
    """Event tag model."""

    # Services
    HUB = "Hub"
    HUB_ADAPTER = "Hub Adapter"
    PO = "Pod Orchestrator"
    STORAGE = "Storage"
    KONG = "Kong"
    AUTH = "Authentication"
    AUTOSTART = "Autostart"

    USER_AUTH = "User Authentication Required"

    # Log levels
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"


class EventLog(BaseModel):
    """Event log response model."""

    id: int
    event_name: str
    service_name: str
    timestamp: datetime.datetime
    body: str
    attributes: dict


class Meta(BaseModel):
    """Event log metadata model."""

    count: int
    total: int
    limit: int
    offset: int


class EventLogResponse(BaseModel):
    """Event log response model."""

    data: list[EventLog]
    meta: Meta


# For logging events
class UserInfo(BaseModel):
    """User info model."""

    id: str | None = None
    username: str
    email: str | None = None
    client_id: str | None = None


class GatewayEventLog(AttributesModel):
    """General event log class for requests."""

    method: str
    path: str
    url: str
    client: Address
    user: UserInfo | None = None
    service: str | None = None
    status_code: int | None = None
    tags: list[EventTag] | None = None


class AutostartEventLog(AttributesModel):
    """Event log entry class for analyses started automatically."""

    status_code: int
    project_id: str
    analysis_id: str
    tags: list[EventTag] | None = None
