"""Methods for saving and loading user-defined settings."""

import json
import logging
from contextlib import contextmanager
from typing import Any

import peewee as pw
from playhouse.postgres_ext import BinaryJSONField

from hub_adapter import cache_dir
from hub_adapter.conf import UserSettings
from hub_adapter.database import node_database

SETTINGS_PATH = cache_dir.joinpath("userSettings.json")
SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


class PersistentUserConfiguration(pw.Model):
    """Database table schema for user settings.

    Attributes
    ----------
    configuration : dict
        User-defined settings.

    Notes
    -----
    Peewee creates an id column.
    """

    configuration = BinaryJSONField(default=dict)

    class Meta:
        database = node_database


@contextmanager
def bind_user_settings(db: pw.Database):
    with db.bind_ctx((PersistentUserConfiguration,)):
        # Create tables if they do not exist yet.
        db.create_tables((PersistentUserConfiguration,))
        yield


def load_persistent_settings() -> UserSettings:
    """Get user settings."""
    saved_settings = {}
    if SETTINGS_PATH.exists():  # Write to the file as backup
        saved_settings = json.loads(SETTINGS_PATH.read_text())

    if node_database is not None:  # Write to the database if available
        with bind_user_settings(node_database):
            entry, _ = PersistentUserConfiguration.get_or_create(id=1)
            saved_settings = entry.configuration or {}

    overloaded = {**UserSettings().model_dump(), **saved_settings}  # Overwrite defaults with saved settings
    return UserSettings(**overloaded)


def save_persistent_settings(settings: UserSettings):
    """Save persistent user settings. Overwrites entire file."""
    settings_dict = settings.model_dump()
    if node_database is not None:
        with bind_user_settings(node_database):
            query = PersistentUserConfiguration.update(configuration=settings_dict).where(
                PersistentUserConfiguration.id == 1  # Only one entry exists in the table
            )
            query.execute()
    SETTINGS_PATH.write_text(json.dumps(settings_dict, indent=2))
    logger.info(f"User settings successfully updated: {settings.model_dump_json(exclude_none=True)}")


def _deep_merge(base: dict, updates: dict) -> dict:
    """Recursively merge updates dict into base dict, preserving nested structures. Used to get around the
    frozen UserSettings model."""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def update_settings(new_settings: dict[str, Any]) -> UserSettings:
    """Update user settings with partial or complete settings.

    Parameters
    ----------
    new_settings : dict[str, Any]
        Dictionary containing settings to update. Only provided keys will be updated;
        unprovided keys will retain their current values. Nested dicts are merged recursively.

    Returns
    -------
    UserSettings
        The complete updated settings.
    """
    current_settings = load_persistent_settings().model_dump()
    merged = _deep_merge(current_settings, new_settings)

    updated_settings = UserSettings(**merged)
    save_persistent_settings(updated_settings)
    return updated_settings
