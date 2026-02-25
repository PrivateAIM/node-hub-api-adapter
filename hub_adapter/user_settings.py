"""Methods for saving and loading user-defined settings."""

import json
import logging
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any, TypeVar

import peewee as pw
from playhouse.postgres_ext import BinaryJSONField

from hub_adapter import cache_dir
from hub_adapter.conf import UserSettings
from hub_adapter.database import node_database

SETTINGS_PATH = cache_dir.joinpath("userSettings.json")
SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_db_fallback(fallback_value: Any = None, log_message: str = "Database operation failed"):
    """Decorator for database operations with automatic fallback on error.

    Parameters
    ----------
    fallback_value : Any, optional
        Value to return if the database operation fails. Default is None.
    log_message : str, optional
        Custom log message prefix for warnings.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)

            except pw.OperationalError as db_err:
                logger.warning(f"{log_message}: {db_err}")
                return fallback_value

        return wrapper

    return decorator


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


@with_db_fallback(fallback_value={}, log_message="Database unavailable, falling back to cached settings")
def _load_from_database() -> dict:
    """Load settings from the database."""
    if node_database is None:
        return {}

    with bind_user_settings(node_database):
        entry, _ = PersistentUserConfiguration.get_or_create(id=1)
        return entry.configuration or {}


def _load_from_json() -> dict:
    """Load settings from JSON file."""
    if not SETTINGS_PATH.exists():
        return {}

    try:
        saved_settings = json.loads(SETTINGS_PATH.read_text())
        logger.info("Loaded settings from JSON file backup")
        return saved_settings

    except Exception as file_err:
        logger.error(f"Failed to load from JSON file: {file_err}")
        return {}


@with_db_fallback(fallback_value=False, log_message="Failed to save to database")
def _save_to_database(settings_dict: dict) -> bool:
    """Save settings to the database.

    Returns
    -------
    bool
        Whether the settings successfully saved to the database.
    """
    if node_database is None:
        return False

    with bind_user_settings(node_database):
        query = PersistentUserConfiguration.update(configuration=settings_dict).where(
            PersistentUserConfiguration.id == 1
        )
        query.execute()
    logger.info(f"User settings saved to database: {settings_dict}")
    return True


def _save_to_json(settings_dict: dict, db_saved: bool):
    """Save settings to cached JSON file."""
    try:
        SETTINGS_PATH.write_text(json.dumps(settings_dict, indent=2))
        if not db_saved:
            logger.info(f"User settings saved to JSON file (database unavailable): {settings_dict}")

    except Exception as file_err:
        logger.error(f"Failed to save settings to JSON file: {file_err}")
        raise


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


def load_persistent_settings() -> UserSettings:
    """Get user settings from the database with fallback to JSON file.

    Attempts to load from the database first, but falls back to the JSON file
    if the database is unavailable or connection is interrupted.
    """
    saved_settings = _load_from_database()

    # Fall back to the cached JSON file if the database failed or is unavailable
    if not saved_settings:
        saved_settings = _load_from_json()

    overloaded = {**UserSettings().model_dump(), **saved_settings}
    return UserSettings(**overloaded)


def save_persistent_settings(settings: UserSettings):
    """Save per_save_to_database(settings_dict)"""
    settings_dict = settings.model_dump(exclude_none=True)
    db_saved = _save_to_database(settings_dict)
    _save_to_json(settings_dict, db_saved)


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
