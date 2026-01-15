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
            logger.error(db_err)
            logger.warning("Failed to log event; continuing without event logging")

    def log_incoming_request(self, request: Request, response):
        """Log incoming FastAPI requests from external clients."""
        user_info = self._extract_user_from_token(request=request)

        event_name = "ui_request"
        function_name = None
        service = None

        route = request.scope.get("route")
        if route:
            function_name = route.name
            service = route.tags[0].lower() if route.tags else None
            event_name = f"{service}_request"

        self.log_event(
            event_name=event_name,
            service_name="hub_adapter",
            body=str(request.url),
            attributes={
                "method": request.method,
                "path": request.url.path,
                "client": request.client,
                "user": user_info,
                "function_name": function_name,
                "service": service,
                "status_code": response.status_code if hasattr(response, "status_code") else None,
            },
        )

    def log_httpx_request(
        self,
        method: str,
        url: str,
        status_code: int | None = None,
        context: str | None = None,
        service: str | None = None,
    ):
        """Log outgoing httpx requests made to internal services."""
        event_name = f"httpx_{method.lower()}"
        if service:
            event_name = f"{service}_httpx_{method.lower()}"

        self.log_event(
            event_name=event_name,
            service_name="hub_adapter",
            body=url,
            attributes={
                "http_method": method,
                "url": url,
                "status_code": status_code,
                "context": context,
                "service": service,
            },
        )

    def httpx_logging_decorator(self, service: str | None = None):
        """Decorator for logging internal httpx requests.

        Safe to use even if event logging isn't initialized - will simply not log.
        """

        def decorator(func: Callable) -> Callable:
            # If logging not enabled or no event_db, return original function
            if not self.enabled or not self.event_db:
                return func

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                result = func(*args, **kwargs)

                # Try to extract httpx response info
                if isinstance(result, httpx.Response):
                    self.log_httpx_request(
                        method=result.request.method,
                        url=str(result.request.url),
                        status_code=result.status_code,
                        context=func.__name__,
                        service=service,
                    )

                return result

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)

                # Try to extract httpx response info
                if isinstance(result, httpx.Response):
                    self.log_httpx_request(
                        method=result.request.method,
                        url=str(result.request.url),
                        status_code=result.status_code,
                        context=func.__name__,
                        service=service,
                    )

                return result

            # Return appropriate wrapper based on function type since both sync/async are used
            if asyncio.iscoroutinefunction(func):
                return async_wrapper

            return sync_wrapper

        return decorator

    def create_httpx_client(self, service: str | None = None) -> httpx.Client:
        """Create a httpx client with automatic logging via event hooks."""

        def log_request(request: httpx.Request):
            self.log_httpx_request(
                method=request.method,
                url=str(request.url),
                context="httpx_client_request",
                service=service,
            )

        return httpx.Client(
            event_hooks={
                "request": [log_request],
            }
        )


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


def log_httpx_request(service: str | None = None):
    """Decorator, if event logging isn't initialized, the decorator does nothing."""

    def decorator(func: Callable) -> Callable:
        httpx_logger = get_event_logger()
        if httpx_logger is None:
            return func  # Return original function if logging not initialized
        return httpx_logger.httpx_logging_decorator(service=service)(func)

    return decorator
