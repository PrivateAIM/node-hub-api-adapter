"""Methods for verifying auth."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import peewee as pw
import uvicorn
from fastapi import FastAPI
from node_event_logging import EventLog, EventModelMap, bind_to
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from hub_adapter.autostart import GoGoAnalysis
from hub_adapter.dependencies import get_settings
from hub_adapter.models.events import RequestEventLog
from hub_adapter.routers.auth import auth_router
from hub_adapter.routers.health import health_router
from hub_adapter.routers.hub import hub_router
from hub_adapter.routers.kong import kong_router
from hub_adapter.routers.meta import meta_router
from hub_adapter.routers.podorc import po_router
from hub_adapter.routers.results import results_router
from hub_adapter.utils import _extract_user_from_token

logger = logging.getLogger(__name__)

event_db = None
event_logging_enabled = False

# API metadata
tags_metadata = [
    {"name": "Auth", "description": "Endpoints for authorization specific tasks."},
    {"name": "Meta", "description": "Custom Hub Adapter endpoints which combine endpoints from other APIs."},
    {
        "name": "Health",
        "description": "Endpoints for checking the health of this API and the downstream services.",
    },
    {"name": "Hub", "description": "Gateway endpoints for the central Hub service."},
    {"name": "Kong", "description": "Endpoints for the Kong gateway service."},
    {"name": "PodOrc", "description": "Gateway endpoints for the Pod Orchestration service."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global event_db, event_logging_enabled

    settings = get_settings()

    EventModelMap.mapping = {
        "ui_request": RequestEventLog,
        "kong_request": RequestEventLog,
        "hub_request": RequestEventLog,
        "podorc_request": RequestEventLog,
        "results_request": RequestEventLog,
        "meta_request": RequestEventLog,
        "auth_request": RequestEventLog,
        "health_request": RequestEventLog,
    }

    try:
        # Validate required settings explicitly
        required = {
            "database": settings.POSTGRES_EVENT_DB,
            "user": settings.POSTGRES_EVENT_USER,
            "password": settings.POSTGRES_EVENT_PASSWORD,
            "hostname": settings.POSTGRES_EVENT_HOST,
            "port": settings.POSTGRES_EVENT_PORT,
        }
        if not all(required.values()):
            raise ValueError(f"Postgres database settings are incomplete: {required}")

        event_db = pw.PostgresqlDatabase(
            database=settings.POSTGRES_EVENT_DB,
            user=settings.POSTGRES_EVENT_USER,
            password=settings.POSTGRES_EVENT_PASSWORD,
            host=settings.POSTGRES_EVENT_HOST,
            port=settings.POSTGRES_EVENT_PORT,
        )

        # Force an actual connection test at startup
        event_db.connect(reuse_if_open=True)
        event_logging_enabled = True
        logger.info("Event logging enabled")

    except (pw.PeeweeException, ValueError) as db_err:
        event_db = None
        event_logging_enabled = False
        logger.warning(db_err)
        logger.warning("Event logging disabled due to database configuration or connection error")

    yield

    # Safely close the connection
    if event_db and not event_db.is_closed():
        event_db.close()


app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME API",
    description="FLAME project API for interacting with various microservices within the node for the UI.",
    swagger_ui_init_oauth={
        "clientId": get_settings().API_CLIENT_ID,  # default client-id is Keycloak
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        "identifier": "Apache-2.0",
    },
    root_path=get_settings().API_ROOT_PATH,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def event_logging_middleware(request: Request, call_next):
    """Middleware to log the events."""
    response = await call_next(request)

    if not event_logging_enabled:
        return response

    try:
        with bind_to(event_db):
            user_info = _extract_user_from_token(request=request)

            event_name = "ui_request"
            function_name = None
            service = None

            route = request.scope.get("route")
            if route:
                function_name = route.name
                service = route.tags[0].lower() if route.tags else None
                event_name = f"{service}_request"

            EventLog.create(
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
                },
            )

    except (pw.PeeweeException, ValueError) as db_err:
        logger.error(db_err)
        logger.exception("Failed to log event; continuing without event logging")

    return response


routers = (
    po_router,
    meta_router,
    hub_router,
    results_router,
    kong_router,
    health_router,
    auth_router,
)

for router in routers:
    app.include_router(router)


async def run_server(host: str, port: int, reload: bool):
    """Start the hub adapter API server."""
    config = uvicorn.Config(app, host=host, port=port, reload=reload)
    server = uvicorn.Server(config)
    await server.serve()


async def autostart_probing(interval: int = 60):
    """Check for available analyses in the background and start them automatically.

    Parameters
    ----------
    interval : int
        Time in seconds to wait between checks.
    """
    analysis_initiator = GoGoAnalysis()
    while True:
        await analysis_initiator.auto_start_analyses()
        await asyncio.sleep(interval)


async def deploy(host: str = "127.0.0.1", port: int = 8081, reload: bool = False):
    # Run both tasks concurrently
    tasks = [asyncio.create_task(run_server(host, port, reload))]

    autostart: bool = os.getenv("AUTOSTART", "False").lower() in ("true", "1", "yes")
    logger.info(f"Autostart enabled: {autostart}")
    autostart_interval: int = int(os.getenv("AUTOSTART_INTERVAL", "60"))

    if autostart:
        autostart_operation = asyncio.create_task(autostart_probing(interval=autostart_interval))
        tasks.append(autostart_operation)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(deploy())
