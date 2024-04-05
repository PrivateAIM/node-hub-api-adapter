"""string constants."""

CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"

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
