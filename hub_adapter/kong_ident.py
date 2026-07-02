"""Identity helpers for Kong resources.

Relationships between FLAME entities (projects, data stores, analyses) and Kong
entities (routes, services, consumers) are carried exclusively by Kong tags —
never encoded in entity names. Names are cosmetic; canonical identifiers are
Kong IDs. This avoids Kong's UUID-name ambiguity (path parameters that parse as
UUIDs are treated as IDs, so entities *named* a bare UUID cannot be fetched by
name).
"""

import re
import uuid

HEALTH_TAG = "health"

# Kong reserves ',' and '/' in tags; names additionally stick to a URL-safe set
_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._~-]+$")


def is_uuid(value: str) -> bool:
    """Return True if the value parses as a UUID."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def validate_datastore_name(name: str) -> str:
    """Validate an admin-chosen data store display name, returning it unchanged."""
    if not name or not _NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid data store name {name!r}: only letters, digits, '.', '_', '~', and '-' are allowed"
        )

    if is_uuid(name):
        raise ValueError(f"Invalid data store name {name!r}: bare UUIDs cannot be used as names")

    return name


def project_tag(project_id: str | uuid.UUID) -> str:
    return f"project:{project_id}"


def datastore_tag(service_id: str | uuid.UUID) -> str:
    return f"datastore:{service_id}"


def type_tag(ds_type) -> str:
    ds = ds_type.value if hasattr(ds_type, "value") else ds_type
    return f"type:{ds}"


def analysis_tag(analysis_id: str | uuid.UUID) -> str:
    return f"analysis:{analysis_id}"


def analysis_username(analysis_id: str | uuid.UUID) -> str:
    return f"analysis-{analysis_id}"


def health_username(project_id: str | uuid.UUID) -> str:
    return f"health-{project_id}"


def link_path(project_id: str | uuid.UUID, service_id: str | uuid.UUID) -> str:
    return f"/{project_id}/{service_id}"


def parse_tags(tags: list[str] | None) -> dict[str, str]:
    """Parse ['project:abc', 'health'] into {'project': 'abc'}; valueless tags are skipped."""
    parsed = {}
    for tag in tags or []:
        key, sep, value = tag.partition(":")
        if sep:
            parsed[key] = value

    return parsed
