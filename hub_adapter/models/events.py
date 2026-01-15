from node_event_logging import AttributesModel
from pydantic import BaseModel
from starlette.datastructures import Address


class UserInfo(BaseModel):
    """User info model."""

    id: str | None = None
    username: str
    email: str | None = None
    client_id: str | None = None


class RequestEventLog(AttributesModel):
    """General event log class for requests."""

    method: str
    path: str
    client: Address
    user: UserInfo | None = None
    function_name: str | None = None
    service: str | None = None
