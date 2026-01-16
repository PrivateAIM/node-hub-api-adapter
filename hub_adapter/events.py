"""Event logging utilities for FastAPI middleware and httpx decorators."""

import asyncio
import logging
from collections.abc import Callable
from functools import wraps

import httpx
import jwt
import peewee as pw
from fastapi import Request
from node_event_logging import EventLog, bind_to
from psycopg2 import DatabaseError

from hub_adapter.constants import gateway_service_events
from hub_adapter.utils import annotate_event_name

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

    def log_fastapi_request(self, request: Request, status_code: int | None = None):
        """Log incoming FastAPI requests from external clients using the middleware."""
        user_info = self._extract_user_from_token(request=request)

        event_name = "unknown"
        service = None

        route = request.scope.get("route")
        if route:
            if route.name not in gateway_service_events:
                raise ValueError(f"Unknown event name: {route.name}")
            event_name = annotate_event_name(route.name, status_code)
            service = route.tags[0].lower() if route.tags else None

        self.log_event(
            event_name=event_name,
            service_name="hub_adapter",
            body=str(request.url),
            attributes={
                "method": request.method,
                "path": request.url.path,
                "client": request.client,
                "user": user_info,
                "service": service,
                "status_code": status_code,
            },
        )

    def log_event(
        self,
        event_name: str,
        service_name: str = "hub_adapter",
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

    def httpx_event_decorator(self, event_name: str):
        """Decorator for logging requests and responses.

        Safe to use even if event logging isn't initialized - will simply not log.
        """

        def decorator(func: Callable) -> Callable:
            # If logging not enabled or no event_db, return original function
            if not self.enabled or not self.event_db:
                return func

            def get_user_and_log(result):
                user_info = self._extract_user_from_token(request=result.request)

                # Try to extract httpx response info
                if isinstance(result, httpx.Response):
                    self.log_event(
                        event_name=event_name,
                        service_name="hub_adapter",
                        body=str(result.request.url),
                        attributes={
                            "method": result.request.method,
                            "url": result.status_code,
                            "client": "foo",  # TODO get client details
                            "user": user_info,
                            "service": "anything",  # TODO get service
                            "status_code": result.status_code,
                        },
                    )

                return result

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                return get_user_and_log(result)

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                return get_user_and_log(result)

            # Return appropriate wrapper based on function type since both sync/async are used
            if asyncio.iscoroutinefunction(func):
                return async_wrapper

            return sync_wrapper

        return decorator

    # def create_httpx_client(self, service: str | None = None) -> httpx.Client:
    #     """Create a httpx client with automatic logging via event hooks."""
    #
    #     def log_request(request: httpx.Request):
    #         self.log_request(
    #             method=request.method,
    #             url=str(request.url),
    #             context="httpx_client_request",
    #             service=service,
    #         )
    #
    #     return httpx.Client(
    #         event_hooks={
    #             "request": [log_request],
    #         }
    #     )


event_db: pw.Database | None = None
event_logger: EventLogger | None = None


def setup_event_logging(
    database: str,
    user: str,
    password: str,
    host: str = "localhost",
    port: int = 5432,
    enabled: bool = True,
):
    """Initialize the event logging system.

    Call this once during application startup (in lifespan or startup event).

    Args:
        database: PostgreSQL database name
        user: Database user
        password: Database password
        host: Database host
        port: Database port
        enabled: Whether event logging is enabled
    """
    global event_db, event_logger

    required = {
        "database": database,
        "user": user,
        "password": password,
        "host": host,
        "port": port,
    }
    if not all(required.values()):
        raise ValueError(f"Unable to connect to database due to incomplete configuration settings: {required}")

    event_db = pw.PostgresqlDatabase(**required)

    # Test connection
    with bind_to(event_db):
        event_db.connect(reuse_if_open=True)

    event_logger = EventLogger(event_db, enabled=enabled)

    logger.info(f"Event logging set to: {'enabled' if enabled else 'disabled'}")


def teardown_event_logging():
    """Clean up event logging resources.

    Call this during application shutdown (in lifespan cleanup).
    """
    global event_db, event_logger

    if event_db and not event_db.is_closed():
        event_db.close()
        logger.info("Event logging database closed")

    event_db = None
    event_logger = None


def get_event_logger() -> EventLogger | None:
    """Get the global event logger instance.

    Returns:
        EventLogger instance if initialized, None otherwise
    """
    return event_logger


def log_httpx_event(event: str, func: Callable):
    """Decorator, if event logging isn't initialized, the decorator does nothing."""

    @wraps(func)
    def decorator() -> Callable:
        active_event_logger = get_event_logger()
        if active_event_logger is None or not active_event_logger.enabled:
            return func  # Return original function if logging not initialized
        return active_event_logger.httpx_event_decorator(event_name=event)(func)

    return decorator
