"""Middleware to inject into FastAPI"""

import logging

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from hub_adapter import current_user_id
from hub_adapter.schemas.logs import TRACKED_EVENTS

logger = logging.getLogger(__name__)


def _set_user_context(request: Request) -> None:
    """Extract user ID from the Bearer token and store it in the request-scoped context var."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ")

        try:
            claims = jwt.decode(token, options={"verify_signature": False})
            user_id = claims.get("preferred_username") or claims.get("sub")
            current_user_id.set(user_id)

        except Exception:
            pass


def log_event(
    event_name: str,
    event_description: str | None = None,
    level: int = logging.INFO,
    status_code: int | None = None,
    user: str | None = None,
    service: str | None = None,
    exc: BaseException | None = None,
) -> None:
    """Emit a structured event log from any context.

    Parameters
    ----------
    event_name : str
        Key from TRACKED_EVENTS (e.g. "autostart.analysis.create").
    event_description : str | None
        If provided, is used in the emitted log instead of the value in TRACKED_EVENTS (if present).
    level : str
        Log level — "info", "warning", "error", or "critical".
    status_code : int
        HTTP-style status code used to append ".success" or ".failure" suffix.
    user : str | None
        User identifier. Falls back to the current request context var if not provided.
    service : str | None
        Service label to include in the log.
    exc : BaseException | None
        If provided, the exception and its traceback are included in the log.
    """

    logger.log(
        level,
        event_description or TRACKED_EVENTS.get(event_name, event_name),
        exc_info=exc,
        extra={
            "event_name": event_name,
            "service": service,
            "user": user or current_user_id.get(),
            "status_code": status_code,
        },
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Set user context and emit a structured event log for every tracked route."""

    def __init__(self, app, log_health_checks: bool = False):
        super().__init__(app)
        self.log_health_checks = log_health_checks

    async def dispatch(self, request: Request, call_next) -> Response:
        _set_user_context(request)
        response = await call_next(request)

        if request.method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            return response

        user = current_user_id.get()
        path = request.scope.get("path", "")
        if path.split("/")[-1] in ("docs", "redoc", "openapi.json"):
            logger.info(
                "api.ui.access",
                extra={
                    "event_name": "api.ui.access",
                    "event_description": TRACKED_EVENTS.get("api.ui.access"),
                    "service": "hub_adapter",
                    "user": user,
                },
            )
            return response

        route = request.scope.get("route")
        if not route:
            return response

        event_name = route.name
        if not self.log_health_checks and event_name == "health.status.get":
            return response

        if event_name == "podorc.status.get":
            return response

        if event_name not in TRACKED_EVENTS:
            return response

        service = route.tags[0] if route.tags else None
        log_level = logging.INFO if response.status_code < 400 else logging.ERROR

        log_event(event_name, level=log_level, user=user, service=service, status_code=response.status_code)

        return response
