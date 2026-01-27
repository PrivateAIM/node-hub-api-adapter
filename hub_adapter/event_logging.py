"""Event logging utilities for FastAPI middleware and httpx decorators."""

import logging

import jwt
import peewee as pw
from fastapi import Request
from node_event_logging import EventLog, bind_to
from psycopg2 import DatabaseError

from hub_adapter.constants import SERVICE_NAME, ANNOTATED_EVENTS
from hub_adapter.dependencies import get_settings
from hub_adapter.utils import annotate_event

logger = logging.getLogger(__name__)


class EventLogger:
    """Event logging utility."""

    def __init__(self, event_database: pw.Database, enabled: bool = True):
        self.event_db = event_database
        self.enabled = enabled

    @staticmethod
    def _extract_user_from_token(request: Request) -> dict | None:
        """Extract user information from JWT token in request headers."""
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.replace("Bearer ", "")

        try:
            decoded = jwt.decode(token, options={"verify_signature": False})

            user_info = {
                "user_id": decoded.get("sub"),
                "username": decoded.get("preferred_username") or decoded.get("username"),
                "email": decoded.get("email"),
                "client_id": decoded.get("azp") or decoded.get("client_id"),
            }

            return {k: v for k, v in user_info.items() if v is not None}

        except (jwt.DecodeError, jwt.InvalidTokenError):
            return None

    def log_fastapi_request(self, request: Request, status_code: int | None = None, log_health_checks: bool = False):
        """Log incoming FastAPI requests from external clients using the middleware."""
        user_info = self._extract_user_from_token(request=request)

        event_name = "unknown"
        service = None
        event_tags = []

        route = request.scope.get("route")
        path = request.scope.get("path")

        if path.split("/")[-1] in ("docs", "redoc", "openapi.json"):
            event_name = "api.ui.access"
            service = "hub_adapter"

        elif route:
            # Health checks will flood the database
            if not log_health_checks and route.name == "health.status.get":
                return

            event_name, tags = annotate_event(route.name, status_code)
            if event_name not in ANNOTATED_EVENTS:
                raise ValueError(f"Unknown event name: {event_name}")
            service = route.tags[0].lower() if route.tags else None

        event_data = ANNOTATED_EVENTS.get(event_name)
        body = event_data.get("body")
        event_tags = event_data.get("tags") + event_tags if event_data.get("tags") else event_tags

        self.log_event(
            event_name=event_name,
            service_name=SERVICE_NAME,
            body=body or str(request.url),
            attributes={
                "method": request.method,
                "path": path,
                "client": request.client,
                "url": str(request.url),
                "user": user_info,
                "service": service,
                "status_code": status_code,
                "tags": event_tags,
            },
        )

    def log_event(
        self,
        event_name: str,
        service_name: str = SERVICE_NAME,
        body: str | None = None,
        attributes: dict | None = None,
    ):
        """Core logging method used by middleware and decorator components."""
        if not self.enabled or not self.event_db:
            return

        try:
            with bind_to(self.event_db):
                EventLog.create(
                    event_name=event_name,
                    service_name=service_name,
                    body=body,
                    attributes=attributes or {},
                )

        except (pw.PeeweeException, ValueError, DatabaseError) as db_err:
            logger.warning(str(db_err).strip())  # Strip needed to remove newline from peewee error
            logger.warning("Failed to log event; continuing without event logging")


event_logger: EventLogger | None = None


def setup_event_logging():
    """Initialize the event logging system."""
    global event_logger

    settings = get_settings()
    logging_enabled = settings.LOG_EVENTS

    logger.debug(f"Event logging set to: {'enabled' if logging_enabled else 'disabled'}")

    if logging_enabled:
        logger.info(f"Event logging enabled, connecting to database at {settings.POSTGRES_EVENT_HOST}")
        required = {
            "database": settings.POSTGRES_EVENT_DB,
            "user": settings.POSTGRES_EVENT_USER,
            "password": settings.POSTGRES_EVENT_PASSWORD,
            "host": settings.POSTGRES_EVENT_HOST,
            "port": settings.POSTGRES_EVENT_PORT,
        }

        if not all(required.values()):
            raise ValueError(f"Unable to connect to database due to incomplete configuration settings: {required}")

        event_db = pw.PostgresqlDatabase(**required)

        # Test connection
        with bind_to(event_db):
            event_db.connect(reuse_if_open=True)

        event_logger = EventLogger(event_db, enabled=logging_enabled)


def teardown_event_logging():
    """Clean up event logging resources.

    Call this during application shutdown (in lifespan cleanup).
    """
    global event_logger

    if event_logger and event_logger.event_db and not event_logger.event_db.is_closed():
        event_logger.event_db.close()
        logger.info("Event logging database closed")

    event_logger.event_db = None
    event_logger = None


def get_event_logger() -> EventLogger | None:
    """Get the global event logger instance. Attempts to reinitialize the event logging system if None.

    Returns:
        EventLogger instance if initialized, None otherwise
    """
    if not event_logger or not event_logger.event_db:
        try:
            setup_event_logging()

        except (pw.PeeweeException, ValueError) as db_err:
            logger.warning(str(db_err).strip())
            logger.warning("Event logging disabled due to database configuration or connection error")

    return event_logger
