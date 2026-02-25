"""Methods for saving and loading user-defined settings."""

import json
import logging
from contextlib import contextmanager

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
    if node_database is not None:
        with bind_user_settings(node_database):
            entry, _ = PersistentUserConfiguration.get_or_create(id=1)
            saved_settings = entry.configuration or {}

    elif SETTINGS_PATH.exists():
        saved_settings = json.loads(SETTINGS_PATH.read_text())

    overloaded = {**UserSettings().model_dump(), **saved_settings}  # Overwrite defaults with saved settings
    return UserSettings(**overloaded)


def save_persistent_settings(settings: UserSettings):
    """Save persistent user settings. Overwrites entire file."""
    if node_database is not None:
        with bind_user_settings(node_database):
            PersistentUserConfiguration.update(**settings.model_dump()).execute(id=1)
    SETTINGS_PATH.write_text(json.dumps(settings.model_dump(), indent=2))
    logger.info(f"User settings successfully updated: {settings.model_dump_json(exclude_none=True)}")


def update_settings(new_settings: UserSettings) -> UserSettings:
    """Update user settings."""
    current_settings = load_persistent_settings()
    updated_settings = current_settings.model_copy(update=new_settings.model_dump(exclude_none=True))
    save_persistent_settings(updated_settings)
    return updated_settings


if __name__ == "__main__":
    foo = UserSettings.model_construct(**{"autostart": {"enabled": False, "interval": 10}})
    update_settings(foo)
