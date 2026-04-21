import datetime

from pydantic import BaseModel

from hub_adapter.constants import ServiceTag


class EventLog(BaseModel):
    """Event log response model."""

    image: str
    component: str
    event_name: str
    service: ServiceTag
    level: str
    timestamp: datetime.datetime
    message: str
    user: str | None = None


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


# Events
## Keys are the event name and the value is a human-readable description of the event
TRACKED_EVENTS = {
    "auth.token.get": "A user attempted to sign in to the IDP and acquire a JWT",
    "auth.user.signin": "A user signed in to the Node UI",
    "auth.user.signout": "A user manually signed out of the Node UI",
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
    "podorc.status.get": "A user requested a status update for an analysis pod from the Pod Orchestrator",
    "podorc.pods.create": "A user sent a request to start an analysis pod to the Pod Orchestrator",
    "podorc.pods.get": "A user requested a list of analysis pods from the Pod Orchestrator",
    "podorc.pods.stop": "A user sent a request to stop an analysis pod to the Pod Orchestrator",
    "podorc.pods.delete": "A user sent a request to delete an analysis pod to the Pod Orchestrator",
    "podorc.cleanup": "A user sent a cleanup request to the Pod Orchestrator",
    "kong.datastore.get": "A user requested a list of datastores (services) from Kong",
    "kong.datastore.create": "A user sent a request to create a datastore to Kong",
    "kong.datastore.delete": "A user sent a request to delete a datastore to Kong",
    "kong.datastore.delete_orphaned": "A user sent a request to delete orphaned datastores to Kong",
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
    "node.settings.get": "A user fetched the node's configurations settings",
    "node.settings.update": "A user updated the node's configurations settings",
    "health.status.get": "An API health check was requested from the Hub Adapter API",
    "health.status.services.get": "An API health check for downstream services was requested from the Hub Adapter API",
    "storage.local.delete": "A user sent a request to delete local results to the Storage Service",
    "logs.events.get": "A user requested a list of events from the event log",
    "autostart.analysis.create": "The Hub Adapter automatically sent a request to start an analysis to the Pod Orchestrator",
    "api.ui.access": "The API Swagger UI was accessed",
    "unknown": "An unknown event has occurred",
    # Error events — hub
    "hub.proxy.error": "A proxy error prevented contacting the Hub",
    "hub.read.timeout": "The Hub timed out during a read operation",
    "hub.connect.error": "The CoreClient could not establish a connection to the Hub",
    "hub.validation.error": "A Pydantic validation error occurred on a Hub response",
    "hub.connection.timeout": "The Hub connection timed out",
    "hub.connection.error": "The Hub is currently unreachable",
    "hub.auth.error": "The Hub Adapter failed to retrieve a JWT from the Hub",
    # Error events — kong
    "kong.consumer.conflict": "A Kong consumer conflict was detected",
    "kong.service.not_found": "A Kong service was not found",
    "kong.api.error": "A Kong API error occurred",
    "kong.service.unavailable": "The Kong service is unavailable after max retries",
    "kong.http.error": "A Kong-related HTTP error was raised",
    "kong.service.error": "An unexpected Kong service error occurred",
    "kong.gateway.error": "The Kong gateway was unable to contact a service",
    "kong.service.resolution_failed": "Kong failed to resolve a service name",
    "kong.consumer.api_key.not_found": "An API key for the health consumer could not be obtained",
    # Error events — storage / fhir
    "storage.bucket.forbidden": "The requested bucket does not exist or is set to private",
    "fhir.endpoint.not_found": "The requested FHIR endpoint was not found",
    # Dependency events
    "hub.http.response": "An HTTP response was received from the Hub",
    # Autostart events
    "autostart.poll": "Autostart checked for new analyses to start",
    "autostart.error": "Autostart encountered an error during its main loop",
    "autostart.started": "Autostart manager started",
    "autostart.stopped": "Autostart manager stopped",
    "autostart.restarted": "Autostart manager restarted with a new interval",
    "autostart.hub.connect_error": "Autostart was unable to connect to the Hub",
    "autostart.analysis.hub_fetch_error": "Autostart failed to fetch analyses due to a Hub connection error",
    "autostart.analysis.register": "Autostart attempted to register an analysis with Kong",
    "autostart.analysis.register_error": "Autostart failed to register an analysis with Kong",
    "autostart.analysis.conflict": "Autostart found an analysis already registered in Kong",
    "autostart.analysis.status_unknown": "Autostart could not obtain pod status for an analysis",
    "autostart.analysis.orphan_cleanup": "Autostart found no running pod and is cleaning up the orphaned Kong consumer",
    "autostart.analysis.max_retries": "Autostart failed to start an analysis after max attempts",
    "autostart.analysis.already_running": "Autostart found a pod already running for an analysis",
    "autostart.token.error": "Autostart was unable to fetch the OIDC token",
    "autostart.analysis.starting": "Autostart is sending a start request for an analysis pod",
    "autostart.analysis.start_response": "Autostart received a response to an analysis start request",
    "autostart.analysis.start_error": "Autostart failed to start an analysis",
    "autostart.podorc.unreachable": "Autostart could not contact the Pod Orchestrator",
    "autostart.analysis.timeout": "Autostart timed out waiting for an analysis pod to start",
    "autostart.analysis.no_token": "Autostart could not start analysis due to missing token",
    "autostart.analysis.status_error": "Autostart failed to fetch the status of an analysis pod",
    "autostart.kong.route_error": "Autostart failed to retrieve Kong routes",
    "autostart.analysis.invalid_project": "Autostart skipped analysis due to an invalid or unapproved project",
    "autostart.analysis.ready": "Autostart found analyses ready to start",
}
