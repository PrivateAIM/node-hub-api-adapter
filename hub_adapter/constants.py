"""Constants."""

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


# Keys are the event name and the value is a human-readable description of the event
AGNOSTIC_EVENTS = {
    "auth.token.get": "A user attempted to sign in to the IDP and acquire a JWT",
    "hub.project.get": "A user requested a list of projects from the Hub",
    "hub.project.node.get": "A user requested a list of node-specific projects from the Hub",
    "hub.project.node.update": "A user attempted to update the approval status of a node in the Hub",
    "hub.analysis.get": "A user requested a list of analyses from the Hub",
    "hub.analysis.update": "A user attempted to update the approval status of an analysis in the Hub",
    "hub.analysis.node.get": "A user requested a list of node-specific analyses from the Hub",
    "hub.analysis.node.update": "A user attempted to update the approval status of an node-specific analysis in the Hub",
    "hub.analysis.image.get": "A request for the URL of an analysis was sent to the Hub",
    "hub.analysis.bucket.get": "A user requested a list of buckets for an analysis from the Hub",
    "hub.analysis.bucket.file.get": "A user requested a list of files for an analysis from the Hub",
    "hub.node.get": "A user requested a list of nodes from the Hub",
    "hub.node.type.get": "A request was sent for the type of node",
    "hub.registry.metadata.get": "A user requested the registry metadata for a project from the Hub",
    "podorc.logs.get": "A user requested the logs for an analysis from the Pod Orchestrator",
    "podorc.history.get": "A user requested the log history for an analysis from the Pod Orchestrator",
    "podorc.status.get": "A user requested a status update for an analysis pod from the Pod Orchestrator",
    "podorc.pods.create": "A user sent a request to start an analysis pod to the Pod Orchestrator",
    "podorc.pods.get": "A user requested a list of analysis pods from the Pod Orchestrator",
    "podorc.pods.stop": "A user sent a request to stop an analysis pod to the Pod Orchestrator",
    "podorc.pods.delete": "A user sent a request to delete an analysis pod to the Pod Orchestrator",
    "podorc.cleanup": "A user sent a cleanup request to the Pod Orchestrator",
    "kong.datastore.get": "A user requested a list of datastores (services) from Kong",
    "kong.datastore.create": "A user sent a request to create a datastore to Kong",
    "kong.datastore.delete": "A user sent a request to delete a datastore to Kong",
    "kong.project.get": "A user requested a list of projects (routes) from Kong",
    "kong.project.create": "A user sent a request to create a project to Kong",
    "kong.project.delete": "A user sent a request to delete a project to Kong",
    "kong.analysis.get": "A user requested a list of analyses (consumers) from Kong",
    "kong.analysis.create": "A user sent a request to create a analysis to Kong",
    "kong.analysis.delete": "A user sent a request to delete a analysis to Kong",
    "kong.initialize": "A user sent a request to create a datastore and link a project to it",
    "kong.probe": "A user requested the status of a datastore",
    "meta.initialize": "A user sent a request to start an analysis to the Pod Orchestrator and Kong",
    "meta.terminate": "A user sent a request to delete an analysis to the Pod Orchestrator and Kong",
    "health.status.get": "An API health check was requested from the Hub Adapter API",
    "health.status.services.get": "An API health check for downstream services was requested from the Hub Adapter API",
    "storage.local.delete": "A user sent a request to delete local results to the Storage Service",
    "autostart.analysis.create": "The Hub Adapter automatically sent a start request for an analysis to the Pod Orchestrator",
    "events.get": "A user requested a list of events from the event log",
}

# Add .success and .failure to all
ANNOTATED_EVENTS = {
    "unknown": "An unknown event has occurred",
    "api.ui.access": "The API Swagger UI was accessed",
}
for event_name, event_body in AGNOSTIC_EVENTS.items():
    ANNOTATED_EVENTS.update({f"{event_name}.success": event_body, f"{event_name}.failure": event_body})
