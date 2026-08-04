"""Methods for connecting to an optional Postgres for event logging and saving user settings."""

import logging

import peewee as pw
from playhouse.pool import PooledPostgresqlDatabase

from hub_adapter.dependencies import get_settings, register_closer

logger = logging.getLogger(__name__)


def connect_to_db() -> pw.PostgresqlDatabase | None:
    """Connect to the Postgres database."""
    settings = get_settings()
    required = {
        "database": settings.postgres_db,
        "user": settings.postgres_user,
        "password": settings.postgres_password,
        "host": settings.postgres_host,
        "port": settings.postgres_port,
    }

    if not all(required.values()):
        redacted = {**required, "password": "***"}
        logger.warning(f"Unable to connect to database due to incomplete configuration settings: {redacted}")

        return None

    db = PooledPostgresqlDatabase(
        **required,
        max_connections=settings.postgres_max_connections,
        stale_timeout=settings.postgres_stale_timeout,
    )

    try:
        db.connect(reuse_if_open=True)

    except pw.OperationalError as db_err:
        logger.error(f"Unable to connect to database: {db_err}")
        logger.warning("Postgres event logging and persistent user settings will be disabled.")
        return None

    return db


_node_database: pw.PostgresqlDatabase | None = None
_connection_attempted = False


def get_node_database() -> pw.PostgresqlDatabase | None:
    """Return the one database object for this process, connecting on first use."""
    global _node_database, _connection_attempted

    if not _connection_attempted:
        _connection_attempted = True
        _node_database = connect_to_db()
        register_closer(_close_database)

    return _node_database


def _close_database() -> None:
    """Close every connection peewee opened across all threads AKA burn everything."""
    global _node_database, _connection_attempted

    if _node_database is not None:
        try:
            _node_database.close_all()

        except pw.PeeweeException as db_err:
            logger.warning(f"Error while closing the database connections: {db_err}")

    _node_database = None
    _connection_attempted = False
