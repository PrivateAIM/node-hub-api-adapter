"""Constants."""

from hub_adapter.models.events import GatewayEventLog

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

# Event model mappings
event_mapping = {}

event_names = (
    "auth.token.get",
    "hub.project.get",
    "hub.project.node.get",
    "hub.project.node.update",
    "hub.analysis.get",
    "hub.analysis.update",
    "hub.analysis.node.get",
    "hub.analysis.node.update",
    "hub.analysis.image.get",
    "hub.analysis.bucket.get",
    "hub.analysis.bucket.file.get",
    "hub.node.get",
    "hub.node.type.get",
    "hub.registry.metadata.get",
    "podorc.logs.get",
    "podorc.history.get",
    "podorc.status.get",
    "podorc.pods.create",
    "podorc.pods.get",
    "podorc.pods.stop",
    "podorc.pods.delete",
    "podorc.cleanup",
    "kong.datastore.get",
    "kong.datastore.create",
    "kong.datastore.delete",
    "kong.project.get",
    "kong.project.create",
    "kong.project.delete",
    "kong.analysis.get",
    "kong.analysis.create",
    "kong.analysis.delete",
    "kong.initialize",
    "kong.probe",
    "meta.initialize",
    "meta.terminate",
    "health.status.get",
    "health.status.services.get",
    "storage.local.delete",
    "autostart.analysis.create",
)
for event_name in event_names:
    event_mapping.update({f"{event_name}.success": GatewayEventLog, f"{event_name}.failure": GatewayEventLog})
