"""string constants."""

CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"

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

# Map Hub responses to what the old FLAME UI expects
analysis_container_status_map = {
    "running": "running",
    "starting": "running",
    "started": "created",
    "stopping": "running",
    "stopped": "exited",
    "finished": "exited",
    "failed": "exited",
}
