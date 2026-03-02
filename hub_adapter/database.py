"""Methods for connecting to an optional Postgres for event logging and saving user settings."""

import logging

import peewee as pw

from hub_adapter.dependencies import get_settings

logger = logging.getLogger(__name__)


def connect_to_db() -> pw.PostgresqlDatabase | None:
    """Connect to the Postgres database."""
    settings = get_settings()
    required = {
        "database": settings.postgres_event_db,
        "user": settings.postgres_event_user,
        "password": settings.postgres_event_password,
        "host": settings.postgres_event_host,
        "port": settings.postgres_event_port,
    }

    if not all(required.values()):
        redacted = {**required, "password": "***"}
        logger.warning(f"Unable to connect to database due to incomplete configuration settings: {redacted}")

        return None

    db = pw.PostgresqlDatabase(**required)

    try:
        db.connect(reuse_if_open=True)

    except pw.OperationalError as db_err:
        logger.error(f"Unable to connect to database: {db_err}")
        logger.warning("Postgres event logging and persistent user settings will be disabled.")
        return None

    return db


_node_database: pw.PostgresqlDatabase | None = None


def get_node_database() -> pw.PostgresqlDatabase | None:
    global _node_database
    if _node_database is None or _node_database.is_closed():
        _node_database = connect_to_db()
    return _node_database
