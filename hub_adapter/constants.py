"""Constants."""

from hub_adapter.models.events import EventTag

CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"

SERVICE_NAME = "hub_adapter"  # Name of this service

# Hub Keywords
ID = "id"
HOST = "host"
NODE = "node"
NODE_ID = "NODE_ID"
REGISTRY = "registry"
ACCOUNT_NAME = "account_name"
EXTERNAL_NAME = "external_name"
ACCOUNT_SECRET = "account_secret"
REGISTRY_PROJECT = "registry_project"
REGISTRY_PROJECT_ID = "registry_project_id"

# Events
## Keys are the event name and the value is a human-readable description of the event
AGNOSTIC_EVENTS = {
    "auth.token.get": {
        "body": "A user attempted to sign in to the IDP and acquire a JWT",
        "tags": [EventTag.AUTH],
    },
    "hub.project.get": {
        "body": "A user requested a list of projects from the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.project.node.get": {
        "body": "A user requested a list of node-specific projects from the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.project.node.update": {
        "body": "A user attempted to update the approval status of a node in the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.analysis.get": {
        "body": "A user requested a list of analyses from the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.analysis.update": {
        "body": "A user attempted to update the approval status of an analysis in the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.analysis.node.get": {
        "body": "A user requested a list of node-specific analyses from the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.analysis.node.update": {
        "body": "A user attempted to update the approval status of an node-specific analysis in the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.analysis.image.get": {
        "body": "A request for the URL of an analysis was sent to the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.analysis.bucket.get": {
        "body": "A user requested a list of buckets for an analysis from the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.analysis.bucket.file.get": {
        "body": "A user requested a list of files for an analysis from the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.node.get": {
        "body": "A user requested a list of nodes from the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.node.type.get": {
        "body": "A request was sent for the type of node",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "hub.registry.metadata.get": {
        "body": "A user requested the registry metadata for a project from the Hub",
        "tags": [EventTag.USER_AUTH, EventTag.HUB],
    },
    "podorc.logs.get": {
        "body": "A user requested the logs for an analysis from the Pod Orchestrator",
        "tags": [EventTag.USER_AUTH, EventTag.PO],
    },
    "podorc.history.get": {
        "body": "A user requested the log history for an analysis from the Pod Orchestrator",
        "tags": [EventTag.USER_AUTH, EventTag.PO],
    },
    "podorc.status.get": {
        "body": "A user requested a status update for an analysis pod from the Pod Orchestrator",
        "tags": [EventTag.USER_AUTH, EventTag.PO],
    },
    "podorc.pods.create": {
        "body": "A user sent a request to start an analysis pod to the Pod Orchestrator",
        "tags": [EventTag.USER_AUTH, EventTag.PO],
    },
    "podorc.pods.get": {
        "body": "A user requested a list of analysis pods from the Pod Orchestrator",
        "tags": [EventTag.USER_AUTH, EventTag.PO],
    },
    "podorc.pods.stop": {
        "body": "A user sent a request to stop an analysis pod to the Pod Orchestrator",
        "tags": [EventTag.USER_AUTH, EventTag.PO],
    },
    "podorc.pods.delete": {
        "body": "A user sent a request to delete an analysis pod to the Pod Orchestrator",
        "tags": [EventTag.USER_AUTH, EventTag.PO],
    },
    "podorc.cleanup": {
        "body": "A user sent a cleanup request to the Pod Orchestrator",
        "tags": [EventTag.USER_AUTH, EventTag.PO],
    },
    "kong.datastore.get": {
        "body": "A user requested a list of datastores (services) from Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.datastore.create": {
        "body": "A user sent a request to create a datastore to Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.datastore.delete": {
        "body": "A user sent a request to delete a datastore to Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.project.get": {
        "body": "A user requested a list of projects (routes) from Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.project.create": {
        "body": "A user sent a request to create a project to Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.project.delete": {
        "body": "A user sent a request to delete a project to Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.analysis.get": {
        "body": "A user requested a list of analyses (consumers) from Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.analysis.create": {
        "body": "A user sent a request to create a analysis to Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.analysis.delete": {
        "body": "A user sent a request to delete a analysis to Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.initialize": {
        "body": "A user sent a request to create a datastore and link a project to it",
        "tags": [EventTag.USER_AUTH, EventTag.KONG],
    },
    "kong.probe": {"body": "A user requested the status of a datastore", "tags": [EventTag.USER_AUTH, EventTag.KONG]},
    "meta.initialize": {
        "body": "A user sent a request to start an analysis to the Pod Orchestrator and Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG, EventTag.PO],
    },
    "meta.terminate": {
        "body": "A user sent a request to delete an analysis to the Pod Orchestrator and Kong",
        "tags": [EventTag.USER_AUTH, EventTag.KONG, EventTag.PO],
    },
    "health.status.get": {
        "body": "An API health check was requested from the Hub Adapter API",
        "tags": [EventTag.HUB_ADAPTER],
    },
    "health.status.services.get": {
        "body": "An API health check for downstream services was requested from the Hub Adapter API",
        "tags": [EventTag.KONG, EventTag.PO, EventTag.STORAGE],
    },
    "storage.local.delete": {
        "body": "A user sent a request to delete local results to the Storage Service",
        "tags": [EventTag.USER_AUTH, EventTag.STORAGE],
    },
    "autostart.analysis.create": {
        "body": "The Hub Adapter automatically sent a start request for an analysis to the Pod Orchestrator",
        "tags": [EventTag.AUTOSTART, EventTag.KONG, EventTag.PO],
    },
    "events.get": {
        "body": "A user requested a list of events from the event log",
        "tags": [EventTag.USER_AUTH, EventTag.HUB_ADAPTER],
    },
}

# Add .success and .failure to all
ANNOTATED_EVENTS = {
    "unknown": {"body": "An unknown event has occurred", "tags": []},
    "api.ui.access": {"body": "The API Swagger UI was accessed", "tags": [EventTag.HUB_ADAPTER]},
}
for event_name, event_body in AGNOSTIC_EVENTS.items():
    ANNOTATED_EVENTS.update({f"{event_name}.success": event_body, f"{event_name}.failure": event_body})
