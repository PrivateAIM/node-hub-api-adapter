"""Constants."""

from enum import StrEnum

CONTENT_TYPE = "Content-Type"
CONTENT_LENGTH = "Content-Length"

SERVICE_NAME = "hub_adapter"  # Name of this service
SERVICE = "service"

EVENT = "event"

# Hub Keywords
ID = "id"
HOST = "host"
NODE = "node"
NODE_ID = "NODE_ID"


class ServiceTag(StrEnum):
    """Service tags"""

    AUTH = "Auth"
    AUTOSTART = "Autostart"
    KONG_CLEANUP = "Kong Cleanup"
    LOGS = "Logs"
    HEALTH = "Health"
    HUB = "Hub"
    HUB_ADAPTER = "Hub Adapter"
    KONG = "Kong"
    META = "Meta"
    NODE = "Node"
    PODORC = "PodOrc"
    STORAGE = "Storage"
    IDP = "IDP"
    UNKNOWN = "Unknown"
