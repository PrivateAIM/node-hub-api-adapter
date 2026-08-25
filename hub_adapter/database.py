"""Methods for connecting to an optional Postgres for event logging and saving user settings."""

import logging
import threading
import time

import peewee as pw
from playhouse.pool import PooledPostgresqlDatabase

from hub_adapter.dependencies import get_settings, register_closer

logger = logging.getLogger(__name__)

# how long to wait before trying a configured but unreachable Postgres again
RECONNECT_COOLDOWN = 30.0


def connect_to_db() -> pw.PostgresqlDatabase | None:
    """Connect to the Postgres database, or None when it is not fully configured.

    Raises pw.OperationalError when Postgres is configured but cannot be reached.
    """
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
        timeout=settings.postgres_pool_timeout,
    )
    db.connect(reuse_if_open=True)
    db.close()

    return db


_node_database: pw.PostgresqlDatabase | None = None
_unconfigured = False
_retry_after: float | None = None
_lock = threading.Lock()


def get_node_database() -> pw.PostgresqlDatabase | None:
    """Return the one database object for this process, connecting on first use.

    An unreachable Postgres may only be down briefly, so retry a failed connection.
    Incomplete settings will not change while the process runs, so that is reported once and never retried.
    """
    global _node_database, _unconfigured, _retry_after

    with _lock:
        if _node_database is not None or _unconfigured:
            return _node_database

        if _retry_after is not None and time.monotonic() < _retry_after:
            return None

        try:
            db = connect_to_db()

        except pw.OperationalError as db_err:
            logger.error(f"Unable to connect to database: {db_err}")
            logger.warning(
                f"Postgres event logging and persistent user settings are disabled, retrying in {RECONNECT_COOLDOWN:.0f}s."
            )
            _retry_after = time.monotonic() + RECONNECT_COOLDOWN
            return None

        if db is None:  # misconfigured, nothing to retry
            _unconfigured = True
            return None

        _node_database = db
        register_closer(_close_database)

        return _node_database


def _close_database() -> None:
    """Close every connection peewee opened across all threads AKA burn everything."""
    global _node_database, _unconfigured, _retry_after

    with _lock:
        if _node_database is not None:
            try:
                _node_database.close_all()

            except pw.PeeweeException as db_err:
                logger.warning(f"Error while closing the database connections: {db_err}")

        _node_database = None
        _unconfigured = False
        _retry_after = None
