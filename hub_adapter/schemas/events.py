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
    UI = "UI"
    STORAGE = "Storage"
    KONG = "Kong"
    AUTH = "Authentication"
    AUTOSTART = "Autostart"
    NODE = "Node"

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


# Events
## Keys are the event name and the value is a human-readable description of the event
AGNOSTIC_EVENTS = {
    "auth.token.get": {
        "body": "A user attempted to sign in to the IDP and acquire a JWT",
        "tags": [EventTag.AUTH],
        "model": GatewayEventLog,
    },
    "auth.user.signin": {
        "body": "A user signed in to the Node UI",
        "tags": [EventTag.AUTH],
        "model": GatewayEventLog,
    },
    "auth.user.signout": {
        "body": "A user manually signed out of the Node UI",
        "tags": [EventTag.AUTH],
        "model": GatewayEventLog,
    },
    "hub.project.get": {
        "body": "A user requested a list of projects from the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.project.node.get": {
        "body": "A user requested a list of node-specific projects from the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.project.node.update": {
        "body": "A user attempted to update the approval status of a node in the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.analysis.get": {
        "body": "A user requested a list of analyses from the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.analysis.update": {
        "body": "A user attempted to update the approval status of an analysis in the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.analysis.node.get": {
        "body": "A user requested a list of node-specific analyses from the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.analysis.node.update": {
        "body": "A user attempted to update the approval status of an node-specific analysis in the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.analysis.image.get": {
        "body": "A request for the URL of an analysis was sent to the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.analysis.bucket.get": {
        "body": "A user requested a list of buckets for an analysis from the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.analysis.bucket.file.get": {
        "body": "A user requested a list of files for an analysis from the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.node.get": {
        "body": "A user requested a list of nodes from the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.node.type.get": {
        "body": "A request was sent for the type of node",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "hub.registry.metadata.get": {
        "body": "A user requested the registry metadata for a project from the Hub",
        "tags": [EventTag.HUB],
        "model": GatewayEventLog,
    },
    "podorc.logs.get": {
        "body": "A user requested the logs for an analysis from the Pod Orchestrator",
        "tags": [EventTag.PO],
        "model": GatewayEventLog,
    },
    "podorc.history.get": {
        "body": "A user requested the log history for an analysis from the Pod Orchestrator",
        "tags": [EventTag.PO],
        "model": GatewayEventLog,
    },
    "podorc.status.get": {
        "body": "A user requested a status update for an analysis pod from the Pod Orchestrator",
        "tags": [EventTag.PO],
        "model": GatewayEventLog,
    },
    "podorc.pods.create": {
        "body": "A user sent a request to start an analysis pod to the Pod Orchestrator",
        "tags": [EventTag.PO],
        "model": GatewayEventLog,
    },
    "podorc.pods.get": {
        "body": "A user requested a list of analysis pods from the Pod Orchestrator",
        "tags": [EventTag.PO],
        "model": GatewayEventLog,
    },
    "podorc.pods.stop": {
        "body": "A user sent a request to stop an analysis pod to the Pod Orchestrator",
        "tags": [EventTag.PO],
        "model": GatewayEventLog,
    },
    "podorc.pods.delete": {
        "body": "A user sent a request to delete an analysis pod to the Pod Orchestrator",
        "tags": [EventTag.PO],
        "model": GatewayEventLog,
    },
    "podorc.cleanup": {
        "body": "A user sent a cleanup request to the Pod Orchestrator",
        "tags": [EventTag.PO],
        "model": GatewayEventLog,
    },
    "kong.datastore.get": {
        "body": "A user requested a list of datastores (services) from Kong",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.datastore.create": {
        "body": "A user sent a request to create a datastore to Kong",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.datastore.delete": {
        "body": "A user sent a request to delete a datastore to Kong",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.project.get": {
        "body": "A user requested a list of projects (routes) from Kong",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.project.create": {
        "body": "A user sent a request to create a project to Kong",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.project.delete": {
        "body": "A user sent a request to delete a project to Kong",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.analysis.get": {
        "body": "A user requested a list of analyses (consumers) from Kong",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.analysis.create": {
        "body": "A user sent a request to create a analysis to Kong",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.analysis.delete": {
        "body": "A user sent a request to delete a analysis to Kong",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.initialize": {
        "body": "A user sent a request to create a datastore and link a project to it",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "kong.probe": {
        "body": "A user requested the status of a datastore",
        "tags": [EventTag.KONG],
        "model": GatewayEventLog,
    },
    "meta.initialize": {
        "body": "A user sent a request to start an analysis to the Pod Orchestrator and Kong",
        "tags": [EventTag.KONG, EventTag.PO],
        "model": GatewayEventLog,
    },
    "meta.terminate": {
        "body": "A user sent a request to delete an analysis to the Pod Orchestrator and Kong",
        "tags": [EventTag.KONG, EventTag.PO],
        "model": GatewayEventLog,
    },
    "node.settings.get": {
        "body": "A user fetched the node's configurations settings",
        "tags": [EventTag.HUB_ADAPTER, EventTag.NODE],
        "model": GatewayEventLog,
    },
    "node.settings.update": {
        "body": "A user updated the node's configurations settings",
        "tags": [EventTag.HUB_ADAPTER, EventTag.NODE],
        "model": GatewayEventLog,
    },
    "health.status.get": {
        "body": "An API health check was requested from the Hub Adapter API",
        "tags": [EventTag.HUB_ADAPTER, EventTag.NODE],
        "model": GatewayEventLog,
    },
    "health.status.services.get": {
        "body": "An API health check for downstream services was requested from the Hub Adapter API",
        "tags": [EventTag.KONG, EventTag.PO, EventTag.STORAGE],
        "model": GatewayEventLog,
    },
    "storage.local.delete": {
        "body": "A user sent a request to delete local results to the Storage Service",
        "tags": [EventTag.STORAGE],
        "model": GatewayEventLog,
    },
    "events.get": {
        "body": "A user requested a list of events from the event log",
        "tags": [EventTag.HUB_ADAPTER],
        "model": GatewayEventLog,
    },
    "autostart.analysis.create": {
        "body": "The Hub Adapter automatically sent a request to start an analysis to the Pod Orchestrator",
        "tags": [EventTag.AUTOSTART, EventTag.KONG, EventTag.PO],
        "model": AutostartEventLog,
    },
}
ANNOTATED_EVENTS = {
    "unknown": {"body": "An unknown event has occurred", "tags": [EventTag.WARNING], "model": GatewayEventLog},
    "api.ui.access": {
        "body": "The API Swagger UI was accessed",
        "tags": [EventTag.HUB_ADAPTER],
        "model": GatewayEventLog,
    },
}

# Add .success and .failure to all
for event_name, event_body in AGNOSTIC_EVENTS.items():
    ANNOTATED_EVENTS.update({f"{event_name}.success": event_body, f"{event_name}.failure": event_body})
