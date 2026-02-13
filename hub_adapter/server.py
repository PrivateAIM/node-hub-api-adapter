"""Methods for verifying auth."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from node_event_logging import EventModelMap
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from hub_adapter import logging_config
from hub_adapter.autostart import GoGoAnalysis
from hub_adapter.dependencies import get_settings
from hub_adapter.event_logging import get_event_logger, teardown_event_logging
from hub_adapter.models.events import ANNOTATED_EVENTS
from hub_adapter.routers.auth import auth_router
from hub_adapter.routers.events import event_router
from hub_adapter.routers.health import health_router
from hub_adapter.routers.hub import hub_router
from hub_adapter.routers.kong import kong_router
from hub_adapter.routers.meta import meta_router
from hub_adapter.routers.podorc import po_router
from hub_adapter.routers.storage import storage_router

logger = logging.getLogger(__name__)


# API metadata
tags_metadata = [
    {"name": "Auth", "description": "Endpoints for authorization specific tasks."},
    {"name": "Events", "description": "Gateway endpoints for interacting with logged events."},
    {"name": "Meta", "description": "Custom Hub Adapter endpoints which combine endpoints from other APIs."},
    {
        "name": "Health",
        "description": "Endpoints for checking the health of this API and the downstream services.",
    },
    {"name": "Hub", "description": "Gateway endpoints for the central Hub service."},
    {"name": "Kong", "description": "Endpoints for the Kong gateway service."},
    {"name": "Storage", "description": "Gateway endpoints for the Storage service."},
    {"name": "PodOrc", "description": "Gateway endpoints for the Pod Orchestration service."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    EventModelMap.mapping = {event_name: event_data.get("model") for event_name, event_data in ANNOTATED_EVENTS.items()}

    get_event_logger()  # Attempts to setup connections

    yield

    teardown_event_logging()


app = FastAPI(
    openapi_tags=tags_metadata,
    title="FLAME Hub Adapter API",
    description="FLAME Hub Adapter gateway API for interacting with downstream services.",
    contact={
        "name": "Bruce Schultz",
        "email": "bschultz013@gmail.com",
        "url": "https://docs.privateaim.net/about/team.html",
    },
    swagger_ui_init_oauth={
        "clientId": get_settings().API_CLIENT_ID,  # default client-id is Keycloak
    },
    servers=[
        {"url": "http://localhost:5000", "description": "api"},
    ],
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
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

    try:
        middleware_logger = get_event_logger()
        middleware_logger.log_fastapi_request(request, response.status_code, log_health_checks=False)

    except AttributeError:
        # Event logging not initialized, skip
        pass

    return response


routers = (
    po_router,
    meta_router,
    hub_router,
    storage_router,
    kong_router,
    health_router,
    auth_router,
    event_router,
)

for router in routers:
    app.include_router(router)


async def run_server(host: str, port: int, reload: bool):
    """Start the hub adapter API server."""
    config = uvicorn.Config(app, host=host, port=port, reload=reload, log_config=logging_config)
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


async def deploy(host: str = "127.0.0.1", port: int = 5000, reload: bool = False):
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
