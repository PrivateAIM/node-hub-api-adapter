import datetime

from node_event_logging import AttributesModel
from pydantic import BaseModel
from starlette.datastructures import Address


class EventLogResponse(BaseModel):
    """Event log response model."""

    id: int
    event_name: str
    service_name: str
    timestamp: datetime.datetime
    body: str
    attributes: dict


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


class AutostartEventLog(AttributesModel):
    """Event log entry class for analyses started automatically."""

    status_code: int
    project_id: str
    analysis_id: str
